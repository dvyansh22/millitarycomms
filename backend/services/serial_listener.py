import json
import logging
import os
import time
from threading import Lock, Thread

try:
    import serial
    from serial import SerialException
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - optional dependency at runtime
    serial = None
    SerialException = Exception
    list_ports = None

logger = logging.getLogger(__name__)

DEFAULT_BAUD_RATE = int(os.getenv("SERIAL_BAUD_RATE", "9600"))
RECONNECT_DELAY_SECONDS = float(os.getenv("SERIAL_RECONNECT_DELAY", "2"))
DEDUPLICATE_WINDOW_SECONDS = float(os.getenv("SERIAL_DEDUPE_WINDOW", "1.5"))
KNOWN_PORT_PREFIXES = ("/dev/ttyUSB", "/dev/ttyACM", "/dev/cu.usb", "COM")

_recent_payloads = {}
_recent_payloads_lock = Lock()
_serial_thread_started = False
_serial_thread_lock = Lock()


def _serial_ingest_enabled():
    value = os.getenv("ENABLE_SERIAL_INGEST", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _iter_json_objects(text):
    depth = 0
    start_index = None
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
            continue

        if char == "}" and depth:
            depth -= 1
            if depth == 0 and start_index is not None:
                yield text[start_index:index + 1]
                start_index = None


def _payload_signature(payload):
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _is_duplicate_payload(payload):
    signature = _payload_signature(payload)
    if signature is None:
        return False

    now = time.monotonic()
    with _recent_payloads_lock:
        expired = [
            key for key, seen_at in _recent_payloads.items()
            if now - seen_at > DEDUPLICATE_WINDOW_SECONDS
        ]
        for key in expired:
            del _recent_payloads[key]

        previous_seen_at = _recent_payloads.get(signature)
        _recent_payloads[signature] = now

    return previous_seen_at is not None and now - previous_seen_at <= DEDUPLICATE_WINDOW_SECONDS


def _discover_serial_port():
    if list_ports is None:
        return None

    candidates = []
    for port in list_ports.comports():
        details = " ".join(
            value for value in (
                port.device,
                port.description,
                getattr(port, "manufacturer", None),
                getattr(port, "product", None),
            )
            if value
        ).lower()

        score = 0
        if port.device.startswith(KNOWN_PORT_PREFIXES):
            score += 4
        if "usb" in details:
            score += 2
        if "serial" in details or "uart" in details:
            score += 2
        if any(tag in details for tag in ("arduino", "cp210", "wch", "ftdi", "silicon labs", "ch340")):
            score += 1

        if score:
            candidates.append((score, port.device))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1]


def _resolve_serial_port():
    configured_port = os.getenv("SERIAL_PORT", "").strip()
    if configured_port and configured_port.lower() != "auto":
        return configured_port

    return _discover_serial_port()


def _consume_serial_line(line, ingest_callback):
    for fragment in _iter_json_objects(line):
        try:
            payload = json.loads(fragment)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        if _is_duplicate_payload(payload):
            continue

        try:
            ingest_callback(payload)
        except ValueError as exc:
            logger.warning("Skipping invalid serial payload: %s", exc)


def _run_serial_ingest(ingest_callback):
    missing_port_logged = False

    while True:
        serial_port = _resolve_serial_port()
        if not serial_port:
            if not missing_port_logged:
                logger.info("Waiting for ESP serial port. Set SERIAL_PORT to override auto-detection.")
                missing_port_logged = True
            time.sleep(RECONNECT_DELAY_SECONDS)
            continue

        missing_port_logged = False

        try:
            with serial.Serial(serial_port, DEFAULT_BAUD_RATE, timeout=1) as serial_handle:
                logger.info(
                    "Serial ingest connected to %s at %s baud.",
                    serial_port,
                    DEFAULT_BAUD_RATE,
                )

                while True:
                    raw_line = serial_handle.readline()
                    if not raw_line:
                        continue

                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if line:
                        _consume_serial_line(line, ingest_callback)

        except SerialException as exc:
            logger.warning("Serial ingest disconnected from %s: %s", serial_port, exc)
        except OSError as exc:
            logger.warning("Serial ingest error on %s: %s", serial_port, exc)

        time.sleep(RECONNECT_DELAY_SECONDS)


def start_serial_ingest(ingest_callback):
    global _serial_thread_started

    if not _serial_ingest_enabled():
        logger.info("Serial ingest disabled by ENABLE_SERIAL_INGEST.")
        return False

    if serial is None:
        logger.warning("pyserial is not installed. Serial ingest is unavailable.")
        return False

    with _serial_thread_lock:
        if _serial_thread_started:
            return True

        thread = Thread(
            target=_run_serial_ingest,
            args=(ingest_callback,),
            daemon=True,
            name="serial-ingest",
        )
        thread.start()
        _serial_thread_started = True

    return True
