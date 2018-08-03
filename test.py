#!/usr/bin/env python
from pprint import pprint
from deepstreampy_twisted.interface import DeepstreamClient

client = DeepstreamClient(url='ws://localhost:6020/deepstream', debug='verbose')
client.record.get_record('some_record')  # returns some tornado thing. Gotta look in the `_records` attribute for something I can work with
record = client.record._records['some_record']

pprint(record)

record.when_ready(lambda ignored: record.subscribe(*args))  # <- this subscribe call is what I referenced earlier
