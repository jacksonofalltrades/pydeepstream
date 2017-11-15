#!/usr/bin/env python
from autobahn.twisted.websocket import WebSocketClientProtocol, WebSocketClientFactory

class DeepstreamProtocol(WebSocketClientProtocol):
    # Protocols are used once per session; they are not re-used. 
    # If reconnection occurs, a new protocol is created by the factory in use.
    def onConnect(self, response):
        # TODO: Anything to do?
        # Options:
        #  Check or set cookies or other HTTP headers
        #  Verify IP address
        # TODO: Verify we're speaking Deepstream, a subprotocol of WebSocket, essentially
        print("Connected to Server: {}".format(response.peer))
    def onOpen(self):
        # TODO: If we have auth information stored, negotiate authentication again.
        # TODO: Switch flag to start flushing message queue as well?
        print("Connection opened.")
        self.transport.write("Hello")
    def onMessage(self, payload, isBinary):
        if isBinary:
            raise NotImplementedError
        else:
            text = payload.decode('utf8')
            print(text)
    def onClose(self, wasClean, code, reason):
        # TODO: Anything to do?
        print("WebSocket connection closed: {}".format(reason))
    def sendData(self, data):
        # TODO: Batch messages
        self.transport.write(data)

class DeepstreamFactory(WebSocketClientFactory):
    # Factories store any stateful information a protocol might need.
    # This way, if reconnection occurs, that state information is still available to the new protocol.
    auth = (None, None)
    protocol = None
    def __init__(self, url, enableCompression=False, autoFragmentSize=1024):
        # TODO: Any relevant init
        return 


# The following code should only be used for testing and developing this library.
if __name__ == '__main__':
    import sys
    from twisted.python import log
    from twisted.internet import reactor
    from twisted.internet.protocol import Factory
    from twisted.internet.endpoints import clientFromString

    log.startLogging(sys.stdout)
    wrappedFactory = Factory.forProtocol(DeepstreamProtocol) 
    #factory = DeepstreamFactory()
    # TODO: Set auth information for factory
    #factory.protocol = DeepstreamProtocol
    endpoint = clientFromString(reactor, "autobahn:tcp\:172.19.0.2\:6020:url=ws\://172.19.0.2/deepstream\:6020")
    endpoint.connect(wrappedFactory)
    #reactor.connectTCP("127.0.0.1", 8020, factory)
    reactor.run()

