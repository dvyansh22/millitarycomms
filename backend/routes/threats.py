from flask import Blueprint, jsonify
from services.store import get_threats

bp = Blueprint('threats', __name__)

@bp.route('/threats')
def threats():
    return jsonify(get_threats())
