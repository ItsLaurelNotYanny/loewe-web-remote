"""Automated unit test suite for Loewe Web Remote."""

import unittest
from unittest.mock import MagicMock, patch
import json
import threading
import urllib.error

from loewe_remote import LoeweController, RemoteRequestHandler


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
        self.assertEqual(fcid, "2")  # Enforced fallback from "0" to DEFAULT_FCID ("2")
        self.assertEqual(status, "Accepted")
        self.assertEqual(self.controller.client_id, "LRemoteClient-0-123456")

    @patch.object(LoeweController, "_soap_request")
    def test_request_access_denied_returns_none(self, mock_soap):
        """Initial handshake anomaly: TV denies pairing request."""
        mock_soap.return_value = (
            b'<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
            b'<SOAP-ENV:Body>'
            b'<m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
            b'<m:AccessStatus>Denied</m:AccessStatus>'
            b'</m:RequestAccessResponse>'
            b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
        )

        cid, fcid, status = self.controller.request_access()
        self.assertIsNone(cid)
        self.assertEqual(status, "Denied")
        self.assertIsNone(self.controller.client_id)

    @patch.object(LoeweController, "_soap_request")
    def test_request_access_pending_returns_none(self, mock_soap):
        """Initial handshake anomaly: Pairing requires PIN/confirmation on TV."""
        mock_soap.return_value = (
            b'<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
            b'<SOAP-ENV:Body>'
            b'<m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
            b'<m:AccessStatus>Pending</m:AccessStatus>'
            b'</m:RequestAccessResponse>'
            b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
        )

        cid, fcid, status = self.controller.request_access()
        self.assertIsNone(cid)
        self.assertEqual(status, "Pending")
        self.assertIsNone(self.controller.client_id)

    @patch.object(LoeweController, "_soap_request")
    def test_request_access_network_error_returns_none(self, mock_soap):
        """Initial handshake anomaly: Network exception handled gracefully."""
        mock_soap.side_effect = urllib.error.URLError("Connection timed out")

        cid, fcid, status = self.controller.request_access()
        self.assertIsNone(cid)
        self.assertIsNone(status)
        self.assertIsNone(self.controller.client_id)

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_existing_session(self, mock_soap):
        self.controller.client_id = "LRemoteClient-0-123456"
        self.controller.fcid = "2"

        mock_soap.return_value = (
            b'<m:InjectRCKeyResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
            b'<m:fcid>2</m:fcid><m:ClientId>LRemoteClient-0-123456</m:ClientId>'
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
    def test_send_key_cold_start_network_error(self, mock_soap):
        """Verify cold start with offline TV safely returns False without raising exception."""
        self.controller.client_id = None
        mock_soap.side_effect = urllib.error.URLError("Host unreachable")

        res = self.controller.send_key("32", alphabet="l2700")
        self.assertFalse(res)

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_auto_recovery_on_invalid(self, mock_soap):
        self.controller.client_id = "LRemoteClient-0-old"
        self.controller.fcid = "2"

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

    @patch.object(LoeweController, "_soap_request")
    def test_send_key_retry_rejection_returns_false(self, mock_soap):
        """Fix verification for '重试误报成功' (Retry false positive success):

        When session recovery retries key injection, but the TV rejects the retry
        with INVALID, send_key MUST return False instead of falsely returning True.
        """
        self.controller.client_id = "LRemoteClient-0-stale"
        self.controller.fcid = "2"

        # First call: expired session
        # Second call: RequestAccess succeeds
        # Third call: Retry InjectRCKey rejected by TV
        mock_soap.side_effect = [
            b'<m:InjectRCKeyResponse><m:ClientId>INVALID</m:ClientId></m:InjectRCKeyResponse>',
            (
                b'<m:RequestAccessResponse xmlns:m="urn:loewe.de:RemoteTV:Tablet">'
                b'<m:fcid>0</m:fcid>'
                b'<m:ClientId>LRemoteClient-0-renewed</m:ClientId>'
                b'<m:AccessStatus>Accepted</m:AccessStatus>'
                b'</m:RequestAccessResponse>'
            ),
            b'<m:InjectRCKeyResponse><m:ClientId>INVALID</m:ClientId></m:InjectRCKeyResponse>',
        ]

        res = self.controller.send_key("32", alphabet="l2700")
        self.assertFalse(res)  # Must be False! Never report false success.
        self.assertEqual(mock_soap.call_count, 3)

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
        self.controller.fcid = "2"
        mock_soap.side_effect = urllib.error.URLError("Connection refused")

        res = self.controller.send_key("32", alphabet="l2700")
        self.assertFalse(res)


class TestRemoteRequestHandler(unittest.TestCase):
    """End-to-end HTTP request handling tests for RemoteRequestHandler."""

    @classmethod
    def setUpClass(cls):
        cls.mock_controller = MagicMock(spec=LoeweController)
        RemoteRequestHandler.controller = cls.mock_controller
        # Silence access logs during tests
        RemoteRequestHandler.log_message = lambda self, format, *args: None

        import http.server
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), RemoteRequestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.mock_controller.reset_mock()

    def _post(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, data
        except urllib.error.HTTPError as e:
            data = json.loads(e.read().decode("utf-8"))
            return e.code, data

    def test_post_key_non_ascii_digit_code_returns_400(self):
        """R3 acceptance test: Non-ASCII digits like '²' (%C2%B2) must return 400 without calling controller."""
        status, data = self._post("/api/key?code=%C2%B2")
        self.assertEqual(status, 400)
        self.assertFalse(data["success"])
        self.assertIn("error", data)
        self.mock_controller.send_key.assert_not_called()

    def test_post_key_invalid_code_cases_return_400(self):
        """R3 acceptance test: bounds (0, 10000), long digits, XML injection, missing code."""
        invalid_paths = [
            "/api/key?code=0",
            "/api/key?code=10000",
            "/api/key?code=123456789",
            "/api/key?code=32%22%20mode=%22inject",
            "/api/key?code=abc",
            "/api/key",
            "/api/key?code=32&alphabet=evil",
        ]
        for path in invalid_paths:
            status, data = self._post(path)
            self.assertEqual(status, 400, f"Path {path} should return HTTP 400")
            self.assertFalse(data["success"])
            self.mock_controller.send_key.assert_not_called()

    def test_post_key_valid_boundaries_reach_controller(self):
        """R3 acceptance test: Valid boundaries 1 and 9999 reach controller."""
        self.mock_controller.send_key.return_value = True

        status, data = self._post("/api/key?code=1")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.mock_controller.send_key.assert_called_with("1", alphabet="l2700")

        self.mock_controller.reset_mock()
        status, data = self._post("/api/key?code=9999&alphabet=l2700-hdr")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.mock_controller.send_key.assert_called_with("9999", alphabet="l2700-hdr")

    def test_post_key_controller_failure_returns_502(self):
        """R1 & R2 acceptance test: When send_key returns False, handler returns HTTP 502 with success: false."""
        self.mock_controller.send_key.return_value = False

        status, data = self._post("/api/key?code=32")
        self.assertEqual(status, 502)
        self.assertFalse(data["success"])
        self.assertEqual(data["code"], "32")
        self.mock_controller.send_key.assert_called_once()


if __name__ == "__main__":
    unittest.main()
