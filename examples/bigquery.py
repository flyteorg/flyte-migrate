import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import workflow
from flytekitplugins.bigquery import BigQueryConfig, BigQueryTask

bigquery_task_no_io = BigQueryTask(
    name="sql.bigquery.no_io",
    inputs={},
    query_template="SELECT 1",
    task_config=BigQueryConfig(ProjectID="flyte"),
)


@workflow
def no_io_wf():
    bigquery_task_no_io()


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(no_io_wf)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
