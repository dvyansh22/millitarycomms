from flask import Blueprint, jsonify
from services.store import get_logs

bp = Blueprint('logs', __name__)

@bp.route('/logs')
def logs():
    return jsonify(get_logs())