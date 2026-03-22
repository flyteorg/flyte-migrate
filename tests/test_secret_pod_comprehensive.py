"""Comprehensive tests for _secret.py and _pod_template.py transformation logic."""

from pathlib import Path
from unittest.mock import MagicMock

import flyte
import flytekit
from kubernetes.client import (
    V1Container,
    V1EnvVar,
    V1PodSpec,
    V1ResourceRequirements,
    V1Toleration,
)

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._secret import _convert_single_secret, _transform_secret_v1_to_v2

# ---------------------------------------------------------------------------
# _secret.py — _convert_single_secret
# ---------------------------------------------------------------------------


class TestConvertSingleSecretComprehensive:
    def test_env_var_mount_explicit(self):
        """ENV_VAR mount: as_env_var should be set, mount should be None."""
        s = flytekit.Secret(key="my-key", group="my-group", env_var="MY_VAR")
        result = _convert_single_secret(s)
        assert isinstance(result, flyte.Secret)
        assert result.key == "my-key"
        assert result.group == "my-group"
        assert result.as_env_var == "MY_VAR"
        assert result.mount is None

    def test_env_var_mount_with_mount_requirement(self):
        """Explicit MountType.ENV_VAR should route to as_env_var."""
        s = flytekit.Secret(
            key="k",
            group="g",
            env_var="E",
            mount_requirement=flytekit.Secret.MountType.ENV_VAR,
        )
        result = _convert_single_secret(s)
        assert result.as_env_var == "E"
        assert result.mount is None

    def test_file_mount(self):
        """FILE mount: mount should be /etc/flyte/secrets, as_env_var should be None."""
        s = MagicMock(spec=flytekit.Secret)
        s.key = "file-key"
        s.group = "file-group"
        s.env_var = "SHOULD_BE_IGNORED"
        s.mount_requirement = flytekit.Secret.MountType.FILE
        result = _convert_single_secret(s)
        assert isinstance(result, flyte.Secret)
        assert result.key == "file-key"
        assert result.group == "file-group"
        assert result.mount == Path("/etc/flyte/secrets")
        assert result.as_env_var is None

    def test_empty_group(self):
        """Empty group string should be passed through."""
        s = flytekit.Secret(key="k", group="", env_var="E")
        result = _convert_single_secret(s)
        assert result.group == ""

    def test_no_env_var_no_file(self):
        """Secret with no env_var and default mount type."""
        s = flytekit.Secret(key="k", group="g")
        result = _convert_single_secret(s)
        assert result.key == "k"
        assert result.group == "g"
        assert result.mount is None


# ---------------------------------------------------------------------------
# _secret.py — _transform_secret_v1_to_v2
# ---------------------------------------------------------------------------


class TestTransformSecretV1ToV2Comprehensive:
    def test_none_returns_none(self):
        assert _transform_secret_v1_to_v2(None) is None

    def test_empty_list_returns_none(self):
        assert _transform_secret_v1_to_v2([]) is None

    def test_mixed_mounts(self):
        """List with both ENV_VAR and FILE mount secrets."""
        file_secret = MagicMock(spec=flytekit.Secret)
        file_secret.key = "file-key"
        file_secret.group = "g"
        file_secret.env_var = None
        file_secret.mount_requirement = flytekit.Secret.MountType.FILE

        env_secret = flytekit.Secret(key="env-key", group="g", env_var="MY_ENV")

        result = _transform_secret_v1_to_v2([file_secret, env_secret])
        assert result is not None
        assert len(result) == 2

        # First should be FILE mount
        assert result[0].mount == Path("/etc/flyte/secrets")
        assert result[0].as_env_var is None

        # Second should be ENV_VAR mount
        assert result[1].as_env_var == "MY_ENV"
        assert result[1].mount is None

    def test_multiple_env_var_secrets(self):
        """Multiple ENV_VAR secrets should all convert correctly."""
        secrets = [
            flytekit.Secret(key="k1", group="g1", env_var="E1"),
            flytekit.Secret(key="k2", group="g2", env_var="E2"),
            flytekit.Secret(key="k3", group="g3", env_var="E3"),
        ]
        result = _transform_secret_v1_to_v2(secrets)
        assert result is not None
        assert len(result) == 3
        assert all(isinstance(r, flyte.Secret) for r in result)
        assert [r.as_env_var for r in result] == ["E1", "E2", "E3"]

    def test_preserves_order(self):
        """Output order should match input order."""
        secrets = [flytekit.Secret(key=f"k{i}", group=f"g{i}", env_var=f"E{i}") for i in range(5)]
        result = _transform_secret_v1_to_v2(secrets)
        assert result is not None
        for i, r in enumerate(result):
            assert r.key == f"k{i}"
            assert r.group == f"g{i}"


# ---------------------------------------------------------------------------
# _pod_template.py — _transform_pod_template_v1_to_v2
# ---------------------------------------------------------------------------


class TestTransformPodTemplateComprehensive:
    def test_none_returns_none(self):
        assert _transform_pod_template_v1_to_v2(None) is None  # type: ignore[arg-type]

    def test_falsy_returns_none(self):
        """Any falsy value should return None."""
        assert _transform_pod_template_v1_to_v2(0) is None  # type: ignore[arg-type]

    def test_labels_and_annotations(self):
        """Labels and annotations should pass through."""
        v1 = flytekit.PodTemplate(
            pod_spec=V1PodSpec(containers=[V1Container(name="primary")]),
            primary_container_name="primary",
            labels={"team": "ml", "env": "staging"},
            annotations={"owner": "test", "purpose": "ci"},
        )
        result = _transform_pod_template_v1_to_v2(v1)
        assert isinstance(result, flyte.PodTemplate)
        assert result.labels == {"team": "ml", "env": "staging"}
        assert result.annotations == {"owner": "test", "purpose": "ci"}

    def test_primary_container_name(self):
        """primary_container_name should pass through."""
        v1 = flytekit.PodTemplate(
            pod_spec=V1PodSpec(containers=[V1Container(name="my-container")]),
            primary_container_name="my-container",
        )
        result = _transform_pod_template_v1_to_v2(v1)
        assert result.primary_container_name == "my-container"

    def test_pod_spec_with_env_vars(self):
        """Pod spec with environment variables should pass through."""
        pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name="primary",
                    env=[
                        V1EnvVar(name="FOO", value="bar"),
                        V1EnvVar(name="BAZ", value="qux"),
                    ],
                )
            ]
        )
        v1 = flytekit.PodTemplate(pod_spec=pod_spec, primary_container_name="primary")
        result = _transform_pod_template_v1_to_v2(v1)
        assert result.pod_spec is not None
        container = result.pod_spec.containers[0]
        env_names = [e.name for e in container.env]
        assert "FOO" in env_names
        assert "BAZ" in env_names

    def test_pod_spec_with_resource_limits(self):
        """Pod spec with resource requirements should pass through."""
        pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name="primary",
                    resources=V1ResourceRequirements(
                        limits={"cpu": "2", "memory": "1Gi"},
                        requests={"cpu": "1", "memory": "512Mi"},
                    ),
                )
            ]
        )
        v1 = flytekit.PodTemplate(pod_spec=pod_spec, primary_container_name="primary")
        result = _transform_pod_template_v1_to_v2(v1)
        container = result.pod_spec.containers[0]
        assert container.resources.limits == {"cpu": "2", "memory": "1Gi"}
        assert container.resources.requests == {"cpu": "1", "memory": "512Mi"}

    def test_pod_spec_with_tolerations(self):
        """Pod spec with tolerations should pass through."""
        pod_spec = V1PodSpec(
            containers=[V1Container(name="primary")],
            tolerations=[
                V1Toleration(
                    key="dedicated",
                    operator="Equal",
                    value="ml",
                    effect="NoSchedule",
                )
            ],
        )
        v1 = flytekit.PodTemplate(pod_spec=pod_spec, primary_container_name="primary")
        result = _transform_pod_template_v1_to_v2(v1)
        assert len(result.pod_spec.tolerations) == 1
        t = result.pod_spec.tolerations[0]
        assert t.key == "dedicated"
        assert t.value == "ml"
        assert t.effect == "NoSchedule"

    def test_all_fields_together(self):
        """PodTemplate with all fields populated should pass through correctly."""
        pod_spec = V1PodSpec(
            containers=[
                V1Container(
                    name="worker",
                    env=[V1EnvVar(name="MODE", value="test")],
                    resources=V1ResourceRequirements(limits={"cpu": "4"}),
                )
            ],
            tolerations=[V1Toleration(key="gpu", operator="Exists", effect="NoSchedule")],
        )
        v1 = flytekit.PodTemplate(
            pod_spec=pod_spec,
            primary_container_name="worker",
            labels={"app": "test", "tier": "backend"},
            annotations={"note": "comprehensive"},
        )
        result = _transform_pod_template_v1_to_v2(v1)
        assert result.primary_container_name == "worker"
        assert result.labels == {"app": "test", "tier": "backend"}
        assert result.annotations == {"note": "comprehensive"}
        assert result.pod_spec.containers[0].name == "worker"
        assert len(result.pod_spec.tolerations) == 1
