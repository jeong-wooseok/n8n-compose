#!/usr/bin/env python3
"""Check installed services without printing credentials or resolved config."""

import json
import subprocess
import sys
import urllib.parse
import urllib.request

from setup import ROOT, read_values


def run(*args, input_text=None):
    result = subprocess.run(["docker", "compose", *args], cwd=ROOT, input=input_text, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("docker compose " + args[0] + " failed; inspect the service locally")
    return result.stdout


def get_json(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def main():
    try:
        values = read_values(ROOT / ".env")
        services = set(run("config", "--services").splitlines())
        address = values.get("N8N_LISTEN_ADDRESS", "127.0.0.1")
        # A wildcard bind is reached through loopback from this host.
        if address in ("0.0.0.0", "::"):
            address = "127.0.0.1"
        base = f"http://{address}:{values.get('N8N_PORT', '5678')}"
        with urllib.request.urlopen(base + "/healthz/readiness", timeout=10) as response:
            if response.status != 200:
                raise RuntimeError("n8n database readiness failed")
        print("PASS n8n database readiness")
        run("exec", "-T", "n8n", "node", "-e",
            "const fs=require('fs');const p='/data/shared/.write-check-'+process.pid;fs.writeFileSync(p,'ok');fs.unlinkSync(p)")
        print("PASS shared folder write access")
        run("exec", "-T", "n8n", "node", "-e",
                            "fetch('http://task-runners:5680/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))")
        print("PASS Code-node runner launcher health")
        if "searxng" in services:
            query = urllib.parse.urlencode({"q": "n8n workflow automation", "format": "json"})
            result = get_json(f"http://127.0.0.1:{values.get('SEARXNG_PORT', '8888')}/search?{query}")
            if not isinstance(result.get("results"), list) or not result["results"]:
                raise RuntimeError("Search API returned no results; inspect searxng logs and upstream engine access")
            print(f"PASS web search JSON API ({len(result['results'])} results)")
        if "sandbox-api" in services:
            run("exec", "-T", "sandbox-api", "wget", "-qO-", "http://127.0.0.1:8080/healthz")
            version = run("exec", "-T", "sandbox-runner-1", "docker", "version", "--format", "{{.Server.Version}}")
            if not version.strip():
                raise RuntimeError("Sandbox internal Docker engine is not ready")
            print("PASS sandbox API and isolated Docker engine")
            print(run("exec", "-T", "n8n", "node", input_text=(ROOT / "scripts" / "sandbox-smoke.js").read_text()).strip())
        oauth = json.loads((ROOT / ".local" / "google-oauth.json").read_text())
        if oauth.get("googleOAuth2Api", {}).get("clientId"):
            print("CONFIGURED Google OAuth client (user sign-in still requires consent)")
        else:
            print("PENDING Google OAuth JSON: run setup.py --google-oauth JSON_PATH")
        print("Startup checks passed. Model requests and Google sign-in require their own credentials.")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
