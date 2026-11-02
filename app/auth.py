"""Identity from the auth proxy (Authelia or Authentik), via Traefik forward-auth.

Traefik asks the auth proxy to authenticate every request and copies the
verified identity into headers (Remote-User for Authelia, X-authentik-username
for Authentik; see Settings). Only the headers the auth proxy actually returns
are overwritten by Traefik, so the configured names must match it exactly:
any other identity header could have been sent by the browser.

The headers are also only meaningful when the connection really came from
Traefik, so we check the direct peer address against HARNESS_TRUSTED_PROXIES.
"""

from __future__ import annotations

import ipaddress
import logging
import re
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

    name = (request.headers.get(settings.user_header) or "").strip().lower()
    if not name or name not in settings.allowed_users:
        log.warning("refused user %r from %s", name, peer)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    # Authelia separates groups with commas, Authentik with pipes.
    raw_groups = request.headers.get(settings.groups_header) or ""
    groups = tuple(g.strip() for g in re.split(r"[,|]", raw_groups) if g.strip())
    if settings.required_group and settings.required_group not in groups:
        log.warning("refused user %r: not in group %r", name, settings.required_group)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    return User(name=name, groups=groups, email=request.headers.get(settings.email_header))
