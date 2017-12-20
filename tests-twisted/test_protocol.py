from deepstreampy_twisted import protocol
from deepstreampy import constants
from twisted.trial import unittest
from twisted.test import proto_helpers
import sys
from twisted.internet import task

if sys.version_info[0] < 3:
    import mock
else:
    from unittest import mock


class ProtocolTests(unittest.TestCase):
    url = 'ws://localhost:0/deepstream'
    def setUp(self):
        self.client = mock.Mock()
        self.factory = protocol.DeepstreamFactory(
            ProtocolTests.url, client=self.client, debug='verbose', authParams={})
        self.clock = task.Clock()
        self.proto = self.factory.buildProtocol(('localhost', 0))
        self.proto.callLater = self.clock.callLater
        self.tr = proto_helpers.StringTransport()
        self.tr.protocol = self.proto
        self.proto.transport = self.tr
    def tearDown(self):
        self.tr.loseConnection()

    def _decode(self, message):
        message.replace(chr(31), '|').replace(chr(30), '+')
        if not isinstance(message,unicode) and isinstance(message, str):
            message = message.decode('utf-8')
        message = message.replace(chr(31), '|').replace(chr(30), '+')
        # message.replace(chr(31), '|').replace(chr(30), '+')
        return message
    def _encode(self, message):
        if isinstance(message,unicode):
            message = message.encode('utf-8')
        return message.replace('|', chr(31)).replace('+', chr(30))
    def _test(self, dataReceived, expected):
        self._server_emit(dataReceived)
        sent = self._decode(self.tr.value())
        self.assertEqual(sent, expected)
    def _server_emit(self, data):
        encoded_data = self._encode(data)
        self.proto.onMessage(encoded_data, False)
    def _get_connection_state_changes(self):
        count = 0
        for call_args in self.client.emit.call_args_list:
            if call_args[0][0] == constants.event.CONNECTION_STATE_CHANGED:
                count += 1
        return count
    def test_connects(self):
        # Start in state CLOSED
        self.assertEqual(self.factory._state, constants.connection_state.CLOSED)
        self.assertEqual(self._get_connection_state_changes(), 0)

        # Create the connection; move state to AWAITING_CONNECTION
        self.proto.makeConnection(self.tr)
        self.assertEqual(self.factory._state, constants.connection_state.AWAITING_CONNECTION)
        self.assertEqual(self._get_connection_state_changes(), 1)

        # Test receiving a message; move state to CHALLENGING
        self._test("C|CH+", "C|CHR|%s+" % ProtocolTests.url)
        self.assertEqual(self.factory._state, constants.connection_state.CHALLENGING)

        # Test receiving a message; move state to AWAITING_AUTHENTICATION, then AUTHENTICATING
        self._server_emit('C|A+')
        # We'll miss AWAITING_AUTHENTICATION, so we'll count state changes and check the 'at rest' state
        self.assertEqual(self._get_connection_state_changes(), 4)
        self.assertEqual(self.factory._state, constants.connection_state.AUTHENTICATING) # Potential timing issue
    def test_anon_auth(self):
        self.proto.makeConnection(self.tr)
        self.factory._state = constants.connection_state.CHALLENGING
        self._test('C|A+', 'A|REQ|{}+')
        self._server_emit('A|A+')
        self.assertEqual(self.factory._state, constants.connection_state.OPEN)
    def test_too_many_auths(self):
        self.proto.makeConnection(self.tr)
        self.factory._state = constants.connection_state.CHALLENGING
        self._test('C|A+', 'A|REQ|{}+')

        self._server_emit('A|E+')
        self.assertEqual(self.factory._state, constants.connection_state.AWAITING_AUTHENTICATION)
        self.proto._send_auth_params()

        self._server_emit('A|E+')
        self.assertEqual(self.factory._state, constants.connection_state.AWAITING_AUTHENTICATION)
        self.proto._send_auth_params()

        self._server_emit('A|E|%s+' % constants.event.TOO_MANY_AUTH_ATTEMPTS)
        self.assertTrue(self.factory._too_many_auth_attempts)
    # def test_redirect(self):
    #     raise NotImplementedError
    #     # Still need to write this test.






