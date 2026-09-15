from __future__ import annotations

from hashlib import sha1

ENTITY_TYPES = ["place", "person", "event", "concept"]


def entity_id(name: str) -> str:
    return "entity_" + sha1(name.encode("utf-8")).hexdigest()[:12]
