"""Compose behavior contracts; uses synthetic credentials and needs no daemon."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SECRET_VALUES = {
    key: f"test-only-{key.lower()}" for key in (
        "POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY", "N8N_RUNNERS_AUTH_TOKEN",
        "SEARXNG_SECRET", "REDIS_PASSWORD", "QDRANT_API_KEY", "SANDBOX_API_KEY",
        "SANDBOX_REGISTRATION_TOKEN", "SANDBOX_RUNNER_API_KEY",
    )
}
IMAGE_VARIABLES = (
    "POSTGRES_IMAGE", "SEARXNG_IMAGE",
    "REDIS_IMAGE", "REDISINSIGHT_IMAGE", "QDRANT_IMAGE", "SANDBOX_API_IMAGE",
    "SANDBOX_RUNNER_IMAGE", "SANDBOX_WORKLOAD_IMAGE",
)
DEFAULT_IMAGES = {
    "n8n": "docker.n8n.io/n8nio/n8n:latest",
    "task-runners": "n8nio/runners:latest",
    "postgres": "postgres:17-alpine",
    "searxng": "ghcr.io/searxng/searxng:latest",
    "redis": "redis:7.4-alpine",
    "redisinsight": "redis/redisinsight:latest",
    "qdrant": "qdrant/qdrant:latest",
    "sandbox-certs": "ghcr.io/n8n-io/n8n-sandbox-service-api:latest",
    "sandbox-api": "ghcr.io/n8n-io/n8n-sandbox-service-api:latest",
    "sandbox-runner-1": "ghcr.io/n8n-io/n8n-sandbox-service-runner-dind:latest",
}
DEFAULT_WORKLOAD_IMAGE = "ghcr.io/n8n-io/n8n-sandbox-service-sandbox:latest"


def compose_model(profiles="", sandbox=False, overrides=None):
    """Render public config with dummy values; None removes a template value."""
    overrides = overrides or {}
    for key, value in overrides.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Override names must be environment variable names")
        if value is not None and (not isinstance(value, str) or "\n" in value or "\r" in value):
            raise ValueError("Override values must be a single line or None")
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        referenced = set()
        for name in ("docker-compose.yml", "compose.sandbox.yml"):
            shutil.copyfile(ROOT / name, target / name)
            referenced.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", (ROOT / name).read_text()))
        shutil.copytree(ROOT / "config", target / "config")
        (target / ".local").mkdir()
        (target / ".local" / "google-oauth.json").write_text("{}\n")
        (target / "data" / "shared").mkdir(parents=True)
        values = {
            key: value for line in (ROOT / ".env.example").read_text().splitlines()
            if line and not line.lstrip().startswith("#")
            for key, separator, value in [line.partition("=")]
            if separator
        }
        values.update(SECRET_VALUES)
        values.update({
            "COMPOSE_PROJECT_NAME": "n8n-contract-test",
            "COMPOSE_FILE": "docker-compose.yml,compose.sandbox.yml" if sandbox else "docker-compose.yml",
            "COMPOSE_PROFILES": profiles,
            "GOOGLE_OAUTH_CLIENT_ID": "compose-test-client.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "compose-test-google-secret",
            "N8N_INSTANCE_AI_MODEL_API_KEY": "compose-test-model-key",
        })
        for key, value in overrides.items():
            if value is None:
                values.pop(key, None)
            else:
                values[key] = value
        (target / ".env").write_text("\n".join(f"{k}={v}" for k, v in values.items()))
        # Isolate variables missing from the template too, including fallback
        # image/version selections and values intentionally removed by a test.
        isolated = referenced | set(values) | set(overrides)
        env = {k: v for k, v in os.environ.items() if k not in isolated and not k.startswith("COMPOSE_")}
        result = subprocess.run(
            ["docker", "compose", "--project-directory", str(target),
             "--env-file", str(target / ".env"), "config", "--format", "json"],
            capture_output=True, text=True, env=env, check=True,
        )
        return json.loads(result.stdout)


class CoreContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = compose_model()
        cls.services = cls.model["services"]

    def test_n8n_uses_postgres_service_dns(self):
        settings = self.services["n8n"]["environment"]
        self.assertEqual(settings["DB_TYPE"], "postgresdb")
        self.assertEqual(settings["DB_POSTGRESDB_HOST"], "postgres")

    def test_n8n_configuration_survives_container_replacement(self):
        targets = {v["target"] for v in self.services["n8n"]["volumes"]}
        self.assertIn("/home/node/.n8n", targets)

    def test_postgres_17_data_survives_container_replacement(self):
        self.assertIn(":17", self.services["postgres"]["image"])
        targets = {v["target"] for v in self.services["postgres"]["volumes"]}
        self.assertIn("/var/lib/postgresql/data", targets)

    def test_database_and_runner_share_n8n_network(self):
        networks = set(self.services["n8n"]["networks"])
        for service in ("postgres", "task-runners"):
            self.assertTrue(networks.intersection(self.services[service]["networks"]))

    def test_runner_connects_to_main_broker(self):
        settings = self.services["task-runners"]["environment"]
        self.assertEqual(settings["N8N_RUNNERS_TASK_BROKER_URI"], "http://n8n:5679")
        self.assertTrue(settings["N8N_RUNNERS_AUTH_TOKEN"])

    def test_encryption_key_comes_from_environment(self):
        self.assertIn("N8N_ENCRYPTION_KEY", self.services["n8n"]["environment"])
        self.assertRegex((ROOT / "docker-compose.yml").read_text(), r"N8N_ENCRYPTION_KEY.*\$\{")

    def test_core_runs_without_optional_profile_services(self):
        self.assertEqual(set(self.services), {"postgres", "n8n", "task-runners"})

    def test_database_has_no_host_port_and_shares_internal_service_network(self):
        self.assertFalse(self.services["postgres"].get("ports"))
        self.assertNotEqual(self.services["postgres"].get("network_mode"), "host")
        self.assertTrue(set(self.services["postgres"]["networks"]).intersection(
            self.services["n8n"]["networks"]))

    def test_runner_and_n8n_versions_and_auth_match(self):
        n8n = self.services["n8n"]
        runner = self.services["task-runners"]
        self.assertEqual(n8n["image"].rsplit(":", 1)[1], runner["image"].rsplit(":", 1)[1])
        self.assertEqual(n8n["environment"]["N8N_RUNNERS_AUTH_TOKEN"],
                         runner["environment"]["N8N_RUNNERS_AUTH_TOKEN"])


class ProfileContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search = compose_model(profiles="search")
        cls.all = compose_model(profiles="*")
        cls.sandbox = compose_model(profiles="search", sandbox=True)
        cls.sandbox_all = compose_model(profiles="*", sandbox=True)

    def test_search_profile_adds_only_search_to_core(self):
        self.assertEqual(set(self.search["services"]), {"postgres", "n8n", "task-runners", "searxng"})

    def test_all_profiles_compose_together(self):
        self.assertEqual(set(self.all["services"]), {
            "postgres", "n8n", "task-runners", "searxng", "redis", "redisinsight", "qdrant",
        })

    def test_all_profiles_and_sandbox_compose_together(self):
        self.assertEqual(set(self.sandbox_all["services"]), set(self.all["services"]) | {
            "sandbox-certs", "sandbox-api", "sandbox-runner-1",
        })

    def test_sandbox_overlay_preserves_database_dependency_and_adds_healthy_dependencies(self):
        services = self.sandbox["services"]
        self.assertEqual(set(services), {
            "postgres", "n8n", "task-runners", "searxng",
            "sandbox-certs", "sandbox-api", "sandbox-runner-1",
        })
        dependencies = services["n8n"]["depends_on"]
        for dependency in ("postgres", "searxng", "sandbox-api"):
            self.assertEqual(dependencies[dependency]["condition"], "service_healthy")
        self.assertEqual(services["sandbox-api"]["depends_on"]["sandbox-certs"]["condition"],
                         "service_completed_successfully")

    def test_every_published_port_defaults_to_loopback(self):
        for name, service in self.all["services"].items():
            for port in service.get("ports", []):
                with self.subTest(service=name):
                    self.assertEqual(port["host_ip"], "127.0.0.1")
        for name in ("postgres", "task-runners", "redis", "sandbox-api", "sandbox-runner-1"):
            service = self.sandbox["services"].get(name, self.all["services"].get(name))
            self.assertFalse(service.get("ports"), name)

    def test_database_and_shared_auth_secrets_only_reach_consuming_services(self):
        expected = {
            "POSTGRES_PASSWORD": {"postgres", "n8n"},
            "N8N_ENCRYPTION_KEY": {"n8n"},
            "N8N_RUNNERS_AUTH_TOKEN": {"n8n", "task-runners"},
            "SEARXNG_SECRET": {"searxng"},
            "REDIS_PASSWORD": {"redis"},
            "QDRANT_API_KEY": {"qdrant"},
            "SANDBOX_API_KEY": {"n8n", "sandbox-api"},
            "SANDBOX_REGISTRATION_TOKEN": {"sandbox-api", "sandbox-runner-1"},
            "SANDBOX_RUNNER_API_KEY": {"sandbox-api", "sandbox-runner-1"},
        }
        combined = self.sandbox_all["services"]
        for key, recipients in expected.items():
            with self.subTest(secret=key):
                observed = {name for name, service in combined.items()
                            if SECRET_VALUES[key] in json.dumps(service)}
                self.assertEqual(observed, recipients)

    def test_google_overwrite_is_mounted_only_into_n8n(self):
        for model in (self.all, self.sandbox):
            for name, service in model["services"].items():
                with self.subTest(service=name, sandbox="sandbox-api" in model["services"]):
                    references = [secret for secret in service.get("secrets", [])
                                  if secret["source"] == "google_oauth"]
                    self.assertEqual(bool(references), name == "n8n")
                    if name == "n8n":
                        self.assertEqual(references[0]["target"], "google-oauth.json")
                        self.assertEqual(service["environment"]["CREDENTIALS_OVERWRITE_DATA_FILE"],
                                         "/run/secrets/google-oauth.json")
                    self.assertNotIn("GOOGLE_OAUTH_CLIENT_ID", service.get("environment", {}))
                    self.assertNotIn("GOOGLE_OAUTH_CLIENT_SECRET", service.get("environment", {}))
                    self.assertNotIn("compose-test-google-secret", json.dumps(service))

    def test_sandbox_does_not_bind_host_docker_socket_or_publish_runner_ports(self):
        services = self.sandbox["services"]
        self.assertTrue(services["sandbox-runner-1"]["privileged"])
        for name, service in services.items():
            if name != "sandbox-runner-1":
                self.assertFalse(service.get("privileged", False), name)
            for volume in service.get("volumes", []):
                self.assertNotIn("docker.sock", volume.get("source", ""))
                self.assertNotIn("docker.sock", volume.get("target", ""))
            if name.startswith("sandbox-"):
                self.assertFalse(service.get("ports"), name)


class ImageVersionContracts(unittest.TestCase):
    def defaults_only(self, **overrides):
        values = dict.fromkeys((*IMAGE_VARIABLES, "N8N_VERSION", "SANDBOX_VERSION"))
        values.update(overrides)
        return compose_model(profiles="*", sandbox=True, overrides=values)

    def test_new_template_does_not_require_individual_image_settings(self):
        keys = {line.partition("=")[0] for line in (ROOT / ".env.example").read_text().splitlines()
                if line and not line.lstrip().startswith("#") and "=" in line}
        self.assertFalse({key for key in keys if key.endswith("_IMAGE")})

    def test_new_template_tracks_latest_n8n_and_runner_releases(self):
        services = compose_model()["services"]
        for name in ("n8n", "task-runners"):
            with self.subTest(service=name):
                self.assertEqual(services[name]["image"], DEFAULT_IMAGES[name])

    def test_latest_defaults_resolve_every_profile_and_sandbox_without_image_variables(self):
        services = self.defaults_only()["services"]
        self.assertEqual(set(services), set(DEFAULT_IMAGES))
        for name, image in DEFAULT_IMAGES.items():
            with self.subTest(service=name):
                self.assertEqual(services[name]["image"], image)
        self.assertEqual(services["sandbox-runner-1"]["environment"]["SANDBOX_RUNNER_DOCKER_SANDBOX_IMAGE"],
                         DEFAULT_WORKLOAD_IMAGE)

    def test_one_n8n_version_selects_matching_main_and_runner_releases(self):
        services = self.defaults_only(N8N_VERSION="9.8.7-contract")["services"]
        self.assertEqual(services["n8n"]["image"], "docker.n8n.io/n8nio/n8n:9.8.7-contract")
        self.assertEqual(services["task-runners"]["image"], "n8nio/runners:9.8.7-contract")

    def test_one_sandbox_version_selects_api_cert_runner_and_workload_releases(self):
        services = self.defaults_only(SANDBOX_VERSION="9.8.7-contract")["services"]
        for name, repository in (
            ("sandbox-api", "n8n-sandbox-service-api"),
            ("sandbox-certs", "n8n-sandbox-service-api"),
            ("sandbox-runner-1", "n8n-sandbox-service-runner-dind"),
        ):
            with self.subTest(service=name):
                self.assertEqual(services[name]["image"], f"ghcr.io/n8n-io/{repository}:9.8.7-contract")
        self.assertEqual(services["sandbox-runner-1"]["environment"]["SANDBOX_RUNNER_DOCKER_SANDBOX_IMAGE"],
                         "ghcr.io/n8n-io/n8n-sandbox-service-sandbox:9.8.7-contract")

    def test_individual_tag_and_digest_image_overrides_win_over_shared_versions(self):
        overrides = {
            key: f"registry.example.test/contracts/{key.lower()}:selected-tag"
            if index % 2 == 0 else f"registry.example.test/contracts/{key.lower()}@sha256:{index:064x}"
            for index, key in enumerate(IMAGE_VARIABLES, start=1)
        }
        services = self.defaults_only(N8N_VERSION="ignored-version", SANDBOX_VERSION="ignored-version",
                                      **overrides)["services"]
        for name, variable in (
            ("postgres", "POSTGRES_IMAGE"), ("searxng", "SEARXNG_IMAGE"),
            ("redis", "REDIS_IMAGE"), ("redisinsight", "REDISINSIGHT_IMAGE"),
            ("qdrant", "QDRANT_IMAGE"), ("sandbox-certs", "SANDBOX_API_IMAGE"),
            ("sandbox-api", "SANDBOX_API_IMAGE"), ("sandbox-runner-1", "SANDBOX_RUNNER_IMAGE"),
        ):
            with self.subTest(service=name):
                self.assertEqual(services[name]["image"], overrides[variable])
        self.assertEqual(services["sandbox-runner-1"]["environment"]["SANDBOX_RUNNER_DOCKER_SANDBOX_IMAGE"],
                         overrides["SANDBOX_WORKLOAD_IMAGE"])

    def test_ambient_compose_image_version_and_listen_settings_are_isolated(self):
        ambient = {key: "registry.example.test/ambient:must-not-be-used" for key in IMAGE_VARIABLES}
        ambient.update({
            "N8N_VERSION": "ambient-version", "SANDBOX_VERSION": "ambient-version",
            "N8N_LISTEN_ADDRESS": "0.0.0.0", "POSTGRES_PASSWORD": "ambient-password",
            "COMPOSE_FILE": "/nonexistent-ambient-compose.yml",
            "COMPOSE_ENV_FILES": "/nonexistent-ambient.env", "COMPOSE_PROFILES": "invalid-profile",
        })
        with patch.dict(os.environ, ambient):
            services = self.defaults_only()["services"]
        for name, image in DEFAULT_IMAGES.items():
            with self.subTest(service=name):
                self.assertEqual(services[name]["image"], image)
        self.assertEqual(services["n8n"]["ports"][0]["host_ip"], "127.0.0.1")
        self.assertEqual(services["postgres"]["environment"]["POSTGRES_PASSWORD"],
                         SECRET_VALUES["POSTGRES_PASSWORD"])

    def test_override_inputs_cannot_add_dotenv_lines(self):
        for overrides in ({"N8N_VERSION\nOTHER": "value"}, {"N8N_VERSION": "stable\nOTHER=value"},
                          {"N8N_VERSION": "stable\rOTHER=value"}, {"N8N_VERSION": 123}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    compose_model(overrides=overrides)


if __name__ == "__main__":
    unittest.main()
