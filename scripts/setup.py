#!/usr/bin/env python3
"""Initialize local configuration without installing Python packages."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys


ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = (
    "POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY", "N8N_RUNNERS_AUTH_TOKEN",
    "SEARXNG_SECRET", "REDIS_PASSWORD", "QDRANT_API_KEY", "SANDBOX_API_KEY",
    "SANDBOX_REGISTRATION_TOKEN", "SANDBOX_RUNNER_API_KEY",
)


def read_values(path):
    """Read literal values from our template; no shell execution or expansion."""
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("Invalid .env line; expected KEY=value")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def prepare_directories(root):
    local = root / ".local"
    local.mkdir(exist_ok=True)
    local.chmod(0o700)
    (root / "data" / "shared").mkdir(parents=True, exist_ok=True)
    return local


def write_oauth(root, values):
    client_id = values.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = values.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if bool(client_id) != bool(client_secret):
        raise ValueError("Set both GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")
    if client_id and not client_id.endswith(".apps.googleusercontent.com"):
        raise ValueError("Use the Client ID of a Google Web application OAuth client")
    payload = {"googleOAuth2Api": {"clientId": client_id, "clientSecret": client_secret}} if client_id else {}
    local = prepare_directories(root)
    # The host directory is private (0700). The container's non-root UID must
    # read the individual Compose secret bind mount, so the file uses 0644.
    temporary = local / "google-oauth.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.chmod(0o644)
    temporary.replace(local / "google-oauth.json")
    return bool(client_id)


def import_google(root, source):
    payload = json.loads(Path(source).read_text())
    web = payload.get("web") if isinstance(payload, dict) else None
    if not isinstance(web, dict):
        raise ValueError("Download a Web application OAuth client JSON from Google Cloud (not Desktop or service account)")
    client_id = web.get("client_id")
    client_secret = web.get("client_secret")
    if not isinstance(client_id, str) or not isinstance(client_secret, str) or not client_id or not client_secret:
        raise ValueError("Google JSON must contain web.client_id and web.client_secret")
    write_oauth(root, {"GOOGLE_OAUTH_CLIENT_ID": client_id, "GOOGLE_OAUTH_CLIENT_SECRET": client_secret})


def initialize(root, sandbox=False):
    env_path = root / ".env"
    if env_path.exists():
        raise ValueError(".env already exists; existing secrets were preserved. Edit it directly.")
    text = (root / ".env.example").read_text()
    for key in SECRET_KEYS:
        text = re.sub(rf"(?m)^{key}=.*$", f"{key}={secrets.token_hex(32)}", text)
    if sandbox:
        text = text.replace("COMPOSE_FILE=docker-compose.yml\n",
                            "COMPOSE_FILE=docker-compose.yml,compose.sandbox.yml\n")
    prepare_directories(root)
    with os.fdopen(os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(text)
    write_oauth(root, {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", action="store_true", help="Enable AI sandbox and web search on a new install")
    parser.add_argument("--google-oauth", nargs="?", const=str(ROOT / ".local" / "google-client.json"),
                        metavar="JSON_PATH", help="Import a downloaded Google Web application OAuth client JSON")
    args = parser.parse_args()
    try:
        if args.google_oauth:
            if args.sandbox:
                raise ValueError("Run --sandbox for initialization, then --google-oauth JSON_PATH")
            if not (ROOT / ".env").exists():
                raise ValueError("Initialize .env first")
            import_google(ROOT, args.google_oauth)
            print("Google OAuth overwrite file updated. Recreate n8n: docker compose up -d --force-recreate n8n")
        else:
            initialize(ROOT, sandbox=args.sandbox)
            print("Created .env and local secret file. Existing server data was not imported.")
            print("Enabled: n8n, PostgreSQL, Code runners, web search" + (", AI sandbox" if args.sandbox else ""))
            print("Next: docker compose config --quiet && docker compose up -d --wait --wait-timeout 600")
    except (OSError, ValueError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
