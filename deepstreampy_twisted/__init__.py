"""Twisted-compatible Client for the deepstream.io realtime web server"""
from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

from tornado.platform.twisted import TwistedIOLoop

TwistedIOLoop().install()  # Incompatible with alternative reactors.
from twisted.logger import Logger

log = Logger()
import txaio

txaio.use_twisted()
from deepstreampy import constants, message
import deepstreampy_twisted
from deepstreampy_twisted import protocol
from deepstreampy_twisted.protocol import DeepstreamFactory, DeepstreamProtocol, WSDeepstreamProtocol, \
    WSDeepstreamFactory
from deepstreampy_twisted.interface import DeepstreamClient

__all__ = ["DeepstreamClient, WSDeepstreamFactory, WSDeepstreamProtocol"]

version = "0.2.0"
version_info = (0, 2, 0)
