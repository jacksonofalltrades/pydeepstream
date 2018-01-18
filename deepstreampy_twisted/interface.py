#!/usr/bin/env python
# Adapted from https://github.com/YavorPaunov/deepstreampy under MIT License
# Author: Will Crawford, github.com/sapid
from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

from tornado import ioloop

from deepstreampy import constants
from deepstreampy.record import RecordHandler

from deepstreampy_twisted.patch import PatchedEventHandler as EventHandler, \
    PatchedPresenceHandler as PresenceHandler, \
    PatchedRPCHandler as RPCHandler
from deepstreampy_twisted.protocol import WSDeepstreamFactory, WSDeepstreamProtocol
from deepstreampy_twisted import log

from pyee import EventEmitter

from deepstreampy.client import Client
from deepstreampy.event import EventHandler
from deepstreampy.message import connection
from twisted.application.internet import ClientService
from twisted.internet.endpoints import clientFromString
from twisted.internet import defer

from urlparse import urlparse


class ConnectionInterface(connection.Connection):
    '''This class largely serves as a compatibility layer for the original Tornado Deepstream client.
    Interaction with this interface should be largely unnecessary; the Client implements an interface to the
    functions an end-user is likely to need to use.'''
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
    @defer.inlineCallbacks
    def protocol(self):
        proto_d = yield self._client._service.whenConnected()
        if isinstance(proto_d, WSDeepstreamProtocol):
            defer.returnValue(proto_d)
        else:
            raise Exception("Failed to retrieve protocol")
    @protocol.setter
    def _set_protocol(self, p):
        raise NotImplementedError("Setting the protocol is not implemented via this attribute.")
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
        self.factory.authenticate(auth_params)
    def close(self):
        self._client.disconnect()


class DeepstreamClient(Client):
    '''
    This class instantiates an interface to interact with a Deepstream server.

    This class is the recommended mechanism for interacting with this module. It provides an interface to the other
    classes, each of which encapsulate a feature: Connection, Records, Events, RPC, and Presence.
    '''
    def __init__(self, url=None, conn_string=None, authParams=None, reactor=None, **options):
        ''' Creates the client, but does not connect to the server automatically.
        Optional keyword parameters (**options) for...
           Client: url (required), authParams, reactor, conn_string, debug, factory
           protocol: url (required), authParams, heartbeat_interval
           rpc: rpcAckTimeout, rpcResponseTimeout, subscriptionTimeout
           record: recordReadAckTimeout, merge_strategy, recordReadTimeout, recordDeleteTimeout, recordDeepCopy,
           presence: subscriptionTimeout
        '''

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
        factory = options.pop('factory', WSDeepstreamFactory)
        self._factory = factory(url, self, debug=options.pop('debug', False), reactor=reactor, **options)
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
        '''
        Submit authentication credentials to the server once state is "Awaiting Authentication."

        Expects a dictionary.
        Options:
          User/pass: {'username': 'my_username', 'password': 'hunter2'}
          Anonymous login/Open auth: {}
            https://deepstreamhub.com/tutorials/guides/open-auth/
          Email: {'type': 'email', 'email': 'my@email.com', 'password': 'hunter2'}
            https://deepstreamhub.com/tutorials/guides/email-auth/
          Token: {'token': 'abcdefg'}
            https://deepstreamhub.com/tutorials/guides/token-auth/

        Returns a Deferred
        '''
        return self._connection.authenticate(auth_params)
    def connect(self, callback=None):
        '''
        Connect to the server. Optionally, fire a callback once connected.

        Recommended callback is a login function.
        Calling the login function is automatic if the DeepstreamClient is instantiated with auth_params.
        '''
        if callback:
            self._factory._connect_callback = callback
        if not self._service.running:
            self._service.startService()
        return
    def close(self):
        '''Legacy method: disconnect from the server.'''
        return self.disconnect()
    def disconnect(self):
        '''Terminate our connection to the server.'''
        # TODO: Say goodbye; clear message queue?
        self._factory._deliberate_close = True
        self._service.stopService()
    def whenAuthenticated(self, callback, *args):
        '''Execute a callback once authentication has succeeded.'''
        if self._factory._state == constants.connection_state.OPEN:
            callback(*args)
        else:
            self.once(constants.event.CONNECTION_STATE_CHANGED,
                              lambda x: DeepstreamClient.whenAuthenticated(self, callback, *args))

    # These properties are the same as in the parent class, but are repeated here for clarity
    @property
    def connection_state(self):
        return self._connection.state

    @property
    def record(self):
        return self._record

    @property
    def event(self):
        return self._event

    @property
    def rpc(self):
        return self._rpc

    @property
    def presence(self):
        return self._presence




if __name__ == '__main__':
    def the_callback(message=None):
        print("Received event :" + str(message))
    from twisted.internet import reactor
    client = DeepstreamClient(url='ws://localhost:6020/deepstream', debug='verbose',)
    client.connect(lambda : client.login({}))
    client.whenAuthenticated(client.event.emit, 'chat', 'hello world')
    client.whenAuthenticated(client.event.subscribe, 'chat', the_callback)
    # reactor.callLater(2, client.disconnect)
    reactor.run()

