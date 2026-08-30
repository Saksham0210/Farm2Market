import math
import hashlib
from typing import Optional


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_distance_km(
    lat1: Optional[float], lon1: Optional[float],
    lat2: Optional[float], lon2: Optional[float],
    fallback_seed_a: str = "", fallback_seed_b: str = "",
) -> float:
    """Use real coordinates when both points have them; otherwise derive a
    stable pseudo-distance from the location text so the demo still works
    without a geocoding API key."""
    if None not in (lat1, lon1, lat2, lon2):
        return round(haversine_km(lat1, lon1, lat2, lon2), 2)

    combined = f"{fallback_seed_a}|{fallback_seed_b}".lower().strip()
    digest = hashlib.md5(combined.encode()).hexdigest()
    # Map to a plausible 2-40 km local-delivery range
    pseudo_km = 2 + (int(digest[:6], 16) % 3800) / 100
    return round(pseudo_km, 2)


def area_key(location_text: str) -> str:
    """Normalize a free-text location into a coarse area key used to group
    individual orders for batching (e.g. by city/locality)."""
    return location_text.strip().lower().split(",")[0]
