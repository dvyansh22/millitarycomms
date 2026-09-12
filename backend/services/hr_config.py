import json
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "heart_rate_sources.json")


def _normalize_url(value):
    url = str(value or "").strip()
    if not url:
        return None

    if "://" not in url:
        url = f"http://{url}"

    if "/" not in url.split("://", 1)[1]:
        url = f"{url}/"

    return url


def _load_sources_from_env():
    raw_sources = os.getenv("HEART_RATE_SOURCES", "").strip()
    if not raw_sources:
        return {}

    sources = {}
    for item in raw_sources.split(","):
        node_id, separator, url = item.partition("=")
        if not separator:
            continue

        normalized_node_id = node_id.strip()
        normalized_url = _normalize_url(url)
        if normalized_node_id and normalized_url:
            sources[normalized_node_id] = normalized_url

    return sources


def _load_sources_from_file():
    config_path = os.getenv("HEART_RATE_SOURCES_FILE", DEFAULT_CONFIG_PATH).strip() or DEFAULT_CONFIG_PATH
    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            payload = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    sources = {}
    for node_id, url in payload.items():
        normalized_node_id = str(node_id).strip()
        normalized_url = _normalize_url(url)
        if normalized_node_id and normalized_url:
            sources[normalized_node_id] = normalized_url

    return sources


def load_heart_rate_sources():
    env_sources = _load_sources_from_env()
    if env_sources:
        return env_sources

    return _load_sources_from_file()


def has_heart_rate_source(node_id):
    return str(node_id or "").strip() in load_heart_rate_sources()
