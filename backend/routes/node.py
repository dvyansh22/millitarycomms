from flask import Blueprint, jsonify, request
from services.store import get_dashboard, get_nodes, ingest_data

bp = Blueprint('node', __name__)

@bp.route('/nodes')
def nodes():
    return jsonify(get_nodes())


@bp.route('/dashboard')
def dashboard():
    return jsonify(get_dashboard())


@bp.route('/data', methods=['POST'])
@bp.route('/esp-data', methods=['POST'])
def receive_data():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "ok": False,
            "error": "Send JSON with Content-Type: application/json."
        }), 400

    try:
        stored_record = ingest_data(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({
        "ok": True,
        "id": stored_record["id"]
    })
