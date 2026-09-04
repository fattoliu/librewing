from __future__ import annotations

import re

from .config import ServerProfile
from .share import parse_ss_url

SS_URL_RE = re.compile(r"ss://[^\s<>\"']+", re.IGNORECASE)


def extract_ss_urls(text: str) -> list[str]:
    """Extract distinct ss:// URLs from arbitrary clipboard text, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for match in SS_URL_RE.finditer(text or ""):
        value = match.group(0).rstrip(".,;)]}")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def profile_identity(profile: ServerProfile) -> tuple[object, ...]:
    """Identity used to avoid adding the exact same endpoint twice."""
    return (
        profile.server.lower(),
        int(profile.server_port),
        profile.method.lower(),
        profile.password,
        profile.plugin,
        profile.plugin_opts,
    )


def import_profiles_from_text(text: str, existing: list[ServerProfile] | None = None) -> list[ServerProfile]:
    existing_keys = {profile_identity(p) for p in (existing or [])}
    imported: list[ServerProfile] = []
    for url in extract_ss_urls(text):
        try:
            profile = parse_ss_url(url)
        except (TypeError, ValueError, UnicodeError):
            continue
        key = profile_identity(profile)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        imported.append(profile)
    return imported
