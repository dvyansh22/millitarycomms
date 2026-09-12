import os
import threading
import time
import logging

from flask import Flask, send_from_directory
from flask_cors import CORS

from routes.logs import bp as log_bp
from routes.node import bp as node_bp
from routes.simulate import bp as simulate_bp
from routes.simulate import generate_data
from services.heart_rate_poller import start_heart_rate_poller
from routes.threats import bp as threat_bp
from routes.vitals import bp as vitals_bp
from services.serial_listener import start_serial_ingest
from services.store import ingest_data, update_heart_rate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app.register_blueprint(node_bp)
app.register_blueprint(log_bp)
app.register_blueprint(threat_bp)
app.register_blueprint(vitals_bp)
app.register_blueprint(simulate_bp)


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/assets/<path:filename>')
def frontend_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), filename)


@app.route('/components/<path:filename>')
def frontend_components(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'components'), filename)


def auto_simulate():
    while True:
        data = generate_data()
        ingest_data(data)
        time.sleep(3)


if os.getenv('ENABLE_SIMULATOR', '').lower() == 'true':
    threading.Thread(target=auto_simulate, daemon=True).start()

start_serial_ingest(ingest_data)
start_heart_rate_poller(update_heart_rate)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
