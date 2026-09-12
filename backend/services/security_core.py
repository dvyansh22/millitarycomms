import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.getenv("CITADEL_DB_PATH", os.path.join(BASE_DIR, "citadel.db"))
MAX_PACKET_BYTES = 4096
MAX_CLOCK_SKEW = int(os.getenv("CITADEL_CLOCK_SKEW", "120"))
VALIDATORS = ("VAL-A", "VAL-B", "VAL-C")
ALLOWED_TYPES = {"telemetry", "command", "threat", "vitals"}


def _master_key():
    raw = os.getenv("CITADEL_MASTER_KEY", "citadel-development-master-key-change-me")
    return hashlib.sha256(raw.encode()).digest()


def _seal(value):
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(_master_key()).encrypt(nonce, value.encode(), b"citadel-device-secret")
    return base64.b64encode(nonce + encrypted).decode()


def _unseal(value):
    raw = base64.b64decode(value)
    return AESGCM(_master_key()).decrypt(raw[:12], raw[12:], b"citadel-device-secret").decode()


@contextmanager
def connection():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL,
          failed_logins INTEGER DEFAULT 0, locked_until INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS devices (
          device_id TEXT PRIMARY KEY, status TEXT NOT NULL,
          secret_box TEXT NOT NULL, fingerprint TEXT NOT NULL,
          allowed_types TEXT NOT NULL, last_contact INTEGER,
          last_sequence INTEGER DEFAULT 0, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS nonces (
          device_id TEXT NOT NULL, nonce TEXT NOT NULL, seen_at INTEGER NOT NULL,
          PRIMARY KEY(device_id, nonce)
        );
        CREATE TABLE IF NOT EXISTS security_events (
          event_id TEXT PRIMARY KEY, timestamp INTEGER NOT NULL,
          event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
          decision TEXT NOT NULL, reason_code TEXT NOT NULL,
          payload_digest TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS blocks (
          block_index INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
          timestamp INTEGER NOT NULL, event_type TEXT NOT NULL,
          actor_id TEXT NOT NULL, decision TEXT NOT NULL,
          reason_code TEXT NOT NULL, payload_digest TEXT NOT NULL,
          previous_hash TEXT NOT NULL, current_hash TEXT NOT NULL,
          state TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS validator_votes (
          block_index INTEGER NOT NULL, validator_id TEXT NOT NULL,
          signature TEXT NOT NULL, approved INTEGER NOT NULL,
          PRIMARY KEY(block_index, validator_id)
        );
        CREATE TABLE IF NOT EXISTS validator_state (
          validator_id TEXT PRIMARY KEY, online INTEGER NOT NULL DEFAULT 1,
          last_block INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS packet_results (
          id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER NOT NULL,
          device_id TEXT NOT NULL, sequence_number INTEGER,
          message_type TEXT, decision TEXT NOT NULL, reason_code TEXT NOT NULL,
          encrypted INTEGER NOT NULL DEFAULT 0, payload_digest TEXT NOT NULL
        );
        """)
        for validator in VALIDATORS:
            db.execute("INSERT OR IGNORE INTO validator_state(validator_id, online, last_block) VALUES (?,1,0)", (validator,))


def seed_demo():
    init_db()
    admin_password = os.getenv("CITADEL_ADMIN_PASSWORD", "CitadelDemo!2026")
    with connection() as db:
        db.execute("INSERT OR IGNORE INTO users(username,password_hash,role) VALUES (?,?,?)",
                   ("admin", generate_password_hash(admin_password), "ADMIN"))
        db.execute("INSERT OR IGNORE INTO users(username,password_hash,role) VALUES (?,?,?)",
                   ("operator", generate_password_hash("OperatorDemo!2026"), "SECURITY_OPERATOR"))
        db.execute("INSERT OR IGNORE INTO users(username,password_hash,role) VALUES (?,?,?)",
                   ("viewer", generate_password_hash("ViewerDemo!2026"), "VIEWER"))
        for device_id, status in (("S1", "TRUSTED"), ("S2", "TRUSTED"), ("S3", "PENDING")):
            secret = f"citadel-demo-{device_id.lower()}-secret"
            db.execute("""INSERT OR IGNORE INTO devices
              (device_id,status,secret_box,fingerprint,allowed_types,created_at)
              VALUES (?,?,?,?,?,?)""", (device_id, status, _seal(secret), hashlib.sha256(secret.encode()).hexdigest()[:16],
              json.dumps(sorted(ALLOWED_TYPES)), int(time.time())))


def authenticate_user(username, password):
    now = int(time.time())
    with connection() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user or user["locked_until"] > now or not check_password_hash(user["password_hash"], password):
            if user:
                failures = user["failed_logins"] + 1
                lock = now + 30 if failures >= 5 else 0
                db.execute("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?", (failures, lock, user["id"]))
            return None
        db.execute("UPDATE users SET failed_logins=0, locked_until=0 WHERE id=?", (user["id"],))
        return {"id": user["id"], "username": user["username"], "role": user["role"]}


def canonical_packet(packet):
    fields = {key: packet.get(key) for key in (
        "protocol_version", "device_id", "sequence_number", "timestamp",
        "message_type", "nonce", "encrypted_payload", "previous_event_hash")}
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign_packet(packet, secret):
    return hmac.new(secret.encode(), canonical_packet(packet), hashlib.sha256).hexdigest()


def build_demo_packet(device_id="S1", sequence_number=None, payload=None, message_type="telemetry"):
    with connection() as db:
        device = db.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
    if not device:
        secret = "unknown-device-secret"
        last_sequence = 0
    else:
        secret = _unseal(device["secret_box"])
        last_sequence = device["last_sequence"]
    clear_payload = payload or {"lat": 12.9723, "lon": 79.1685, "hr": 92, "cmd": "all clear", "en": []}
    nonce_bytes = secrets.token_bytes(12)
    encryption_key = hashlib.sha256((secret + ":encryption").encode()).digest()
    encrypted = AESGCM(encryption_key).encrypt(
        nonce_bytes, json.dumps(clear_payload, sort_keys=True, separators=(",", ":")).encode(), device_id.encode()
    )
    packet = {
        "protocol_version": 1,
        "device_id": device_id,
        "sequence_number": sequence_number if sequence_number is not None else last_sequence + 1,
        "timestamp": int(time.time()),
        "message_type": message_type,
        "nonce": base64.b64encode(nonce_bytes).decode(),
        "encrypted_payload": base64.b64encode(encrypted).decode(),
        "previous_event_hash": latest_hash(),
    }
    packet["authentication_tag"] = sign_packet(packet, secret)
    return packet


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _block_hash(block):
    return _digest({k: block[k] for k in (
        "block_index", "event_id", "timestamp", "event_type", "actor_id",
        "decision", "reason_code", "payload_digest", "previous_hash")})


def _validator_signature(validator, block_hash):
    key = hmac.new(_master_key(), f"validator:{validator}".encode(), hashlib.sha256).digest()
    return hmac.new(key, block_hash.encode(), hashlib.sha256).hexdigest()


def latest_hash():
    with connection() as db:
        row = db.execute("SELECT current_hash FROM blocks ORDER BY block_index DESC LIMIT 1").fetchone()
        return row["current_hash"] if row else "0" * 64


def record_event(event_type, actor_id, decision, reason_code, payload_digest=""):
    now, event_id = int(time.time()), str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO security_events VALUES (?,?,?,?,?,?,?)",
                   (event_id, now, event_type, actor_id, decision, reason_code, payload_digest))
        previous = db.execute("SELECT current_hash FROM blocks ORDER BY block_index DESC LIMIT 1").fetchone()
        index = db.execute("SELECT COALESCE(MAX(block_index),0)+1 AS n FROM blocks").fetchone()["n"]
        block = {"block_index": index, "event_id": event_id, "timestamp": now,
                 "event_type": event_type, "actor_id": actor_id, "decision": decision,
                 "reason_code": reason_code, "payload_digest": payload_digest,
                 "previous_hash": previous["current_hash"] if previous else "0" * 64}
        block["current_hash"] = _block_hash(block)
        online = db.execute("SELECT validator_id FROM validator_state WHERE online=1").fetchall()
        approvals = 0
        for row in online:
            validator = row["validator_id"]
            signature = _validator_signature(validator, block["current_hash"])
            db.execute("INSERT INTO validator_votes VALUES (?,?,?,1)", (index, validator, signature))
            db.execute("UPDATE validator_state SET last_block=? WHERE validator_id=?", (index, validator))
            approvals += 1
        state = "CONFIRMED" if approvals >= 2 else "PENDING"
        db.execute("INSERT INTO blocks VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            index, event_id, now, event_type, actor_id, decision, reason_code,
            payload_digest, block["previous_hash"], block["current_hash"], state))
    return {"event_id": event_id, "block_index": index, "state": state}


def _reject(device_id, sequence, message_type, reason, digest):
    now = int(time.time())
    with connection() as db:
        db.execute("""INSERT INTO packet_results(timestamp,device_id,sequence_number,message_type,decision,reason_code,payload_digest)
                      VALUES (?,?,?,?,?,?,?)""", (now, device_id or "UNKNOWN", sequence, message_type, "REJECTED", reason, digest))
    event_type = "REPLAY_BLOCKED" if reason in {"DUPLICATE_NONCE", "REPLAYED_SEQUENCE"} else "MESSAGE_REJECTED"
    record_event(event_type, device_id or "UNKNOWN", "REJECTED", reason, digest)
    return {"ok": False, "decision": "REJECTED", "reason_code": reason}


def verify_packet(packet):
    raw_size = len(json.dumps(packet).encode()) if isinstance(packet, dict) else MAX_PACKET_BYTES + 1
    if not isinstance(packet, dict) or raw_size > MAX_PACKET_BYTES:
        return _reject("UNKNOWN", None, None, "MALFORMED_PACKET", "")
    required = {"protocol_version", "device_id", "sequence_number", "timestamp", "message_type", "nonce", "encrypted_payload", "authentication_tag"}
    if set(packet) - (required | {"previous_event_hash"}) or not required.issubset(packet):
        return _reject(str(packet.get("device_id", "UNKNOWN")), packet.get("sequence_number"), packet.get("message_type"), "MALFORMED_PACKET", _digest(packet))
    device_id, digest = str(packet["device_id"]), hashlib.sha256(str(packet.get("encrypted_payload", "")).encode()).hexdigest()
    if packet.get("protocol_version") != 1 or packet.get("message_type") not in ALLOWED_TYPES:
        return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "INVALID_PAYLOAD", digest)
    with connection() as db:
        device = db.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
        if not device:
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "UNKNOWN_DEVICE", digest)
        if device["status"] != "TRUSTED":
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), f"DEVICE_{device['status']}", digest)
        if packet["message_type"] not in json.loads(device["allowed_types"]):
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "INSUFFICIENT_PERMISSION", digest)
        if not isinstance(packet["sequence_number"], int) or packet["sequence_number"] <= device["last_sequence"]:
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "REPLAYED_SEQUENCE", digest)
        # Clockless edge nodes may send 0 and rely on persistent sequence + nonce
        # freshness. A non-zero device clock must remain within the configured window.
        if not isinstance(packet["timestamp"], int) or (packet["timestamp"] != 0 and abs(int(time.time()) - packet["timestamp"]) > MAX_CLOCK_SKEW):
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "STALE_TIMESTAMP", digest)
        if not isinstance(packet["nonce"], str) or len(packet["nonce"]) < 16:
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "MALFORMED_PACKET", digest)
        if db.execute("SELECT 1 FROM nonces WHERE device_id=? AND nonce=?", (device_id, packet["nonce"])).fetchone():
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "DUPLICATE_NONCE", digest)
        device_secret = _unseal(device["secret_box"])
        expected = sign_packet(packet, device_secret)
        if not hmac.compare_digest(expected, str(packet["authentication_tag"])):
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "INVALID_AUTH_TAG", digest)
        try:
            nonce_bytes = base64.b64decode(packet["nonce"], validate=True)
            ciphertext = base64.b64decode(packet["encrypted_payload"], validate=True)
            encryption_key = hashlib.sha256((device_secret + ":encryption").encode()).digest()
            payload = json.loads(AESGCM(encryption_key).decrypt(nonce_bytes, ciphertext, device_id.encode()))
        except (ValueError, InvalidTag, json.JSONDecodeError):
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "DECRYPTION_FAILED", digest)
        lat, lon, hr = payload.get("lat"), payload.get("lon"), payload.get("hr")
        if (not isinstance(payload, dict) or len(str(payload.get("cmd", ""))) > 240 or
            not isinstance(payload.get("en", []), list) or len(payload.get("en", [])) > 10 or
            (lat is not None and (not isinstance(lat, (int, float)) or not -90 <= lat <= 90)) or
            (lon is not None and (not isinstance(lon, (int, float)) or not -180 <= lon <= 180)) or
            (hr is not None and (not isinstance(hr, (int, float)) or not 0 <= hr <= 250))):
            return _reject(device_id, packet.get("sequence_number"), packet.get("message_type"), "INVALID_PAYLOAD", digest)
        db.execute("INSERT INTO nonces VALUES (?,?,?)", (device_id, packet["nonce"], int(time.time())))
        db.execute("UPDATE devices SET last_sequence=?,last_contact=? WHERE device_id=?", (packet["sequence_number"], int(time.time()), device_id))
        db.execute("DELETE FROM nonces WHERE seen_at < ?", (int(time.time()) - 86400,))
        db.execute("""INSERT INTO packet_results(timestamp,device_id,sequence_number,message_type,decision,reason_code,encrypted,payload_digest)
                      VALUES (?,?,?,?,?,?,?,?)""", (int(time.time()), device_id, packet["sequence_number"], packet["message_type"], "ACCEPTED", "VERIFIED", 1, digest))
    ledger = record_event("MESSAGE_ACCEPTED", device_id, "ACCEPTED", "VERIFIED", digest)
    return {"ok": True, "decision": "ACCEPTED", "reason_code": "VERIFIED", "payload": payload,
            "device_id": device_id, "sequence_number": packet["sequence_number"], "ledger": ledger}


def list_devices():
    with connection() as db:
        return [dict(row) | {"allowed_types": json.loads(row["allowed_types"])} for row in db.execute(
            "SELECT device_id,status,fingerprint,allowed_types,last_contact,last_sequence,created_at FROM devices ORDER BY device_id")]


def set_device_status(device_id, status, actor):
    if status not in {"TRUSTED", "REVOKED", "PENDING"}:
        raise ValueError("invalid status")
    with connection() as db:
        changed = db.execute("UPDATE devices SET status=? WHERE device_id=?", (status, device_id)).rowcount
    if not changed:
        raise ValueError("device not found")
    record_event(f"DEVICE_{'APPROVED' if status == 'TRUSTED' else status}", actor, "ACCEPTED", device_id)


def enroll_device(device_id, actor, allowed_types=None):
    device_id = str(device_id).strip().upper()
    if not device_id or len(device_id) > 32 or not all(c.isalnum() or c in "-_" for c in device_id):
        raise ValueError("invalid device id")
    secret = secrets.token_urlsafe(32)
    allowed = sorted(set(allowed_types or ALLOWED_TYPES) & ALLOWED_TYPES)
    with connection() as db:
        db.execute("""INSERT INTO devices(device_id,status,secret_box,fingerprint,allowed_types,created_at)
                      VALUES (?,?,?,?,?,?)""", (device_id, "PENDING", _seal(secret),
                      hashlib.sha256(secret.encode()).hexdigest()[:16], json.dumps(allowed), int(time.time())))
    record_event("DEVICE_ENROLLED", actor, "ACCEPTED", device_id)
    return {"device_id": device_id, "status": "PENDING", "provisioning_secret": secret}


def reset_sequence(device_id, actor):
    with connection() as db:
        changed = db.execute("UPDATE devices SET last_sequence=0 WHERE device_id=?", (device_id,)).rowcount
        db.execute("DELETE FROM nonces WHERE device_id=?", (device_id,))
    if not changed:
        raise ValueError("device not found")
    record_event("SEQUENCE_RESET", actor, "ACCEPTED", device_id)


def verify_ledger():
    issues, previous = [], "0" * 64
    with connection() as db:
        blocks = db.execute("SELECT * FROM blocks ORDER BY block_index").fetchall()
        for block in blocks:
            data = dict(block)
            if data["previous_hash"] != previous or _block_hash(data) != data["current_hash"]:
                issues.append(f"block {data['block_index']} hash mismatch")
            votes = db.execute("SELECT * FROM validator_votes WHERE block_index=?", (data["block_index"],)).fetchall()
            valid_votes = sum(hmac.compare_digest(v["signature"], _validator_signature(v["validator_id"], data["current_hash"])) for v in votes)
            if data["state"] == "CONFIRMED" and valid_votes < 2:
                issues.append(f"block {data['block_index']} lacks quorum")
            previous = data["current_hash"]
    return {"valid": not issues, "issues": issues, "blocks": len(blocks)}


def security_dashboard():
    with connection() as db:
        device_counts = {r["status"]: r["n"] for r in db.execute("SELECT status,COUNT(*) n FROM devices GROUP BY status")}
        packet_counts = {r["decision"]: r["n"] for r in db.execute("SELECT decision,COUNT(*) n FROM packet_results GROUP BY decision")}
        replays = db.execute("SELECT COUNT(*) n FROM packet_results WHERE reason_code IN ('REPLAYED_SEQUENCE','DUPLICATE_NONCE')").fetchone()["n"]
        events = [dict(r) for r in db.execute("SELECT * FROM security_events ORDER BY timestamp DESC LIMIT 40")]
        blocks = []
        for row in db.execute("SELECT * FROM blocks ORDER BY block_index DESC LIMIT 20"):
            item = dict(row)
            item["approvals"] = db.execute("SELECT COUNT(*) n FROM validator_votes WHERE block_index=? AND approved=1", (row["block_index"],)).fetchone()["n"]
            blocks.append(item)
        validators = [dict(r) for r in db.execute("SELECT * FROM validator_state ORDER BY validator_id")]
        packets = [dict(r) for r in db.execute("SELECT * FROM packet_results ORDER BY id DESC LIMIT 30")]
    verification = verify_ledger()
    return {"summary": {"trusted": device_counts.get("TRUSTED", 0), "pending": device_counts.get("PENDING", 0),
                         "revoked": device_counts.get("REVOKED", 0), "accepted": packet_counts.get("ACCEPTED", 0),
                         "rejected": packet_counts.get("REJECTED", 0), "replays": replays,
                         "ledger": "VERIFIED" if verification["valid"] else "CONFLICTED"},
            "devices": list_devices(), "events": events, "blocks": blocks, "validators": validators,
            "packets": packets, "verification": verification}


def toggle_validator(validator_id):
    with connection() as db:
        row = db.execute("SELECT online FROM validator_state WHERE validator_id=?", (validator_id,)).fetchone()
        if not row:
            raise ValueError("validator not found")
        online = 0 if row["online"] else 1
        latest = db.execute("SELECT COALESCE(MAX(block_index),0) n FROM blocks").fetchone()["n"]
        db.execute("UPDATE validator_state SET online=?,last_block=? WHERE validator_id=?", (online, latest if online else 0, validator_id))
    record_event("VALIDATOR_STATUS_CHANGED", validator_id, "ACCEPTED", "ONLINE" if online else "OFFLINE")
    return bool(online)


def tamper_latest_block():
    with connection() as db:
        row = db.execute("SELECT block_index FROM blocks ORDER BY block_index DESC LIMIT 1").fetchone()
        if not row:
            return False
        db.execute("UPDATE blocks SET reason_code='TAMPERED' WHERE block_index=?", (row["block_index"],))
    return True
