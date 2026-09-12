import secrets
import time
from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.security_core import (
    authenticate_user, build_demo_packet, enroll_device, list_devices, record_event, reset_sequence,
    security_dashboard, set_device_status, sign_packet, tamper_latest_block,
    toggle_validator, verify_packet,
)
from services.store import ingest_data

bp = Blueprint("security", __name__)
_login_attempts = {}
_ingest_attempts = {}


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get("user"):
                return jsonify({"ok": False, "error": "authentication required"}), 401
            if session.get("role") not in roles:
                record_event("ROLE_ACTION_DENIED", session.get("user", "UNKNOWN"), "REJECTED", "INSUFFICIENT_PERMISSION")
                return jsonify({"ok": False, "error": "insufficient permission"}), 403
            if int(time.time()) - session.get("last_seen", session.get("login_at", 0)) > 900:
                session.clear()
                return jsonify({"ok": False, "error": "session expired"}), 401
            session["last_seen"] = int(time.time())
            if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("X-CSRF-Token") != session.get("csrf"):
                return jsonify({"ok": False, "error": "invalid request token"}), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator


@bp.post("/api/auth/login")
def login():
    address = request.remote_addr or "local"
    attempts = [t for t in _login_attempts.get(address, []) if time.time() - t < 60]
    if len(attempts) >= 8:
        return jsonify({"ok": False, "error": "try again later"}), 429
    body = request.get_json(silent=True) or {}
    user = authenticate_user(str(body.get("username", "")), str(body.get("password", "")))
    if not user:
        attempts.append(time.time()); _login_attempts[address] = attempts
        return jsonify({"ok": False, "error": "invalid credentials"}), 401
    session.clear()
    session.update(user=user["username"], role=user["role"], csrf=secrets.token_urlsafe(24), login_at=int(time.time()))
    return jsonify({"ok": True, "user": user["username"], "role": user["role"], "csrf": session["csrf"]})


@bp.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/api/auth/me")
def me():
    if not session.get("user"):
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": session["user"], "role": session["role"], "csrf": session["csrf"]})


@bp.post("/api/secure-data")
def secure_data():
    address = request.remote_addr or "local"
    attempts = [t for t in _ingest_attempts.get(address, []) if time.time() - t < 60]
    if len(attempts) >= 120:
        return jsonify({"ok": False, "error": "rate limit exceeded"}), 429
    attempts.append(time.time()); _ingest_attempts[address] = attempts
    result = verify_packet(request.get_json(silent=True))
    if result["ok"]:
        ingest_data({"id": result["device_id"], **result["payload"], "timestamp": int(time.time())})
    return jsonify({k: v for k, v in result.items() if k != "payload"}), 200 if result["ok"] else 403


@bp.get("/api/security/dashboard")
@require_role("SECURITY_OPERATOR", "ADMIN")
def dashboard():
    return jsonify(security_dashboard())


@bp.get("/api/security/devices")
@require_role("SECURITY_OPERATOR", "ADMIN")
def devices():
    return jsonify(list_devices())


@bp.post("/api/security/devices")
@require_role("ADMIN")
def enroll():
    body = request.get_json(silent=True) or {}
    try:
        result = enroll_device(body.get("device_id"), session["user"], body.get("allowed_types"))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "invalid or duplicate device"}), 400
    return jsonify({"ok": True, **result}), 201


@bp.post("/api/security/devices/<device_id>/<action>")
@require_role("ADMIN")
def device_action(device_id, action):
    if action == "approve": set_device_status(device_id, "TRUSTED", session["user"])
    elif action == "revoke": set_device_status(device_id, "REVOKED", session["user"])
    elif action == "reset-sequence": reset_sequence(device_id, session["user"])
    else: return jsonify({"ok": False, "error": "unknown action"}), 404
    return jsonify({"ok": True})


@bp.post("/api/demo/<scenario>")
@require_role("ADMIN")
def demo(scenario):
    packet = build_demo_packet("S1")
    if scenario == "valid": pass
    elif scenario == "unknown": packet = build_demo_packet("INTRUDER")
    elif scenario == "tampered": packet["encrypted_payload"] = packet["encrypted_payload"][:-2] + "AA"
    elif scenario == "stale": packet["timestamp"] -= 1000; packet["authentication_tag"] = sign_packet(packet, "citadel-demo-s1-secret")
    elif scenario == "replay":
        first = verify_packet(packet)
        second = verify_packet(packet)
        if first.get("ok"): ingest_data({"id": first["device_id"], **first["payload"], "timestamp": int(time.time())})
        return jsonify({"scenario": scenario, "first": {k:v for k,v in first.items() if k != "payload"}, "result": second})
    elif scenario == "revoked":
        set_device_status("S1", "REVOKED", session["user"])
    elif scenario == "ledger-tamper":
        return jsonify({"scenario": scenario, "tampered": tamper_latest_block(), "message": "Latest audit block modified; verification now detects it."})
    elif scenario.startswith("validator-"):
        validator = scenario.replace("validator-", "").upper()
        return jsonify({"scenario": scenario, "online": toggle_validator(validator)})
    else: return jsonify({"ok": False, "error": "unknown scenario"}), 404
    result = verify_packet(packet)
    if scenario == "revoked": set_device_status("S1", "TRUSTED", session["user"])
    if result.get("ok"): ingest_data({"id": result["device_id"], **result["payload"], "timestamp": int(time.time())})
    return jsonify({"scenario": scenario, "result": {k:v for k,v in result.items() if k != "payload"}})
