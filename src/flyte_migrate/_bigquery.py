"""Shim for v1 BigQueryTask -> v2 TaskTemplate.

Patches ``flytekitplugins.bigquery.BigQueryTask`` so that instantiation produces
a v2-compatible ``TaskTemplate`` which serialises with task-type
``bigquery_query_job_task``, the correct ``custom`` config, and an embedded SQL
statement.  The v2 Flyte backend routes this to the BigQuery agent/connector
automatically.
"""

from __future__ import annotations

import sys
import types
import weakref
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from flyte._task import TaskTemplate
from flyte.models import NativeInterface, SerializationContext
from flyteidl2.core import tasks_pb2

from flyte_migrate._workflow import parent_env


@dataclass
class BigQueryConfig:
    """Standalone BigQueryConfig that mirrors the v1 class so that the module
    import works even when flytekitplugins-bigquery is not installed."""

    ProjectID: str
    Location: Optional[str] = None
    QueryJobConfig: Optional[Any] = None


@dataclass(kw_only=True)
class BigQueryTaskTemplate(TaskTemplate):
    """A v2 TaskTemplate that represents a v1 BigQueryTask.

    This is an agent/connector-based task -- no container is needed.  The Flyte
    backend dispatches it to the BigQuery connector by matching on ``task_type``.
    """

    task_type: str = "bigquery_query_job_task"
    image: None = None  # agent task, no image needed
    query_template: str = ""
    project_id: str = ""
    location: Optional[str] = None
    query_job_config: Optional[Any] = None

    def custom_config(self, sctx: SerializationContext) -> Dict[str, Any]:
        config: Dict[str, Any] = {
            "ProjectID": self.project_id,
            "Location": self.location,
        }
        if self.query_job_config is not None:
            config.update(self.query_job_config.to_api_repr()["query"])
        return config

    def sql(self, sctx: SerializationContext) -> tasks_pb2.Sql:
        return tasks_pb2.Sql(
            statement=self.query_template,
            dialect=tasks_pb2.Sql.Dialect.ANSI,
        )

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("BigQueryTask cannot be executed locally through the shim.")


def _create_bigquery_task_template(
    name: str,
    query_template: str,
    task_config: Any,
    inputs: Optional[Dict[str, Type]] = None,
    output_structured_dataset_type: Optional[Type] = None,
    **kwargs: Any,
) -> BigQueryTaskTemplate:
    """Factory that mirrors the v1 ``BigQueryTask.__init__`` signature and
    returns a v2 ``BigQueryTaskTemplate`` registered with the parent workflow
    environment."""

    # Build interface
    native_inputs: Dict[str, Any] = {}
    if inputs:
        for k, v in inputs.items():
            native_inputs[k] = (v, None)

    native_outputs: Dict[str, Type] = {}
    if output_structured_dataset_type is not None:
        native_outputs["results"] = output_structured_dataset_type

    interface = NativeInterface(inputs=native_inputs, outputs=native_outputs)

    tmpl = BigQueryTaskTemplate(
        name=parent_env.name + "." + name,
        short_name=name,
        interface=interface,
        query_template=query_template,
        project_id=task_config.ProjectID,
        location=getattr(task_config, "Location", None),
        query_job_config=getattr(task_config, "QueryJobConfig", None),
        parent_env=weakref.ref(parent_env),
        parent_env_name=parent_env.name,
    )
    parent_env._tasks[tmpl.name] = tmpl
    return tmpl


def _patch_bigquery() -> None:
    """Monkey-patch ``flytekitplugins.bigquery.BigQueryTask`` so that
    ``BigQueryTask(...)`` returns a ``BigQueryTaskTemplate``.

    If the real ``flytekitplugins.bigquery`` package is not installed (e.g. on
    the remote container), we register a synthetic module in ``sys.modules`` so
    that ``from flytekitplugins.bigquery import BigQueryConfig, BigQueryTask``
    works regardless.
    """
    # Ensure flytekitplugins namespace package exists
    if "flytekitplugins" not in sys.modules:
        pkg = types.ModuleType("flytekitplugins")
        pkg.__path__ = []  # type: ignore[attr-defined]
        pkg.__package__ = "flytekitplugins"
        sys.modules["flytekitplugins"] = pkg

    try:
        import flytekitplugins.bigquery as bq_mod
    except (ModuleNotFoundError, ImportError):
        # Create a synthetic module
        bq_mod = types.ModuleType("flytekitplugins.bigquery")
        bq_mod.__package__ = "flytekitplugins"  # type: ignore[attr-defined]
        bq_mod.BigQueryConfig = BigQueryConfig  # type: ignore[attr-defined]
        sys.modules["flytekitplugins.bigquery"] = bq_mod

    bq_mod.BigQueryTask = _create_bigquery_task_template  # type: ignore[attr-defined]


_patch_bigquery()
