"""Transport modes, static routes, and Geoapify API lookup."""

import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_ROUTING_URL = "https://api.geoapify.com/v1/routing"
GEOAPIFY_API_KEY_ENV = "GEOAPIFY_API_KEY"
ENV_FILE = Path(__file__).with_name(".env")

TRANSPORT_MODES = ["bus", "train", "flight", "cab"]

ROUTES = {
    ("mumbai", "pune"): {
        "bus": {"time": "3.5 hrs", "fare": 250, "distance": "149 km"},
        "train": {"time": "3 hrs", "fare": 180, "distance": "149 km"},
        "flight": {"time": "1 hr", "fare": 4500, "distance": "119 km"},
        "cab": {"time": "2.5 hrs", "fare": 1200, "distance": "149 km"},
    },
    ("mumbai", "delhi"): {
        "bus": {"time": "24 hrs", "fare": 1500, "distance": "1,421 km"},
        "train": {"time": "16 hrs", "fare": 1200, "distance": "1,421 km"},
        "flight": {"time": "2 hrs", "fare": 5500, "distance": "1,148 km"},
        "cab": {"time": "20 hrs", "fare": 12000, "distance": "1,421 km"},
    },
    ("pune", "goa"): {
        "bus": {"time": "8 hrs", "fare": 500, "distance": "448 km"},
        "train": {"time": "6 hrs", "fare": 400, "distance": "448 km"},
        "flight": {"time": "1 hr", "fare": 3500, "distance": "357 km"},
        "cab": {"time": "7 hrs", "fare": 3000, "distance": "448 km"},
    },
}


def geoapify_enabled():
    """Return True when the API key is available."""
    return bool(get_geoapify_api_key())


def get_geoapify_api_key():
    """Read Geoapify API key from environment or local .env file."""
    api_key = os.getenv(GEOAPIFY_API_KEY_ENV)
    if api_key:
        return api_key.strip()

    return _read_env_file_key(GEOAPIFY_API_KEY_ENV)


def get_options(source, destination):
    """Return transport options from Geoapify API, then static fallback."""
    source = source.strip()
    destination = destination.strip()

    if geoapify_enabled():
        api_options = get_geoapify_options(source, destination)
        if api_options:
            return api_options

    return get_static_options(source, destination)


def get_static_options(source, destination):
    """Return static route options for beginner/demo usage."""
    key = (source.lower(), destination.lower())
    reverse_key = (destination.lower(), source.lower())

    if key in ROUTES:
        return ROUTES[key]
    if reverse_key in ROUTES:
        return ROUTES[reverse_key]
    return None


def get_geoapify_options(source, destination):
    """Build multi-mode options using Geoapify route distance and time."""
    start = _geocode_city(source)
    end = _geocode_city(destination)

    if not start or not end:
        return None

    route = _fetch_geoapify_route(start, end)
    if not route:
        return None

    distance_km = route["distance_meters"] / 1000
    cab_minutes = route["time_seconds"] / 60

    return {
        "bus": _make_estimated_option(
            distance_km,
            cab_minutes * 1.25,
            fare_per_km=3.5,
            minimum_fare=80,
            source="Estimated from Geoapify route",
        ),
        "train": _make_estimated_option(
            distance_km,
            max(cab_minutes * 0.85, distance_km / 70 * 60),
            fare_per_km=2.0,
            minimum_fare=50,
            source="Estimated from Geoapify route",
        ),
        "flight": _make_estimated_option(
            distance_km,
            max(150, (distance_km / 650 * 60) + 90),
            fare_per_km=5.0,
            minimum_fare=2500,
            source="Estimated from Geoapify route",
        ),
        "cab": _make_estimated_option(
            distance_km,
            cab_minutes,
            fare_per_km=14.0,
            minimum_fare=150,
            source="Geoapify Routing API",
        ),
    }


def _geocode_city(city):
    """Convert a city/address into latitude and longitude using Geoapify."""
    api_key = get_geoapify_api_key()
    if not api_key:
        return None

    params = {
        "text": city,
        "format": "json",
        "apiKey": api_key,
    }
    data = _get_json(f"{GEOAPIFY_GEOCODE_URL}?{urlencode(params)}")

    results = data.get("results", []) if data else []
    if not results:
        return None

    first = results[0]
    return {
        "lat": first["lat"],
        "lon": first["lon"],
    }


def _fetch_geoapify_route(start, end):
    """Fetch driving route details from Geoapify Routing API."""
    api_key = get_geoapify_api_key()
    if not api_key:
        return None

    waypoints = f"{start['lat']},{start['lon']}|{end['lat']},{end['lon']}"
    params = {
        "waypoints": waypoints,
        "mode": "drive",
        "apiKey": api_key,
    }
    data = _get_json(f"{GEOAPIFY_ROUTING_URL}?{urlencode(params)}")

    features = data.get("features", []) if data else []
    if not features:
        return None

    properties = features[0].get("properties", {})
    distance = properties.get("distance")
    travel_time = properties.get("time")

    if distance is None or travel_time is None:
        return None

    return {
        "distance_meters": distance,
        "time_seconds": travel_time,
    }


def _get_json(url):
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _make_estimated_option(distance_km, minutes, fare_per_km, minimum_fare, source):
    fare = max(minimum_fare, round(distance_km * fare_per_km))

    return {
        "time": _format_minutes(minutes),
        "fare": fare,
        "distance": _format_distance(distance_km),
        "source": source,
    }


def _format_distance(distance_km):
    return f"{round(distance_km):,} km"


def _format_minutes(minutes):
    total_minutes = max(1, round(minutes))
    hours = total_minutes // 60
    mins = total_minutes % 60

    if hours and mins:
        return f"{hours} hrs {mins} mins"
    if hours:
        return f"{hours} hrs"
    return f"{mins} mins"


def _read_env_file_key(name):
    """Read one KEY=value entry from .env without adding a dependency."""
    if not ENV_FILE.exists():
        return ""

    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    for line in lines:
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue

        key, value = clean_line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")

    return ""
