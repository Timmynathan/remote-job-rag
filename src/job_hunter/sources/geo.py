from __future__ import annotations

WORLDWIDE_MARKERS = ("worldwide", "anywhere", "global", "nigeria", "africa")


def infer_nigeria_eligible_from_text(location_text: str | None, *, default_when_specific: bool | None) -> bool | None:
    """Classify a free-text location/geo-restriction field for Nigeria eligibility.

    `default_when_specific` controls what a named, non-worldwide location
    means: False when the field is genuinely a candidate-eligibility
    restriction (Remotive/Jobicy/RemoteOK/WWR), None when it's just a job's
    base location with no real geo-eligibility signal either way (Arbeitnow).
    """
    location = (location_text or "").strip().lower()
    if not location:
        return None
    if any(marker in location for marker in WORLDWIDE_MARKERS):
        return True
    return default_when_specific


def infer_nigeria_eligible_from_restrictions(restrictions: list[str] | None) -> bool | None:
    """Classify a structured list of location restrictions (Himalayas-style).

    An empty list means no restriction was specified - open worldwide.
    """
    if restrictions is None:
        return None
    if not restrictions:
        return True
    combined = " ".join(restrictions).lower()
    if any(marker in combined for marker in WORLDWIDE_MARKERS):
        return True
    return False
