#!/usr/bin/env python
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory
from twisted.internet import task as twisted_task
from twisted.internet.protocol import ReconnectingClientFactory
from deepstreampy_twisted import constants
import time
from deepstreampy_twisted.message import message_parser, message_builder
from twisted.python import log
import txaio
import inspect # TODO: For debug only

class ErrorCatcher(object):
    def __init__(self, func):
        self._on_error = func

class DeepstreamProtocol(WebSocketClientProtocol):
    # Protocols are used once per session; they are not re-used. 
    # If reconnection occurs, a new protocol is created by the factory in use.
    def onConnect(self, response):
        self.debugExec()
        # Options:
        #  Check or set cookies or other HTTP headers
        #  Verify IP address
        # TODO: Verify we're speaking Deepstream, a subprotocol of WebSocket, essentially
        #       Update: may not be possible; there doesn't seem to be an "info" call or anything
        print("Connected to Server: {}".format(response.peer))
        # TODO: Register handlers
        if self.factory._state != constants.connection_state.AWAITING_CONNECTION:
            self.factory._set_state(constants.connection_state.AWAITING_CONNECTION)
        self.debug("onConnect response: {}".format(response))
    def onOpen(self):
        self.debugExec()
        # TODO: If auth is open, we don't need auth information to login. 
        #         How can we check if auth is open? Attempt to login anyway and catch exceptions?
        #         Per https://deepstream.io/info/protocol/all-messages/ it may not be possible to query for state.
        self.debug("Connection opened.")
        # TODO: Register handlers
        self._heartbeat_last = time.time()
        l = twisted_task.LoopingCall(self._heartbeat)
        self.factory._heartbeat_looper = l
        # TODO: Reset retry timer in reconnectfactory.
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
        raw_error_message = event + ': ' + msg
        if topic:
            raw_error_message += ' (' + topic + ')'
        raise ValueError(raw_error_message)
    def send(self, message):
        self.debugExec()
        # TODO: Buffer messages
        if isinstance(message, unicode):
            #message = message.encode("utf-8")
            message = message.encode()
        self.sendMessage(message)

    def onMessage(self, payload, isBinary):
        self.debugExec()
        if isBinary:
            raise NotImplementedError
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
                raise NotImplementedError(msg) # TODO: Send to client object?


    def _heartbeat(self):
        self.debugExec()
        elapsed = time.time() - self.factory._heartbeat_last
        if elapsed >= self.factory._heartbeat_tolerance:
            self.debug("Heartbeat missed. Closing connection.")
            self.transport.loseConnection()
            # TODO: Inform logger
        # TODO: Check if we've missed any.
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
        print(inspect.stack()[0][3] + " from " + inspect.stack()[1][3])
        # TODO: Anything to do?
        #       Should state be set to ERROR if wasClean is false?
        self.factory._set_state(constants.connection_state.CLOSED)
        print("WebSocket connection closed: {}".format(reason))
        if self.factory._heartbeat_looper and self.factory._heartbeat_looper.running:
            self.factory._heartbeat_looper.stop()
        self.factory._heartbeat_looper = None
        self.factory._heartbeat_last = None

    def sendMessage(self, payload):
        self.debugExec()
        super(DeepstreamProtocol, self).sendMessage(payload)
        self.debug("Sent " + str(payload))
    #def sendData(self, data, **kwargs):
    #    self.debugExec()
    #    # TODO: Batch messages
    #    super(DeepstreamProtocol, self).sendData(data, **kwargs)
    #    self.debug("Sent " + str(data))
    def debug(self, message):
        self.debugExec()
        if not self.factory.debug:
            return
        if isinstance(message, str):
            message = unicode(message, 'utf-8')
        self.log.debug(message.replace(chr(31), '|').replace(chr(30), '+'))
    def debugExec(self):
        if not self.factory.debug:
            return
        self.log.debug(inspect.stack()[1][3])

class DeepstreamFactory(WebSocketClientFactory, ReconnectingClientFactory):
    # Factories store any stateful information a protocol might need.
    # This way, if reconnection occurs, that state information is still available to the new protocol.
    # In the Twisted paradigm, the factory is initialized then handed off to the reactor which initiates the connection.
    # TODO note: Important for message queue: self.(connection?).
    handlers_needed = [
                       #constants.topic.CONNECTION,
                       #constants.topic.AUTH,
                       constants.topic.EVENT,
                       constants.topic.PRIVATE,
                       constants.topic.RPC,
                       constants.topic.ERROR,
                       constants.topic.PRESENCE,
                       constants.topic.RECORD,
                       ]
    protocol = DeepstreamProtocol
    def __init__(self, url, client=None, *args, **kwargs):
        # url: (str) the URL to connect to
        # debug: (bool) (optional) print debug messages
        # heartbeat_interval: (double) (optional) interval to check heartbeat
        # auth_params: (dict) # TODO: Document structure expected
        # authCallback (func) # Callback triggered by successful authentication
        self.url = url
        if client:
            self.client = client
        self._state = constants.connection_state.CLOSED
        kwargs['url'] = url
        self.debug = kwargs.pop('debug', False)
        if self.debug:
            txaio.start_logging(level='debug')
        self._heartbeat_interval = kwargs.pop('heartbeat_interval', 100)
        self._heartbeat_tolerance = self._heartbeat_interval * 2
        self._heartbeat_looper = None
        self._heartbeat_last = None
        self._message_buffer = ''
        self.authParams = kwargs.pop('authParams', None)
        self.authToken = None
        #self.authCallback = kwargs.pop('authCallback', None)
        self._auth_future = None # TODO: Convert to Deferred
        super(DeepstreamFactory, self).__init__(*args, **kwargs)
    def _set_state(self, state):
        # This state keeps track of the connection with Deepstream per the
        # Deepstream spec. This state is distinct from the state
        # handled by ReconnectingClientFactory.
        self._state = state
        print "State set to " + str(state)
    def setAuth(self, authParams):
        # TODO: Write docstring
        self.authParams = authParams
    def startedConnecting(self, connector):
        self._set_state(constants.connection_state.AWAITING_CONNECTION)
    # TODO: def clientConnectionFailed and def clientConnectionLost are inherited from ReconnectingClientFactory.
    #       Can we add _set_state updates to these?
    #       Should be able to just call retry with super, also.
    #       TODO: Retry timer doesn't reset on connect.


# The following code should only be used for testing and developing this library.
if __name__ == '__main__':
    from twisted.internet import reactor
    from autobahn.twisted.websocket import WebSocketClientFactory,WebSocketClientProtocol

    factory = DeepstreamFactory("ws://localhost:6020/deepstream", debug=True)
    # TODO: Set auth information for factory
    factory.protocol = DeepstreamProtocol
    reactor.connectTCP("127.0.0.1", 6020, factory)
    reactor.run()

