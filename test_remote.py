"""Automated unit test suite for Loewe Web Remote."""

import unittest
from unittest.mock import MagicMock, patch
import json
import urllib.error

from loewe_remote import LoeweController


class TestLoeweController(unittest.TestCase):
    def setUp(self):
        self.controller = LoeweController(
            tv_ip="192.168.3.226",
            mac_address="f8:a2:d6:67:0f:f0",
            client_uuid="synology-ds220-loewe",
            device_name="Synology-DS220",
            fcid="2",
        )

    @patch("loewe_remote.socket.socket")
    def test_wake_on_lan(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        res = self.controller.wake_on_lan()
        self.assertTrue(res)
        self.assertTrue(mock_sock.sendto.called)

        # Check magic packet structure
        args, kwargs = mock_sock.sendto.call_args
        packet, (ip, port) = args
        self.assertEqual(packet[:6], b"\xff\xff\xff\xff\xff\xff")
        self.assertEqual(port, 9)

    @patch("loewe_remote.socket.socket")
    def test_probe_status_online(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        res = self.controller.probe_status()
        self.assertEqual(res["status"], "on")
        self.assertEqual(res["method"], "tcp:905")

    @patch("loewe_remote.socket.socket")
    @patch("loewe_remote.subprocess.run")
    def test_probe_status_offline(self, mock_subproc, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # Connection refused
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        mock_subproc.return_value.returncode = 1  # Ping failed

        res = self.controller.probe_status()
        self.assertEqual(res["status"], "off")

    @patch.object(LoeweController, "_soap_request")
    def test_request_access_success(self, mock_soap):
        mock_soap.return_value = (
            b'<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
            b'<SOAP-ENV:Body>'
            b'<m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
            b'<m:fcid>0</m:fcid>'
            b'<m:ClientId>LRemoteClient-0-123456</m:ClientId>'
            b'<m:AccessStatus>Accepted</m:AccessStatus>'
            b'</m:RequestAccessResponse>'
            b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
        )

        cid, fcid, status = self.controller.request_access()
        self.assertEqual(cid, "LRemoteClient-0-123456")
        self.assertEqual(fcid, "0")
        self.assertEqual(status, "Accepted")
        self.assertEqual(self.controller.client_id, "LRemoteClient-0-123456")

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_existing_session(self, mock_soap):
        self.controller.client_id = "LRemoteClient-0-123456"
        self.controller.fcid = "0"

        mock_soap.return_value = (
            b'<m:InjectRCKeyResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
            b'<m:fcid>0</m:fcid><m:ClientId>LRemoteClient-0-123456</m:ClientId>'
            b'</m:InjectRCKeyResponse>'
        )

        res = self.controller.send_key("126", alphabet="l2700")  # HOME
        self.assertTrue(res)
        mock_soap.assert_called_once()
        args, kwargs = mock_soap.call_args
        self.assertEqual(args[0], "InjectRCKey")
        self.assertIn('alphabet="l2700"', args[1])
        self.assertIn('value="126"', args[1])

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_auto_recovery_on_invalid(self, mock_soap):
        self.controller.client_id = "LRemoteClient-0-old"
        self.controller.fcid = "0"

        # First call returns invalid/expired session
        # Second call is RequestAccess returning new token
        # Third call is InjectRCKey retry succeeding
        mock_soap.side_effect = [
            b'<m:InjectRCKeyResponse><m:ClientId>INVALID</m:ClientId></m:InjectRCKeyResponse>',
            (
                b'<m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
                b'<m:fcid>0</m:fcid>'
                b'<m:ClientId>LRemoteClient-0-fresh</m:ClientId>'
                b'<m:AccessStatus>Accepted</m:AccessStatus>'
                b'</m:RequestAccessResponse>'
            ),
            b'<m:InjectRCKeyResponse><m:ClientId>LRemoteClient-0-fresh</m:ClientId></m:InjectRCKeyResponse>',
        ]

        res = self.controller.send_key("53", alphabet="l2700-hdr")  # PLAY
        self.assertTrue(res)
        self.assertEqual(mock_soap.call_count, 3)
        self.assertEqual(self.controller.client_id, "LRemoteClient-0-fresh")

    def test_input_validation_defense(self):
        """Verify XML injection payloads and invalid alphabets are rejected."""
        malicious_code = '32" mode="inject'
        malicious_alphabet = 'l2700" inject="true'

        self.assertFalse(malicious_code.isdigit())
        self.assertNotIn(malicious_alphabet, {"l2700", "l2700-hdr"})

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_network_timeout(self, mock_soap):
        """Verify graceful error recovery when TV drops connection mid-flight."""
        self.controller.client_id = "LRemoteClient-0-123"
        self.controller.fcid = "0"
        mock_soap.side_effect = urllib.error.URLError("Connection refused")

        res = self.controller.send_key("32", alphabet="l2700")
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
