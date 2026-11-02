"""Runtime settings, read from environment variables.

Everything defaults to the most restrictive value: with no allowed users or
trusted proxies configured, every request is refused.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _networks(value: str | None) -> list[Network]:
    return [ipaddress.ip_network(part, strict=False) for part in _csv(value)]


@dataclass(frozen=True)
class Settings:
    # Authelia usernames allowed to use the harness.
    allowed_users: frozenset[str] = frozenset()
    # Optional Authelia group a user must also belong to.
    required_group: str | None = None
    # IPs/CIDRs of the reverse proxy (Traefik). Identity headers are only
    # trusted on connections that come directly from one of these.
    trusted_proxies: list[Network] = field(default_factory=list)
    db_path: Path = Path("/data/harness.db")
    secrets_dir: Path = Path("/run/secrets")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            allowed_users=frozenset(u.lower() for u in _csv(os.getenv("HARNESS_ALLOWED_USERS"))),
            required_group=os.getenv("HARNESS_REQUIRED_GROUP") or None,
            trusted_proxies=_networks(os.getenv("HARNESS_TRUSTED_PROXIES")),
            db_path=Path(os.getenv("HARNESS_DB_PATH", "/data/harness.db")),
            secrets_dir=Path(os.getenv("HARNESS_SECRETS_DIR", "/run/secrets")),
        )
