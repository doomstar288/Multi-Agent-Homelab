"""Identity from Authelia, delivered by Traefik forward-auth.

Traefik asks Authelia to authenticate every request and copies the verified
identity into Remote-User / Remote-Groups / Remote-Email headers. Those headers
are only meaningful when the connection really came from Traefik, so we check
the direct peer address against HARNESS_TRUSTED_PROXIES and refuse anything else.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from .config import Settings

log = logging.getLogger("harness.auth")


@dataclass(frozen=True)
class User:
    name: str
    groups: tuple[str, ...]
    email: str | None


def peer_is_trusted(host: str | None, settings: Settings) -> bool:
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in settings.trusted_proxies)


def authenticate(request: Request, settings: Settings) -> User:
    peer = request.client.host if request.client else None
    if not peer_is_trusted(peer, settings):
        log.warning("refused request from untrusted peer %s", peer)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    name = (request.headers.get("Remote-User") or "").strip().lower()
    if not name or name not in settings.allowed_users:
        log.warning("refused user %r from %s", name, peer)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    groups = tuple(g.strip() for g in (request.headers.get("Remote-Groups") or "").split(",") if g.strip())
    if settings.required_group and settings.required_group not in groups:
        log.warning("refused user %r: not in group %r", name, settings.required_group)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    return User(name=name, groups=groups, email=request.headers.get("Remote-Email"))
