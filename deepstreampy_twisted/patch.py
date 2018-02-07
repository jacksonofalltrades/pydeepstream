from deepstreampy.event import EventHandler
from deepstreampy.presence import PresenceHandler
from deepstreampy.rpc import RPCHandler
from deepstreampy.utils import AckTimeoutRegistry
from functools import partial
from deepstreampy.constants import topic as topic_constants


class PatchedAckTimeoutRegistry(AckTimeoutRegistry):
    def add(self, name, action=None):
        unique_name = (action or "") + name

        self.remove(name, action)
        timeout = self._client.io_loop.call_later(self._timeout_duration,
                                                  partial(self._on_timeout,
                                                          unique_name,
                                                          name))
        self._register[unique_name] = timeout


class PatchedEventHandler(EventHandler):
    def __init__(self, connection, client, **options):
        super(PatchedAckTimeoutRegistry, self).__init__(connection, client, **options)
        subscription_timeout = options.get("subscriptionTimeout", 15)
        self._ack_timeout_registry = PatchedAckTimeoutRegistry(client,
                                                               topic_constants.EVENT,
                                                               subscription_timeout)


class PatchedPresenceHandler(PresenceHandler):
    def __init__(self, connection, client, **options):
        super(PatchedPresenceHandler, self).__init__(connection, client, **options)
        subscription_timeout = options.get("subscriptionTimeout", 15)
        self._ack_timeout_registry = PatchedAckTimeoutRegistry(
            client, topic_constants.PRESENCE, subscription_timeout)


class PatchedRPCHandler(RPCHandler):
    def __init__(self, connection, client, **options):
        super(PatchedRPCHandler, self).__init__(connection, client, **options)
        subscription_timeout = options.get("subscriptionTimeout", 15)
        self._ack_timeout_registry = PatchedAckTimeoutRegistry(
            client, topic_constants.RPC, subscription_timeout)
