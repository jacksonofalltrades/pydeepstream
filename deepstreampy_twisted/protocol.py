#!/usr/bin/env python
from twisted.internet import defer, task as twisted_task
from twisted.internet.protocol import Protocol, ClientFactory
from deepstreampy import constants
import time
from deepstreampy.message import message_parser, message_builder
from deepstreampy_twisted import log
from collections import deque
import txaio
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory


class ErrorCatcher(object):
    def __init__(self, func):
        self._on_error = func

class DeepstreamProtocol(Protocol):
    # Protocols are used once per session; they are not re-used.
    # If reconnection occurs, a new protocol is created by the factory in use.
    def connectionMade(self):
        self.debugExec()
        if self.factory._state != constants.connection_state.AWAITING_CONNECTION:
            self.factory._set_state(constants.connection_state.AWAITING_CONNECTION)
    def onConnect(self, response):
        self.debugExec()
        log.info("Connected to Server: {}".format(response.peer))
        self.debug("Whole response received: %s" % response)
    def onOpen(self):
        self.debugExec()
        self.debug("Connection opened.")
        self._heartbeat_last = time.time()
        l = twisted_task.LoopingCall(self._heartbeat)
        self.factory._heartbeat_looper = l
        self.factory._protocol_instance = self
    def _catch_error(self, topic, event, msg=None):
        self.debugExec()
        # Adapted from https://github.com/YavorPaunov/deepstreampy under MIT License
        if event in (constants.event.ACK_TIMEOUT,
                     constants.event.RESPONSE_TIMEOUT):
            if (self.factory._state == constants.connection_state.AWAITING_AUTHENTICATION):
                error_msg = ("Message timed out because authentication is incomplete.")
                self.factory.reactor.callLater(0.1, lambda: self._catch_error(event.NOT_AUTHENTICATED,
                                                                              constants.topic.ERROR,
                                                                              error_msg))
        # TODO: If we end up having listeners for errors, notify them here.
        #         Use pyee?
        raw_error_message = event + ': ' + msg
        if topic:
            raw_error_message += ' (' + topic + ')'
        raise ValueError(raw_error_message)

    def onMessage(self, payload, isBinary):
        self.debugExec()
        if isBinary:
            raise NotImplementedError("Received binary message; expected string")
        self.debug("Received: " + payload)
        # TODO: Do we need to catch decoding errors?
        #text = payload.decode('UTF-8', errors='strict') # Unnecessary?
        full_buffer = self.factory._message_buffer + payload
        split_buffer = full_buffer.rsplit(constants.message.MESSAGE_SEPERATOR, 1)
        if len(split_buffer) > 1:
            self.factory._message_buffer = split_buffer[1]
        raw_messages = split_buffer[0]
        # TODO Urgent: Uncomment below once message_parser is fixed
        parsed_messages = message_parser.parse(raw_messages, ErrorCatcher(self._catch_error))
        for msg in parsed_messages:
            if msg is None:
                continue
            elif msg['topic'] == constants.topic.CONNECTION:
                self._connection_response_handler(msg)
            elif msg['topic'] == constants.topic.AUTH:
                self._auth_response_handler(msg)
            else:
                self.factory.client._on_message(parsed_messages[0])

    # def dataReceived(self, data):
    #     self.log.debug(data)
    def _heartbeat(self):
        self.debugExec()
        elapsed = time.time() - self.factory._heartbeat_last
        if elapsed >= self.factory._heartbeat_tolerance:
            self.log.error("Heartbeat missed. Closing connection.")
            self.transport.loseConnection()
    def authenticate(self):
        # Dead code: we automatically authenticate when we receive "C|A+"
        #            instead of making our client call authentication manually
        self.debugExec()
        self._auth_params = self.factory.authParams
        #self._auth_future = concurrent.Future() # Change to deferred? Do we need this?

        # if (self._too_many_auth_attempts or
        #         self._challenge_denied or
        #         self._connection_auth_timeout):
        #     msg = "this client's connection was closed"
        #     self._client._on_error(constants.topic.ERROR,
        #                            constants.event.IS_CLOSED,
        #                            msg)
        #     self._auth_future.set_result(
        #         {'success': False,
        #          'error': constants.event.IS_CLOSED,
        #          'message': msg})
        #
        # elif (self._deliberate_close and
        #               self._state == constants.connection_state.CLOSED):
        #     self.connect()
        #     self._deliberate_close = False
        #     self._client.once(constants.event.CONNECTION_STATE_CHANGED,
        #                       lambda: self.authenticate(auth_params))

        if self.factory._state == constants.connection_state.AWAITING_AUTHENTICATION:
            self._send_auth_params()

        return self._auth_future
        self.factory._set_state(constants.connection_state.AUTHENTICATING)
    def _send_auth_params(self):
        self.debugExec()
        self.factory._set_state(constants.connection_state.AUTHENTICATING)
        authParams = self.factory.authParams
        if authParams is None:
            authParams = {}
        raw_auth_message = message_builder.get_message(
            constants.topic.AUTH,
            constants.actions.REQUEST,
            [{}]
        )
        self.send(raw_auth_message)
    def _get_auth_data(self, data):
        self.debugExec()
        if data:
            return message_parser.convert_typed(data, ErrorCatcher(self._catch_error()))
    def _auth_response_handler(self, message):
        message_data = message['data']
        message_action = message['action']
        data_size = len(message_data)
        if message_action == constants.actions.ERROR:
            if (message_data and
                message_data[0] == constants.event.TOO_MANY_AUTH_ATTEMPTS):
                self.transport.loseConnection() # TODO: Prevent reconnection
            else:
                self.factory._set_state(
                    constants.connection_state.AWAITING_AUTHENTICATION)
            # auth_data = (self._get_auth_data(message_data[1]) if
            #              data_size > 1 else None)
            # if self._auth_future:
            #     self._auth_future.set_result(
            #         {'success': False,
            #          'error': message_data[0] if data_size else None,
            #          'message': auth_data}
            #     )
        elif message_action == constants.actions.ACK:
            self.factory._set_state(constants.connection_state.OPEN)
            # auth_data = (self._get_auth_data(message_data[0]) if
            #             data_size else None)
            # if self._auth_future:
            #     self._auth_future.set_result(
            #         {'success': True,
            #          'error': None,
            #          'message': auth_data}
            #     )

        # TODO: Flush outgoing message queue
        # TODO: Offer a Deferred for finishing authentication?
    def _connection_response_handler(self, message):
        self.debugExec()
        action = message['action']
        data = message['data']
        if action == constants.actions.PING:
            self._heartbeat_last = time.time()
            ping_response = message_builder.get_message(
                constants.topic.CONNECTION, constants.actions.PONG)
            self.send(ping_response)
        elif action == constants.actions.ACK:
            self.factory._set_state(constants.connection_state.AWAITING_AUTHENTICATION)
            self._send_auth_params()
        elif action == constants.actions.CHALLENGE:
            challenge_response = message_builder.get_message(
                constants.topic.CONNECTION,
                constants.actions.CHALLENGE_RESPONSE,
                [self.factory.url])
            self.factory._set_state(constants.connection_state.CHALLENGING)
            self.send(challenge_response)
    def onClose(self, wasClean, code, reason):
        # TODO: Anything else to do?
        #       Should state be set to ERROR if wasClean is false?
        self.factory._set_state(constants.connection_state.CLOSED)
        self.log.info("WebSocket connection closed: {}".format(reason))
        if self.factory._heartbeat_looper and self.factory._heartbeat_looper.running:
            self.factory._heartbeat_looper.stop()
        self.factory._heartbeat_looper = None
        self.factory._heartbeat_last = None
        self.factory._protocol_instance = None
    def send(self, message):
        self.debugExec()
        if isinstance(message, unicode):
            #message = message.encode("utf-8")
            message = message.encode()
        self.debug("Sending: %s" % message)
        self.sendMessage(message)

    def sendMessage(self, payload):
        self.debugExec()
        return self.transport.write(payload)
        # r = yield defer.maybeDeferred(self.transport.write(payload))
        # defer.returnValue(r)
        # super(DeepstreamProtocol, self).sendMessage(payload)
    #def sendData(self, data, **kwargs):
    #    self.debugExec()
    #    # TODO: Batch messages
    #    super(DeepstreamProtocol, self).sendData(data, **kwargs)
    #    self.debug("Sent " + str(data))
    def debug(self, message):
        if not self.factory.debug:
            return
        if isinstance(message, str):
            message = unicode(message, 'utf-8')
        log.debug(message.replace(chr(31), '|').replace(chr(30), '+').replace('{', '{{').replace('}', '}}'))
    def debugExec(self):
        if not self.factory.debug:
            return
        if self.factory.debug == 'verbose':
            log.debug(inspect.stack()[1][3])

class WSDeepstreamProtocol(DeepstreamProtocol, WebSocketClientProtocol):
    def connectionMade(self):
        WebSocketClientProtocol.connectionMade(self)
        DeepstreamProtocol.connectionMade(self)
    def sendMessage(self, payload):
        self.debugExec()
        return WebSocketClientProtocol.sendMessage(self, payload)
    #     # r = yield defer.maybeDeferred(WebSocketClientProtocol.sendMessage(self, payload))
    #     # defer.returnValue(r)

class DeepstreamFactory(ClientFactory):
    # Factories store any stateful information a protocol might need.
    # This way, if reconnection occurs, that state information is still available to the new protocol.
    # In the Twisted paradigm, the factory is initialized then handed off to the reactor which initiates the connection.
    # TODO note: Important for message queue: self.(connection?).
    protocol = DeepstreamProtocol
    def __init__(self, url, client=None, *args, **kwargs):
        # url: (str) the URL to connect to
        # debug: (bool) (optional) print debug messages
        # heartbeat_interval: (double) (optional) interval to check heartbeat
        # auth_params: (dict) # TODO: Document structure expected
        # authCallback (func) # Callback triggered by successful authentication
        self.url = url
        self.client = client
        self._state = constants.connection_state.CLOSED
        kwargs['url'] = url
        self.debug = kwargs.pop('debug', False)
        if self.debug:
            global inspect
            import inspect
            txaio.start_logging(level='debug')
            print('Debug enabled.')

        self._heartbeat_interval = kwargs.pop('heartbeat_interval', 100)
        self._heartbeat_tolerance = self._heartbeat_interval * 2
        self._heartbeat_looper = None
        self._heartbeat_last = None
        self._message_buffer = ''
        self._queued_messages = deque()
        self.authParams = kwargs.pop('authParams', None)
        self.authToken = None
        self._auth_deferred = defer.Deferred()
        self.authCallback = kwargs.pop('authCallback', None)
        if self.authCallback:
            if callable(self.authCallback):
                self._auth_deferred.addCallback(self.authCallback)
            else:
                raise ValueError("authCallback must be a callable")
    def _set_state(self, state):
        # This state keeps track of the connection with Deepstream per the
        # Deepstream spec. This state is distinct from the state
        # handled by ReconnectingClientFactory.
        # TODO: Emit state change to client
        self._state = state
        if self.client:
            self.client.emit(constants.event.CONNECTION_STATE_CHANGED, state)
        print "State set to " + str(state)
    def setAuth(self, authParams):
        # This is a dict containing authentication parameters to send to the Deepstream server.
        # TODO: Write better docstring
        self.authParams = authParams
    def startedConnecting(self, connector):
        self._set_state(constants.connection_state.AWAITING_CONNECTION)
    def send(self, raw_message):
        if self._state == constants.connection_state.OPEN and self._protocol_instance:
            return self._protocol_instance.send(raw_message)
        else:
            deferred = defer.Deferred()
            self._queued_messages.append((raw_message, deferred))
            return deferred
    def startFactory(self):
        print("Starting DS factory")
    # def buildProtocol(self, addr):
    #     super(DeepstreamFactory, self).buildProtocol(addr)

class WSDeepstreamFactory(DeepstreamFactory, WebSocketClientFactory):
    protocol = WSDeepstreamProtocol
    def __init__(self, url, *args, **kwargs):
        DeepstreamFactory.__init__(self, url, *args, **kwargs)
        WebSocketClientFactory.__init__(self,
            url=url,
            origin=kwargs.pop('origin', None),
            protocols=kwargs.pop('protocols', None),
            useragent=kwargs.pop('useragent', None),
            headers=kwargs.pop('headers', None),
            proxy=kwargs.pop('proxy', None),
        )


# The following code should only be used for testing and developing this library.
# See interface.py for an example on how to use this in production.
if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.internet.endpoints import clientFromString

    factory = WSDeepstreamFactory("ws://localhost:6020/deepstream", debug='verbose')
    factory.protocol = WSDeepstreamProtocol
    endpoint = clientFromString(reactor, "tcp:localhost:6020")
    endpoint.connect(factory)
    reactor.run()
