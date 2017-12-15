from __future__ import absolute_import
from zope.interface import implementer
from twisted.plugin import IPlugin
from twisted.internet.interfaces import IStreamClientEndpoint, ITransport

try:
    from twisted.internet.interfaces import IStreamClientEndpointStringParserWithReactor
    _HAS_REACTOR_ARG = True
except ImportError:
    _HAS_REACTOR_ARG = False
    from twisted.internet.interfaces import IStreamClientEndpointStringParser as \
        IStreamClientEndpointStringParserWithReactor

from twisted.internet.endpoints import clientFromString
from autobahn.twisted.websocket import WrappingWebSocketClientFactory, WebSocketClientFactory, \
    WebSocketClientProtocol, WrappingWebSocketAdapter, WrappingWebSocketClientProtocol
from twisted.plugins.autobahn_endpoints import _parseOptions
import txaio
import random

from autobahn.websocket.compress import PerMessageDeflateOffer, \
    PerMessageDeflateOfferAccept, \
    PerMessageDeflateResponse, \
    PerMessageDeflateResponseAccept

@implementer(IPlugin)
@implementer(IStreamClientEndpointStringParserWithReactor)
class PatchedAutobahnClientParser(object):
    prefix = "pautobahn"

    def parseStreamClient(self, *args, **options):
        if _HAS_REACTOR_ARG:
            reactor = args[0]
            if len(args) != 2:
                raise RuntimeError("pautobahn: client plugin takes exactly one positional argument")
            description = args[1]
        else:
            from twisted.internet import reactor
            if len(args) != 1:
                raise RuntimeError("pautobahn: client plugin takes exactly one positional argument")
            description = args[0]
        opts = _parseOptions(options)
        endpoint = clientFromString(reactor, description)
        return PatchedAutobahnClientEndpoint(reactor, endpoint, opts)

@implementer(IPlugin)
@implementer(IStreamClientEndpoint)
class PatchedAutobahnClientEndpoint(object):

    def __init__(self, reactor, endpoint, options):
        self._reactor = reactor
        self._endpoint = endpoint
        self._options = options

    def connect(self, protocolFactory):
        return self._endpoint.connect(PatchedWrappingWebSocketClientFactory(protocolFactory, reactor=self._reactor, **self._options))


patchedAutobahnClientParser = PatchedAutobahnClientParser()

class PatchedWrappingWebSocketClientFactory(WebSocketClientFactory):
    '''Identical to its parent class except it wraps a factory.'''
    # def __init__(self,
    #              factory,
    #              url,
    #              *args, **kwargs):
    #     """
    #     Implements :func:`autobahn.websocket.interfaces.IWebSocketClientChannelFactory.__init__`
    #     """
    #     self._factory = factory
    #     kwargs['url'] = url
    #     super(PatchedWrappingWebSocketClientFactory, self).__init__(*args, **kwargs)
    def __init__(self,
                 factory,
                 url,
                 reactor=None,
                 enableCompression=True,
                 autoFragmentSize=0,
                 subprotocol=None):
        """

        :param factory: Stream-based factory to be wrapped.
        :type factory: A subclass of ``twisted.internet.protocol.Factory``
        :param url: WebSocket URL of the server this client factory will connect to.
        :type url: unicode
        """
        self._factory = factory
        self._subprotocols = ['binary']
        if subprotocol:
            self._subprotocols.append(subprotocol)

        WebSocketClientFactory.__init__(self,
                                        url=url,
                                        reactor=reactor,
                                        protocols=self._subprotocols)

        # automatically fragment outgoing traffic into WebSocket frames
        # of this size
        self.setProtocolOptions(autoFragmentSize=autoFragmentSize)

        # play nice and perform WS closing handshake
        self.setProtocolOptions(failByDrop=False)

        if enableCompression:
            # Enable WebSocket extension "permessage-deflate".

            # The extensions offered to the server ..
            offers = [PerMessageDeflateOffer()]
            self.setProtocolOptions(perMessageCompressionOffers=offers)

            # Function to accept responses from the server ..
            def accept(response):
                if isinstance(response, PerMessageDeflateResponse):
                    return PerMessageDeflateResponseAccept(response)

            self.setProtocolOptions(perMessageCompressionAccept=accept)
    def buildProtocol(self, addr):
        proto = WrappingWebSocketClientProtocol()
        proto.factory = self
        proto._proto = self._factory.buildProtocol(addr)
        proto._proto.transport = proto
        return proto

@implementer(ITransport)
class PatchedWrappingWebSocketClientProtocol(WrappingWebSocketAdapter):
    pass

