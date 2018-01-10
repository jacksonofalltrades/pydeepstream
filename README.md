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
```
    def the_callback(message=None):
        print("Received event :" + str(message))
    from twisted.internet import reactor
    client = DeepstreamClient(url='ws://localhost:6020/deepstream', debug='verbose',)
    client.connect(lambda : client.login({}))
    client.whenAuthenticated(client.event.emit, 'chat', 'hello world')
    client.whenAuthenticated(client.event.subscribe, 'chat', the_callback)
    # reactor.callLater(2, client.disconnect)
    reactor.run()
```

( TODO - Better example code. )


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
* **Will Crawford** - *Initial work (Twisted adaptation)* - [Sapid](https://github.com/sapid)

## License
This project is licensed under MIT - see the [LICENSE](LICENSE) file for details.
