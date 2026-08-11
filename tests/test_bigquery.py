"""Tests for the BigQuery shim (_bigquery.py)."""

import sys

import pytest

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._bigquery import (
    BigQueryConfig,
    BigQueryTaskTemplate,
    _create_bigquery_task_template,
)


class TestBigQueryConfig:
    def test_defaults(self):
        cfg = BigQueryConfig(ProjectID="my-project")
        assert cfg.ProjectID == "my-project"
        assert cfg.Location is None
        assert cfg.QueryJobConfig is None

    def test_with_location(self):
        cfg = BigQueryConfig(ProjectID="p", Location="US")
        assert cfg.Location == "US"


class TestBigQueryTaskTemplate:
    def test_task_type(self):
        from flyte.models import NativeInterface

        tmpl = BigQueryTaskTemplate(
            name="test.bq",
            interface=NativeInterface(inputs={}, outputs={}),
            query_template="SELECT 1",
            project_id="flyte",
        )
        assert tmpl.task_type == "bigquery_query_job_task"
        assert tmpl.image is None

    def test_custom_config(self):
        from flyte.models import NativeInterface, SerializationContext

        tmpl = BigQueryTaskTemplate(
            name="test.bq",
            interface=NativeInterface(inputs={}, outputs={}),
            query_template="SELECT 1",
            project_id="flyte",
            location="US",
        )
        sctx = SerializationContext(project="p", domain="d", version="v", org="", input_path="", output_path="")
        custom = tmpl.custom_config(sctx)
        assert custom["ProjectID"] == "flyte"
        assert custom["Location"] == "US"

    def test_sql(self):
        from flyte.models import NativeInterface, SerializationContext

        tmpl = BigQueryTaskTemplate(
            name="test.bq",
            interface=NativeInterface(inputs={}, outputs={}),
            query_template="SELECT 1",
            project_id="flyte",
        )
        sctx = SerializationContext(project="p", domain="d", version="v", org="", input_path="", output_path="")
        sql = tmpl.sql(sctx)
        assert sql.statement == "SELECT 1"
        assert sql.dialect == 1  # ANSI

    def test_forward_raises(self):
        from flyte.models import NativeInterface

        tmpl = BigQueryTaskTemplate(
            name="test.bq",
            interface=NativeInterface(inputs={}, outputs={}),
            query_template="SELECT 1",
            project_id="flyte",
        )
        with pytest.raises(NotImplementedError):
            tmpl.forward()


class TestCreateBigQueryTaskTemplate:
    def test_no_io(self):
        cfg = BigQueryConfig(ProjectID="flyte")
        tmpl = _create_bigquery_task_template(
            name="sql.bigquery.no_io",
            query_template="SELECT 1",
            task_config=cfg,
            inputs={},
        )
        assert isinstance(tmpl, BigQueryTaskTemplate)
        assert tmpl.project_id == "flyte"
        assert tmpl.query_template == "SELECT 1"
        assert "sql.bigquery.no_io" in tmpl.name
        # v1 workflows call tasks synchronously; without this the call returns a coroutine
        assert tmpl._call_as_synchronous is True

    def test_with_inputs(self):
        cfg = BigQueryConfig(ProjectID="flyte")
        tmpl = _create_bigquery_task_template(
            name="sql.bigquery.with_input",
            query_template="SELECT * FROM t WHERE id = {{ .inputs.id }}",
            task_config=cfg,
            inputs={"id": int},
        )
        assert "id" in tmpl.interface.inputs

    def test_with_output(self):
        from flytekit.types.structured import StructuredDataset

        cfg = BigQueryConfig(ProjectID="flyte")
        tmpl = _create_bigquery_task_template(
            name="sql.bigquery.with_output",
            query_template="SELECT * FROM t",
            task_config=cfg,
            inputs={},
            output_structured_dataset_type=StructuredDataset,
        )
        assert "results" in tmpl.interface.outputs


class TestPatchBigquery:
    def test_patch_creates_synthetic_module(self):
        """Verify the synthetic module is in sys.modules."""
        assert "flytekitplugins.bigquery" in sys.modules
        mod = sys.modules["flytekitplugins.bigquery"]
        assert hasattr(mod, "BigQueryTask")
        assert hasattr(mod, "BigQueryConfig")

    def test_import_from_patched_module(self):
        """Verify that importing from the patched module works."""
        from flytekitplugins.bigquery import BigQueryConfig, BigQueryTask

        cfg = BigQueryConfig(ProjectID="test")
        assert cfg.ProjectID == "test"
        # BigQueryTask is now the factory function
        tmpl = BigQueryTask(
            name="test_task",
            query_template="SELECT 1",
            task_config=cfg,
        )
        assert isinstance(tmpl, BigQueryTaskTemplate)
