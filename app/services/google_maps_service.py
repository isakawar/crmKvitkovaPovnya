import logging

import requests

logger = logging.getLogger(__name__)

_DIRECTIONS_URL = 'https://maps.googleapis.com/maps/api/directions/json'


def get_route_distance_km(addresses: list, api_key: str) -> float | None:
    """
    Call Google Maps Directions API for a list of addresses in route order.
    Returns total road distance in km, or None on any error (caller falls back to OSRM value).
    """
    if not api_key or len(addresses) < 2:
        return None

    params = {
        'origin': addresses[0],
        'destination': addresses[-1],
        'mode': 'driving',
        'language': 'uk',
        'key': api_key,
    }
    middle = addresses[1:-1]
    if middle:
        params['waypoints'] = '|'.join(middle)

    try:
        resp = requests.get(_DIRECTIONS_URL, params=params, timeout=10)
        data = resp.json()
        if data.get('status') != 'OK':
            logger.warning('Google Maps Directions API returned status=%s', data.get('status'))
            return None
        legs = data['routes'][0]['legs']
        total_m = sum(leg['distance']['value'] for leg in legs)
        return round(total_m / 1000, 1)
    except Exception as exc:
        logger.warning('Google Maps distance calculation failed: %s', exc)
        return None
