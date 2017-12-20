from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

from tornado import ioloop

from deepstreampy import constants
from deepstreampy.record import RecordHandler
from deepstreampy.event import EventHandler
from deepstreampy.rpc import RPCHandler
from deepstreampy.presence import PresenceHandler

from deepstreampy_twisted.protocol import WSDeepstreamFactory
from deepstreampy_twisted import log

from pyee import EventEmitter

from deepstreampy.client import Client
from deepstreampy.event import EventHandler
from deepstreampy.message import connection, message_parser, message_builder
from twisted.application.internet import ClientService
from twisted.internet.endpoints import clientFromString
from twisted.internet import defer

from urlparse import urlparse


class ConnectionInterface(connection.Connection):
    def __init__(self, client, url, **options):
        self._io_loop = ioloop.IOLoop.current()
        self._client = client
    @property
    def state(self):
        return self.factory._state
    @property
    def _state(self):
        return self.factory._state
    @_state.setter
    def __set_state(self, s):
        self.factory._state = s
    @property
    def protocol(self):
        return self._service.whenConnected()
    @protocol.setter
    def _set_protocol(self, p):
        raise NotImplementedError("Setting the protocol is not implemented via this method.")
    @property
    def factory(self):
        return self._client._factory
    def send(self, raw_message):
        return self.factory.send(raw_message)
    @property
    def _url(self):
        return self.factory.url
    @_url.setter
    def _url(self, value):
        self.factory.url = value
    @property
    def _original_url(self):
        return self.factory._original_url
    def connect(self, callback):
        return self._client.connect(callback)
    def authenticate(self, auth_params):
        self.protocol.authenticate(auth_params)
    def close(self):
        self._client.disconnect()


class DeepstreamClient(Client):
    def __init__(self, url=None, conn_string=None, authParams=None, reactor=None, **options):
        # Optional params for...
        #   Client: conn_string, authParams, reactor
        #   protocol: heartbeat_interval TODO
        #   rpc: TODO
        #   record: TODO
        #   presence: TODO
        if not url or url is None:
            raise ValueError("url is None; you must specify a  URL for the deepstream server, e.g. ws://localhost:6020/deepstream")
        parse_result = urlparse(url)
        if not authParams or authParams is None:
            authParams = {}
            if parse_result.username and parse_result.password:
                authParams['username'] = parse_result.username
                authParams['password'] = parse_result.password
        if not conn_string or conn_string is None:
            if parse_result.scheme == 'ws':
                if parse_result.hostname:
                    conn_string = 'tcp:%s' % parse_result.hostname
                if parse_result.port:
                    conn_string += ':%s' % parse_result.port
                else:
                    conn_string += ':6020'
        if not conn_string or conn_string is None:
            raise ValueError("Could not parse conn string from URL; you must specify a Twisted endpoint descriptor for the server, e.g. tcp:127.0.0.1:6020")
        if not reactor or reactor is None:
            from twisted.internet import reactor
        self.reactor = reactor
        self._factory = WSDeepstreamFactory(url, self, debug=options.pop('debug', False), reactor=reactor, **options)
        self._endpoint = clientFromString(reactor, conn_string)
        self._service = ClientService(self._endpoint, self._factory) # Handles reconnection for us

        EventEmitter.__init__(self)
        self._connection = ConnectionInterface(self, url)
        self._presence = PresenceHandler(self._connection, self, **options)
        self._event = EventHandler(self._connection, self, **options)
        self._rpc = RPCHandler(self._connection, self, **options)
        self._record = RecordHandler(self._connection, self, **options)
        self._message_callbacks = dict()

        self._message_callbacks[
            constants.topic.PRESENCE] = self._presence.handle
        self._message_callbacks[
            constants.topic.EVENT] = self._event.handle
        self._message_callbacks[
            constants.topic.RPC] = self._rpc.handle
        self._message_callbacks[
            constants.topic.RECORD] = self._record.handle
        self._message_callbacks[
            constants.topic.ERROR] = self._on_error


    def login(self, auth_params):
        d = defer.Deferred()
        # TODO: turn in to Deferred to return after authenticated properly?
        raise NotImplementedError("This client implementation authenticates automatically after a successful connection. Specify auth_params before starting the connection.")
    def connect(self, callback=None):
        if callback:
            self._factory._connect_callback = callback
        if not self._service.running:
            self._service.startService()
        return
    def close(self):
        return self.disconnect()
    def disconnect(self):
        # TODO: Say goodbye; clear message queue?
        self._factory._deliberate_close = True
        self._service.stopService()
    def whenAuthenticated(self, callback, *args):
        d = defer.Deferred()
        d.addCallback(callback, *args)
        # Offer a deferred that will fire when we connect.
        pass




if __name__ == '__main__':
    def the_callback(message=None):
        print("Received event :" + str(message))
    from twisted.internet import reactor
    client = DeepstreamClient(url='ws://localhost:6020/deepstream', debug='verbose',)
    client.connect(lambda : client.login({}))
    reactor.callLater(1, client.event.emit, 'chat', 'hello world')
    reactor.callLater(1, client.event.subscribe, 'chat', the_callback)
    # reactor.callLater(2, client.disconnect)
    reactor.run()

