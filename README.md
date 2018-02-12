# pydeepstream
Python driver for Deepstream.io on Twisted with Autobahn. This project provides an API interface to communicate with a Deepstream server for Twisted applications. 

## Getting Started

### Installing

```# From the repo root folder
pip install -r requirements.txt
pip install ./
```
Or, alternatively,
```#From the repo root folder
pip install --process-dependency-links ./
```

### Usage
In this example, we connect to a local Deepstream server, login anonymously, say hello to the 'chat' topic, subscribe to that topic, and then disconnect after 2 seconds.
```
def the_callback(message=None):
    print("Received event :" + str(message))
from twisted.internet import reactor # Select your reactor
client = DeepstreamClient(url='ws://localhost:6020/deepstream', debug='verbose',) # Debug has three options: False disables it, "verbose" enables verbose mode, and any other value enables normal debug mode.
client.connect(lambda : client.login({})) # .connect accepts a callback once connection is established to trigger authentication
client.whenAuthenticated(client.event.emit, 'chat', 'hello world') # Submit "hello world" to any listeners on the "chat" topic
client.whenAuthenticated(client.event.subscribe, 'chat', the_callback) # "Subscribe to the "chat" topic; upon receiving an event, call the callback we defined earlier
reactor.callLater(2, client.disconnect) # Two seconds after running the reactor, disconnect.
reactor.run()
```

For further reading, start in the `DeepstreamClient` class in `deepstreampy_twisted/interface.py`

Also check out the functions in `EventEmitter`, from which DeepstreamClient inherits.    
The events available are defined upstream in [`deepstreampy.constants.event`](https://github.com/YavorPaunov/deepstreampy/blob/dev/deepstreampy/constants/event.py).  
These events are distinct from the Deepstream.io Events feature; they are used only internally.  

`DeepstreamClient` also makes some upstream features available as properties. To investigate their interface, see the code upstream:
- [Events](https://github.com/YavorPaunov/deepstreampy/blob/dev/deepstreampy/event.py)
- [RPC](https://github.com/YavorPaunov/deepstreampy/blob/dev/deepstreampy/rpc.py)
- [Records](https://github.com/YavorPaunov/deepstreampy/blob/dev/deepstreampy/record.py)
- [Presence](https://github.com/YavorPaunov/deepstreampy/blob/dev/deepstreampy/presence.py)
 


## Running the tests
First, install the extra dev requirements  
`pip install -r dev_requirements.txt`  
Then you may run the tests  
`trial tests`

## Built With

* [Twisted Matrix](https://twistedmatrix.com/trac/) - network engine
* [Autobahn](https://github.com/crossbario/autobahn-python) - provides WebSocket protocol & factory for Twisted
* [deepstreampy](https://github.com/YavorPaunov/deepstreampy) - provides an interface for deepstreampy's non-connection-related features

## Authors
* **Will Crawford** - Adaptation to Twisted; connection layer in Twisted + interface to  - [Sapid](https://github.com/sapid)

## License
This project is licensed under MIT - see the [LICENSE](LICENSE) file for details.
