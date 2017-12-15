"""Client for the deepstream.io realtime web server"""
from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

from tornado.platform.twisted import TwistedIOLoop
TwistedIOLoop().install() # TODO: Is this compatible with alternative reactors?
from twisted.logger import Logger
log = Logger()
import txaio
txaio.use_twisted()
from deepstreampy import constants, message
import deepstreampy_twisted
from deepstreampy_twisted import protocol
from deepstreampy_twisted.protocol import DeepstreamFactory, DeepstreamProtocol
from twisted.plugin import pluginPackagePaths, getPlugins, IPlugin
__path__.extend(pluginPackagePaths(__name__))
list(getPlugins(IPlugin))



__all__ = ["DeepstreamClient, DeepstreamFactory, DeepstreamProtocol"]


version = "0.2.0"
version_info = (0, 2, 0)