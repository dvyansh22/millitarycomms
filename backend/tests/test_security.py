import os
import sys
import tempfile
import unittest

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["CITADEL_DB_PATH"] = TEST_DB
os.environ["ENABLE_SERIAL_INGEST"] = "false"
os.environ["CITADEL_MASTER_KEY"] = "test-master"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from services.security_core import (
    build_demo_packet, connection, set_device_status, tamper_latest_block,
    verify_ledger, verify_packet,
)
from services.store import get_dashboard


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()
        login = cls.client.post("/api/auth/login", json={"username": "admin", "password": "CitadelDemo!2026"})
        cls.csrf = login.json["csrf"]

    def setUp(self):
        with connection() as db:
            db.execute("DELETE FROM nonces")
            db.execute("UPDATE devices SET last_sequence=0,status=CASE WHEN device_id='S3' THEN 'PENDING' ELSE 'TRUSTED' END")

    def test_valid_packet_updates_operational_state(self):
        packet = build_demo_packet("S1", payload={"lat": 1, "lon": 2, "hr": 88, "cmd": "verified", "en": []})
        response = self.client.post("/api/secure-data", json=packet)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_dashboard()["nodes"][0]["cmd"], "verified")

    def test_tamper_unknown_replay_stale_and_pending_are_rejected(self):
        packet = build_demo_packet("S1")
        self.assertTrue(verify_packet(packet)["ok"])
        self.assertEqual(verify_packet(packet)["reason_code"], "REPLAYED_SEQUENCE")
        tampered = build_demo_packet("S1")
        tampered["encrypted_payload"] = tampered["encrypted_payload"][:-2] + "AA"
        self.assertEqual(verify_packet(tampered)["reason_code"], "INVALID_AUTH_TAG")
        self.assertEqual(verify_packet(build_demo_packet("INTRUDER"))["reason_code"], "UNKNOWN_DEVICE")
        stale = build_demo_packet("S1")
        stale["timestamp"] -= 999
        from services.security_core import sign_packet
        stale["authentication_tag"] = sign_packet(stale, "citadel-demo-s1-secret")
        self.assertEqual(verify_packet(stale)["reason_code"], "STALE_TIMESTAMP")
        self.assertEqual(verify_packet(build_demo_packet("S3"))["reason_code"], "DEVICE_PENDING")

    def test_revocation_and_role_access(self):
        set_device_status("S1", "REVOKED", "test")
        self.assertEqual(verify_packet(build_demo_packet("S1"))["reason_code"], "DEVICE_REVOKED")
        set_device_status("S1", "TRUSTED", "test")
        operator = app.test_client()
        login = operator.post("/api/auth/login", json={"username": "operator", "password": "OperatorDemo!2026"})
        denied = operator.post("/api/security/devices/S1/revoke", headers={"X-CSRF-Token": login.json["csrf"]})
        self.assertEqual(denied.status_code, 403)

    def test_ledger_detects_tampering(self):
        verify_packet(build_demo_packet("S2"))
        self.assertTrue(verify_ledger()["valid"])
        tamper_latest_block()
        self.assertFalse(verify_ledger()["valid"])

    def test_unsigned_legacy_ingestion_is_disabled(self):
        self.assertEqual(self.client.post("/esp-data", json={"id": "S1"}).status_code, 426)


if __name__ == "__main__":
    unittest.main()
