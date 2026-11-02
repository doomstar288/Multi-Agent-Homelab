"""The three model providers and their roles.

Step 1 only loads and reports on API keys; the actual model calls arrive with
the request system in step 3. Keys are read from Docker secrets and are never
returned by any endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    role: str
    secret: str  # file name under the secrets directory


PROVIDERS: tuple[Provider, ...] = (
    Provider("claude", "Claude (Anthropic)", "planner", "claude_api_key"),
    Provider("gemini", "Gemini (Google)", "reviewer", "gemini_api_key"),
    Provider("grok", "Grok (xAI)", "reviewer", "grok_api_key"),
)


def load_key(secrets_dir: Path, provider: Provider) -> str | None:
    path = secrets_dir / provider.secret
    try:
        key = path.read_text().strip()
    except OSError:
        return None
    return key or None


def status(secrets_dir: Path) -> list[dict[str, object]]:
    return [
        {"name": p.name, "label": p.label, "role": p.role, "configured": load_key(secrets_dir, p) is not None}
        for p in PROVIDERS
    ]
