"""Helpers for the Google-Places address coordinates carried on
subscription / order / delivery records."""

COORD_FIELDS = ('latitude', 'longitude', 'google_place_id', 'formatted_address')


def _parse_coord(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num == 0:
        return None
    return num


def coords_from_form(form, is_pickup=False):
    """Extract the 4 Google-Places fields from a submitted form.

    Returns a dict ready to splat into an ``Order`` / ``Subscription``
    constructor. For pickup orders coordinates are irrelevant → all None.
    """
    if is_pickup:
        return {f: None for f in COORD_FIELDS}
    return {
        'latitude': _parse_coord(form.get('latitude')),
        'longitude': _parse_coord(form.get('longitude')),
        'google_place_id': (form.get('google_place_id') or '').strip() or None,
        'formatted_address': (form.get('formatted_address') or '').strip() or None,
    }


def copy_coords(source, is_pickup=False):
    """Copy the 4 coordinate fields off a parent record (Subscription→Order,
    Order→Delivery). ``is_pickup`` blanks them."""
    if is_pickup:
        return {f: None for f in COORD_FIELDS}
    return {f: getattr(source, f, None) for f in COORD_FIELDS}
