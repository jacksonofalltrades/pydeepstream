"""Client for the deepstream.io realtime web server"""
from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

#from deepstreampy_twisted.client import connect
from deepstreampy_twisted import constants, message, protocol
from deepstreampy_twisted.protocol import DeepstreamFactory, DeepstreamProtocol


__all__ = ["DeepstreamClient, DeepstreamFactory, DeepstreamProtocol, constants"]


version = "0.2.0"
version_info = (0, 2, 0)
