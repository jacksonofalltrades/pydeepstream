from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

# TODO: Override tornado's gen and concurrent

from tornado.platform.twisted import TwistedIOLoop
from twisted.internet import reactor
TwistedIOLoop().install()

from deepstreampy_twisted import constants
from deepstreampy_twisted.protocol import DeepstreamFactory
from deepstreampy_twisted.client import Client
from deepstreampy_twisted.event import EventHandler
from deepstreampy_twisted.message import connection, message_parser, message_builder
from tornado import ioloop


def connect(host, port=6020, url=None, **kwargs):
    if not url:
        url = "ws://%s:%s/deepstream" % (host, port)
    factory = DeepstreamFactory(url, debug=True)
    # TODO: Set auth information for factory
    reactor.connectTCP(host, port, factory)

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
        return self._client._factory._protocol_instance
    @property
    def factory(self):
        return self._client._factory
    def send(self, raw_message):
        return self.protocol.send(raw_message)
    @staticmethod
    def _stripped_send(protocol, raw_message):
        return protocol.send(raw_message)
    # def send_message(self, topic, action, data):
    #     message = message_builder.get_message(topic, action, data)
    #     return self.send(message)


class DeepstreamClient(Client):
    def __init__(self, host, port=6020, url=None, authParams=None, **options):
        # Optional params: port, url, authParams, heartbeat_interval
        if not host:
            raise ValueError("Must specify a hostname or IP for deepstream server.")
        if not url:
            url = "ws://%s:%s/deepstream" % (host, port)
        self._factory = DeepstreamFactory(url, self, debug=options.pop('debug', False), **options)
        reactor.connectTCP(host, port, self._factory)
        super(Client, self).__init__()
        self._connection = ConnectionInterface(self, url)
        # self._presence = PresenceHandler(self._connection, self, **options)
        self._event = EventHandler(self._connection, self, **options)
        # self._rpc = RPCHandler(self._connection, self, **options)
        # self._record = RecordHandler(self._connection, self, **options)
        self._message_callbacks = dict()
        #
        # self._message_callbacks[
        #     constants.topic.PRESENCE] = self._presence.handle
        #
        self._message_callbacks[
            constants.topic.EVENT] = self._event.handle
        #
        # self._message_callbacks[
        #     constants.topic.RPC] = self._rpc.handle
        #
        # self._message_callbacks[
        #     constants.topic.RECORD] = self._record.handle
        #
        # self._message_callbacks[constants.topic.ERROR] = self._on_error
    def login(self, auth_params):
        # TODO: turn in to Deferred to return after authenticated properly?
        raise NotImplementedError("")
    def connect(self, callback=None):
        # TODO: Pass callback to onConnect
        reactor.run()



if __name__ == '__main__':
    def the_callback(message=None):
        print("Received event :" + str(message))
    client = DeepstreamClient('localhost', debug=True)
    reactor.callLater(1, client.event.emit, 'chat', 'hello world')
    reactor.callLater(1, client.event.subscribe, 'chat', the_callback)
    # NOTE: To see
    client.connect()

