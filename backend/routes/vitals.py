from flask import Blueprint, jsonify
from services.store import get_vitals

bp = Blueprint('vitals', __name__)

@bp.route('/vitals')
def vitals():
    return jsonify(get_vitals())