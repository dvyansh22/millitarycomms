import json
import logging
import os
import re
import time
from threading import Lock, Thread
from urllib import error, request

from services.hr_config import load_heart_rate_sources

logger = logging.getLogger(__name__)

HEART_RATE_PATTERN = re.compile(r"\bBPM\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
POLL_INTERVAL_SECONDS = float(os.getenv("HEART_RATE_POLL_INTERVAL", "1.5"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("HEART_RATE_TIMEOUT", "2"))

_poller_started = False
_poller_lock = Lock()


def _coerce_heart_rate(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_heart_rate(body, content_type=""):
    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return None

    if "json" in content_type.lower() or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            for key in ("hr", "bpm", "value"):
                heart_rate = _coerce_heart_rate(payload.get(key))
                if heart_rate is not None:
                    return heart_rate

    match = HEART_RATE_PATTERN.search(text)
    if match:
        return _coerce_heart_rate(match.group(1))

    return _coerce_heart_rate(text)


def _fetch_heart_rate(source_url):
    http_request = request.Request(source_url, headers={"User-Agent": "Makeathon-HR-Poller/1.0"})

    with request.urlopen(http_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()

    return _extract_heart_rate(body, content_type)


def _run_heart_rate_poller(update_heart_rate):
    missing_sources_logged = False

    while True:
        sources = load_heart_rate_sources()
        if not sources:
            if not missing_sources_logged:
                logger.info(
                    "No external heart-rate ESP sources configured. "
                    "Set HEART_RATE_SOURCES or edit backend/heart_rate_sources.json."
                )
                missing_sources_logged = True
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        missing_sources_logged = False

        for node_id, source_url in sources.items():
            try:
                heart_rate = _fetch_heart_rate(source_url)
            except (error.URLError, TimeoutError, OSError) as exc:
                logger.warning("Failed to fetch heart rate for %s from %s: %s", node_id, source_url, exc)
                continue

            if heart_rate is None:
                logger.warning("No BPM value found for %s at %s", node_id, source_url)
                continue

            update_heart_rate(node_id, heart_rate)

        time.sleep(POLL_INTERVAL_SECONDS)


def start_heart_rate_poller(update_heart_rate):
    global _poller_started

    with _poller_lock:
        if _poller_started:
            return True

        thread = Thread(
            target=_run_heart_rate_poller,
            args=(update_heart_rate,),
            daemon=True,
            name="heart-rate-poller",
        )
        thread.start()
        _poller_started = True

    return True
