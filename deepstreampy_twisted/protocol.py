#!/usr/bin/env python
# Adapted from https://github.com/YavorPaunov/deepstreampy under MIT License
# Author: Will Crawford, github.com/sapid
from __future__ import print_function
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
    def onMessage(self, payload, isBinary):
        self.debugExec()
        if isBinary:
            raise NotImplementedError("Received binary message; expected string")
        self.debug("Received: " + payload)
        full_buffer = self.factory._message_buffer + payload
        split_buffer = full_buffer.rsplit(constants.message.MESSAGE_SEPERATOR, 1)
        if len(split_buffer) > 1:
            self.factory._message_buffer = split_buffer[1]
        raw_messages = split_buffer[0]
        parsed_messages = message_parser.parse(raw_messages, self.factory.client)
        for msg in parsed_messages:
            if msg is None:
                continue
            elif msg['topic'] == constants.topic.CONNECTION:
                self._handle_connection_response(msg)
            elif msg['topic'] == constants.topic.AUTH:
                self._handle_auth_response(msg)
            else:
                self.factory.client._on_message(parsed_messages[0])

    def _heartbeat(self):
        self.debugExec()
        elapsed = time.time() - self.factory._heartbeat_last
        if elapsed >= self.factory._heartbeat_tolerance:
            self.log.error("Heartbeat missed. Closing connection.")
            self.transport.loseConnection()
    def _send_auth_params(self):
        self.debugExec()
        self.factory._set_state(constants.connection_state.AUTHENTICATING)
        authParams = self.factory.authParams
        if authParams is None:
            authParams = {}
        raw_auth_message = message_builder.get_message(
            constants.topic.AUTH,
            constants.actions.REQUEST,
            [authParams]
        )
        self.send(raw_auth_message)
    def _get_auth_data(self, data):
        self.debugExec()
        if data:
            return message_parser.convert_typed(data, self.factory.client)
    def _handle_auth_response(self, message):
        message_data = message['data']
        message_action = message['action']
        data_size = len(message_data)
        if message_action == constants.actions.ERROR:
            if (message_data and
                message_data[0] == constants.event.TOO_MANY_AUTH_ATTEMPTS):
                self.factory._deliberate_close = True
                self.factory._too_many_auth_attempts = True
                if self._client:
                    self._client._service.stopService()
                else:
                    self.transport.loseConnection()
            else:
                self.factory._set_state(
                    constants.connection_state.AWAITING_AUTHENTICATION)
            auth_data = (self._get_auth_data(message_data[1]) if
                          data_size > 1 else None)
            if self.factory._auth_deferred:
                self.factory.reactor.callLater(0, self.factory._auth_deferred.callback,
                                                {'success': False,
                                                'error': message_data[0] if data_size else None,
                                                'message': auth_data})
        elif message_action == constants.actions.ACK:
            self.factory._set_state(constants.connection_state.OPEN)
            auth_data = (self._get_auth_data(message_data[0]) if
                         data_size else None)
            if self.factory._auth_deferred and self.factory._auth_deferred is not None:
                self.factory.reactor.callLater(0, self.factory._auth_deferred.callback,
                                                {'success': True,
                                                'error': None,
                                                'message': auth_data})
        self.factory._send_queued_messages()
    def _handle_connection_response(self, message):
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
            if self.factory._connect_callback:
                self.factory.reactor.callLater(0, self.factory._connect_callback)
            if self.factory._auto_auth:
                self._send_auth_params()
        elif action == constants.actions.CHALLENGE:
            challenge_response = message_builder.get_message(
                constants.topic.CONNECTION,
                constants.actions.CHALLENGE_RESPONSE,
                [self.factory.url])
            self.factory._set_state(constants.connection_state.CHALLENGING)
            self.send(challenge_response)
        elif action == constants.actions.REJECTION:
            self._challenge_denied = True
            self.close()
        elif action == constants.actions.REDIRECT:
            self.factory.url = data[0]
            self._redirecting = True
            self.close()
        elif action == constants.actions.ERROR:
            if data[0] == constants.event.CONNECTION_AUTHENTICATION_TIMEOUT:
                self._deliberate_close = True
                self._connection_auth_timeout = True
                self._client._on_error(
                    constants.topic.CONNECTION, data[0], data[1])
    def onClose(self, wasClean, code, reason):
        if wasClean:
            self.factory._set_state(constants.connection_state.ERROR)
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
            message = message.encode()
        self.debug("Sending: %s" % message)
        self.sendMessage(message)

    def sendMessage(self, payload):
        self.debugExec()
        return self.transport.write(payload)

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
    @property
    def _client(self):
        if hasattr(self.factory, 'client'):
            return self.factory.client
        else:
            return None

class WSDeepstreamProtocol(DeepstreamProtocol, WebSocketClientProtocol):
    def connectionMade(self):
        WebSocketClientProtocol.connectionMade(self)
        DeepstreamProtocol.connectionMade(self)
    def sendMessage(self, payload):
        self.debugExec()
        return WebSocketClientProtocol.sendMessage(self, payload)


class DeepstreamFactory(ClientFactory):
    # Factories store any stateful information a protocol might need.
    # This way, if reconnection occurs, that state information is still available to the new protocol.
    protocol = DeepstreamProtocol
    def __init__(self, url, client=None, *args, **kwargs):
        # url: (str) the URL to connect to
        # reactor (IReactor) (optional) the reactor instance
        # debug: (bool or str) (optional) print debug messages, 'verbose' for more debug messages
        # heartbeat_interval: (double) (optional) interval to check heartbeat
        # auth_params: (dict) (optional) e.g. {} or {'username': 'AzureDiamond', 'password': 'hunter2'}
        #              Providing auth_params will enable auto-auth on connect;
        #              otherwise, auth must be done manually with self.authenticate or client.login
        # authCallback (func) # Callback triggered by successful authentication
        self.url = url
        self.reactor = kwargs.pop('reactor', None)
        if self.reactor is None:
            from twisted.internet import reactor
            self.reactor = reactor
        self._original_url = url
        self.client = client
        self._state = constants.connection_state.CLOSED
        kwargs['url'] = url
        self.debug = kwargs.pop('debug', False)
        if self.debug:
            global inspect
            import inspect
            txaio.start_logging(level='debug')
            print('Debug enabled.')
            if self.debug == 'verbose':
                defer.setDebugging(on=True)

        self._heartbeat_interval = kwargs.pop('heartbeat_interval', 100)
        self._heartbeat_tolerance = self._heartbeat_interval * 2
        self._heartbeat_looper = None
        self._heartbeat_last = None
        self._message_buffer = ''
        self._queued_messages = deque()
        self.authParams = kwargs.pop('authParams', None)
        self._auto_auth = False
        if self.authParams is not None:
            self._auto_auth = True
        self.authToken = None
        self._auth_deferred = None
        self._connect_callback = None
        self.authCallback = kwargs.pop('authCallback', None)
        if self.authCallback:
            if callable(self.authCallback):

                self.addAuthCallback(self.authCallback)
            else:
                raise ValueError("authCallback must be a callable")

        self._deliberate_close = False
        self._too_many_auth_attempts = False
        self._challenge_denied = False
        self._connection_auth_timeout = False

    def authenticate(self, auth_params):
        self.authParams = auth_params
        result = None
        if not self._auth_deferred or self._auth_deferred is None:
            self._auth_deferred = defer.Deferred()
        if (self._too_many_auth_attempts or
                self._challenge_denied or
                self._connection_auth_timeout):
            msg = "This client's connection was closed."
            self.client._on_error(constants.topic.ERROR,
                                   constants.event.IS_CLOSED,
                                   msg)
            result = {  'success': False,
                        'error': constants.event.IS_CLOSED,
                        'message': msg
                     }
        elif (self._deliberate_close and
                      self._state == constants.connection_state.CLOSED):
            self._deliberate_close = False
            if not self.client._service.running:
                self.client.connect(callback=lambda: self.authenticate(auth_params))
        elif self._state == constants.connection_state.AWAITING_AUTHENTICATION:
            self.reactor.callLater(0, self._protocol_instance._send_auth_params)
        if result:
            self.reactor.callLater(0,self._auth_deferred.callback, result)
        return self._auth_deferred
    def _set_state(self, state):
        # This state keeps track of the connection with Deepstream per the
        # Deepstream spec. This state is distinct from the state
        # handled by ReconnectingClientFactory.
        self._state = state
        if self.client:
            self.client.emit(constants.event.CONNECTION_STATE_CHANGED, state)
        log.info("Deepstream connection state set to " + str(state))
    def setAuth(self, authParams):
        # This is a dict containing authentication parameters to send to the Deepstream server.
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
    def _send_queued_messages(self):
        if self._state != constants.connection_state.OPEN:
            return
        while self._queued_messages:
            raw_message, deferred = self._queued_messages.popleft()
            r = defer.maybeDeferred(self._protocol_instance.send(raw_message))
            r.chainDeferred(deferred)

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
    def do_auth(factory):
        factory.authenticate({})
        d = factory._auth_deferred
        d.addCallback(print)
    factory = WSDeepstreamFactory("ws://localhost:6020/deepstream", debug='verbose')
    factory.protocol = WSDeepstreamProtocol
    endpoint = clientFromString(reactor, "tcp:localhost:6020")
    endpoint.connect(factory)
    reactor.callLater(1, do_auth, factory)
    reactor.run()
