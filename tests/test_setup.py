"""Setup CLI contracts; every invocation uses a disposable synthetic install."""

import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = (
    "POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY", "N8N_RUNNERS_AUTH_TOKEN",
    "SEARXNG_SECRET", "REDIS_PASSWORD", "QDRANT_API_KEY", "SANDBOX_API_KEY",
    "SANDBOX_REGISTRATION_TOKEN", "SANDBOX_RUNNER_API_KEY",
)
GOOGLE_CLIENT_ID = "contract-test-client.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "contract-test-google-client-secret"


def read_env(path):
    return {
        key: value for line in path.read_text().splitlines()
        if line and not line.lstrip().startswith("#")
        for key, separator, value in [line.partition("=")]
        if separator
    }


class SetupContracts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(ROOT / "scripts" / "setup.py", self.root / "scripts" / "setup.py")
        shutil.copyfile(ROOT / ".env.example", self.root / ".env.example")
        self.env_path = self.root / ".env"
        self.oauth_path = self.root / ".local" / "google-oauth.json"

    def run_setup(self, *arguments):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / "setup.py"), *arguments],
            cwd=self.root, capture_output=True, text=True, check=False,
        )

    def initialize(self, *arguments):
        result = self.run_setup(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def write_google_client(self, client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET,
                            path=None, client_type="web"):
        path = path or self.oauth_path.parent / "google-client.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({client_type: {
            "client_id": client_id, "client_secret": client_secret,
            "redirect_uris": ["http://localhost:5678/rest/oauth2-credential/callback"],
        }}) + "\n")
        return path

    def assert_no_secret_output(self, result, values):
        output = result.stdout + result.stderr
        for value in values:
            if value:
                self.assertNotIn(value, output)

    def test_initialization_generates_distinct_private_secrets_and_empty_oauth(self):
        result = self.initialize()
        values = read_env(self.env_path)
        generated = [values[key] for key in SECRET_KEYS]
        for value in generated:
            self.assertRegex(value, r"\A[0-9a-f]{64}\Z")
        self.assertEqual(len(set(generated)), len(generated))
        self.assertEqual(stat.S_IMODE(self.env_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.oauth_path.parent.stat().st_mode), 0o700)
        self.assertEqual(json.loads(self.oauth_path.read_text()), {})
        self.assertTrue((self.root / "data" / "shared").is_dir())
        self.assertEqual(values["COMPOSE_FILE"], "docker-compose.yml")
        self.assert_no_secret_output(result, generated)

    def test_independent_installations_generate_fresh_secrets(self):
        self.initialize()
        first = read_env(self.env_path)
        self.env_path.unlink()
        self.initialize()
        second = read_env(self.env_path)
        for key in SECRET_KEYS:
            self.assertNotEqual(first[key], second[key], key)

    def test_rerun_preserves_existing_env_and_oauth(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        env_before = self.env_path.read_bytes()
        oauth_before = self.oauth_path.read_bytes()
        for arguments in ((), ("--sandbox",)):
            with self.subTest(arguments=arguments):
                result = self.run_setup(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.env_path.read_bytes(), env_before)
                self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
                self.assertEqual(stat.S_IMODE(self.env_path.stat().st_mode), 0o600)
                self.assert_no_secret_output(result, (read_env(self.env_path)[key] for key in SECRET_KEYS))

    def test_sandbox_initialization_enables_overlay_and_search(self):
        self.initialize("--sandbox")
        values = read_env(self.env_path)
        self.assertEqual(values["COMPOSE_FILE"], "docker-compose.yml,compose.sandbox.yml")
        self.assertEqual(values["COMPOSE_PATH_SEPARATOR"], ",")
        self.assertIn("search", values["COMPOSE_PROFILES"].split(","))

    def test_google_oauth_writes_parent_credential_without_printing_client_values(self):
        self.initialize()
        source = self.write_google_client()
        env_before = self.env_path.read_bytes()
        source_before = source.read_bytes()
        result = self.run_setup("--google-oauth")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.oauth_path.read_text()), {
            "googleOAuth2Api": {
                "clientId": GOOGLE_CLIENT_ID,
                "clientSecret": GOOGLE_CLIENT_SECRET,
            },
        })
        self.assertEqual(self.env_path.read_bytes(), env_before)
        self.assertEqual(source.read_bytes(), source_before)
        self.assertEqual(stat.S_IMODE(self.oauth_path.parent.stat().st_mode), 0o700)
        # Compose binds the file for n8n's non-root UID; the parent stays private.
        self.assertEqual(stat.S_IMODE(self.oauth_path.stat().st_mode), 0o644)
        self.assertFalse(self.oauth_path.with_suffix(".json.tmp").exists())
        self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_google_oauth_accepts_explicit_download_path(self):
        self.initialize()
        source = self.write_google_client(path=self.root / "downloaded-google-client.json")
        result = self.run_setup("--google-oauth", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.oauth_path.read_text())["googleOAuth2Api"]["clientSecret"],
                         GOOGLE_CLIENT_SECRET)
        self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_missing_google_value_preserves_existing_oauth(self):
        self.initialize()
        self.write_google_client()
        self.assertEqual(self.run_setup("--google-oauth").returncode, 0)
        oauth_before = self.oauth_path.read_bytes()
        for client_id, client_secret in (
            (GOOGLE_CLIENT_ID, ""), ("", GOOGLE_CLIENT_SECRET), ("", ""),
        ):
            with self.subTest(client_id=bool(client_id), client_secret=bool(client_secret)):
                self.write_google_client(client_id, client_secret)
                env_before = self.env_path.read_bytes()
                result = self.run_setup("--google-oauth")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
                self.assertEqual(self.env_path.read_bytes(), env_before)
                self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_invalid_google_client_preserves_existing_oauth(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        oauth_before = self.oauth_path.read_bytes()
        self.write_google_client(client_id="not-a-web-application-client")
        result = self.run_setup("--google-oauth")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
        self.assert_no_secret_output(result, ("not-a-web-application-client", GOOGLE_CLIENT_SECRET))

    def test_native_google_client_is_rejected_without_overwriting(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        oauth_before = self.oauth_path.read_bytes()
        self.write_google_client(client_type="installed")
        result = self.run_setup("--google-oauth")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
        self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_malformed_google_json_does_not_overwrite_or_echo_download(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        oauth_before = self.oauth_path.read_bytes()
        source = self.write_google_client()
        source.write_text('{"web": {"client_secret": "' + GOOGLE_CLIENT_SECRET + '", malformed}')
        result = self.run_setup("--google-oauth")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
        self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_invalid_google_json_shapes_preserve_existing_oauth(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        oauth_before = self.oauth_path.read_bytes()
        source = self.oauth_path.parent / "google-client.json"
        for payload in (
            [], {"web": []}, {"web": {}},
            {"web": {"client_id": GOOGLE_CLIENT_ID}},
            {"web": {"client_secret": GOOGLE_CLIENT_SECRET}},
            {"web": {"client_id": 123, "client_secret": GOOGLE_CLIENT_SECRET}},
            {"web": {"client_id": GOOGLE_CLIENT_ID, "client_secret": {"secret": GOOGLE_CLIENT_SECRET}}},
        ):
            with self.subTest(payload_type=type(payload).__name__, web_type=type(payload.get("web")).__name__
                              if isinstance(payload, dict) else None):
                source.write_text(json.dumps(payload))
                result = self.run_setup("--google-oauth")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
                self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))

    def test_missing_google_download_preserves_existing_oauth(self):
        self.initialize()
        self.oauth_path.write_text('{"existing": "keep-me"}\n')
        oauth_before = self.oauth_path.read_bytes()
        result = self.run_setup("--google-oauth", str(self.root / "missing-client.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.oauth_path.read_bytes(), oauth_before)

    def test_google_oauth_requires_initialized_env(self):
        result = self.run_setup("--google-oauth")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.env_path.exists())
        self.assertFalse(self.oauth_path.exists())

    def test_conflicting_setup_modes_do_not_mutate_existing_files(self):
        self.initialize()
        self.write_google_client()
        env_before = self.env_path.read_bytes()
        oauth_before = self.oauth_path.read_bytes()
        result = self.run_setup("--sandbox", "--google-oauth")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.env_path.read_bytes(), env_before)
        self.assertEqual(self.oauth_path.read_bytes(), oauth_before)
        self.assert_no_secret_output(result, (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET))


if __name__ == "__main__":
    unittest.main()
