from flask import Blueprint, jsonify
import random, time

bp = Blueprint('simulate', __name__)

def generate_data():
    enemy_count = random.randint(0, 3)
    base_lat = 12.97230 + random.uniform(-0.0015, 0.0015)
    base_lon = 79.16850 + random.uniform(-0.0015, 0.0015)

    return {
        "id": f"S{random.randint(1,3)}",
        "timestamp": int(time.time()),
        "lat": round(base_lat, 5),
        "lon": round(base_lon, 5),
        "hr": random.randint(70, 120),
        "cmd": random.choice([
            "NULL",
            "enemy ahead need backup",
            "hold position",
            "move east 20m",
        ]),
        "en": [
            {
                "i": index + 1,
                "lat": round(base_lat + random.uniform(-0.0004, 0.0004), 5),
                "lon": round(base_lon + random.uniform(-0.0004, 0.0004), 5),
            }
            for index in range(enemy_count)
        ],
    }

@bp.route('/simulate-once')
def simulate_once():
    return jsonify(generate_data())
