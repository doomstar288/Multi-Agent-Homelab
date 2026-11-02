# Multi-Agent-Homelab

A self-hosted harness where Claude, Gemini, and Grok monitor and help manage a homelab, with every change approved by a human.

It runs as a single lightweight container on the homelab server, behind Traefik and Authelia. No ports are published and nothing is exposed to the internet by the harness itself.

## Roadmap

1. **Foundation container** (this step): FastAPI + SQLite app, Authelia identity via Traefik forward-auth, tamper-evident audit log, provider key loading, hardened container.
2. **Monitoring layer** (read-only): container health, logs and resource use through a read-only Docker socket proxy, host metrics, and pfSense data. Agents summarize and alert; they can't change anything.
3. **Request and approval system**: Claude plans, Gemini and Grok review, and work is split to the best-suited model. Every change is shown as an exact command or diff that you approve before a separate, narrowly permissioned runner executes it.
4. **Hardening pass**: rate limits, model output treated as untrusted input to the runner, backups, and a kill switch.

## How access works

```
browser ──► Traefik ──► Authelia (login + 2FA) ──► Traefik ──► harness:8080
                         sets Remote-User / Remote-Groups
```

The harness believes the `Remote-User` header **only** when the connection comes directly from Traefik's IP (`HARNESS_TRUSTED_PROXIES`), and only for usernames in `HARNESS_ALLOWED_USERS`. Anything else gets a 403. With either setting empty, everyone is refused.

## Setup

1. **Authelia rule.** Require two-factor for the harness hostname in Authelia's `configuration.yml`:

   ```yaml
   access_control:
     rules:
       - domain: harness.home.example.com
         policy: two_factor
         subject: ['user:matt']
   ```

2. **Traefik middleware.** Your Authelia forward-auth middleware must pass the identity headers through. If it's defined with Docker labels on the Authelia container, it should include:

   ```
   traefik.http.middlewares.authelia.forwardauth.address=http://authelia:9091/api/authz/forward-auth
   traefik.http.middlewares.authelia.forwardauth.trustForwardHeader=true
   traefik.http.middlewares.authelia.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Email,Remote-Name
   ```

3. **Pin Traefik's IP.** The harness trusts identity headers from one address, so give Traefik a fixed IP on the shared network (e.g. `ipv4_address: 172.18.0.2` under its `networks:` entry) and use that as a `/32` in `.env`. Any other container on the network that tries to send `Remote-User` is refused.

4. **Configure and start.**

   ```sh
   cp .env.example .env            # then edit it
   touch secrets/claude_api_key secrets/gemini_api_key secrets/grok_api_key
   # paste each key into its file, then:
   sudo chown 10001:10001 secrets/*_api_key && sudo chmod 400 secrets/*_api_key
   docker compose up -d --build
   ```

5. Open `https://<HARNESS_HOST>`. You should land on the dashboard after Authelia, with each agent showing **key loaded** or **no key**, and the audit log showing a `startup` entry with **chain intact**.

## Endpoints

| Path | What it returns |
| --- | --- |
| `/` | Dashboard |
| `/api/me` | Your Authelia identity |
| `/api/providers` | Which model keys are loaded (never the keys themselves) |
| `/api/audit?limit=50` | Recent audit entries |
| `/api/audit/verify` | Whether the audit hash chain is intact |
| `/healthz` | Container healthcheck (only answers on localhost inside the container) |

## Security notes

- Container runs as UID 10001 with a read-only root filesystem, all capabilities dropped, `no-new-privileges`, and memory/CPU/PID limits.
- API keys are Docker secrets, never environment variables, and are never returned or logged.
- The audit log is append-only (SQLite triggers refuse updates and deletes) and hash-chained, so editing the database file directly shows up as a broken chain.
- No interactive API docs (`/docs`, `/openapi.json`) are served.
- Strict security headers on every response: CSP with no inline scripts, `frame-ancestors 'none'`, `no-referrer`, `no-store`.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```
