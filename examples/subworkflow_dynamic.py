"""
Comprehensive v1 flytekit example exercising:
- @dynamic with typed I/O
- Subworkflows (@workflow calling @workflow)
- Typed inputs/outputs: str, int, float, List[int], Dict[str, str], Optional[int], NamedTuple
- flytekit.Deck with HTML content
- @task with environment variables
- @task with enable_deck=True
"""

import flyte_migrate  # noqa: F401, I001
import logging
from typing import Dict, List, NamedTuple, Optional

from flytekit import Deck, ImageSpec, dynamic, task, workflow


image = ImageSpec(packages=["setuptools"])


# --- Typed NamedTuple output ---


class SummaryResult(NamedTuple):
    total: int
    average: float
    label: str


# --- Tasks ---


@task(container_image=image, environment={"MY_VAR": "my_value"})
def add_one(x: int) -> int:
    """Simple task that adds one to the input."""
    import os

    assert os.environ.get("MY_VAR") == "my_value", "Environment variable MY_VAR not set"
    return x + 1


@task(container_image=image)
def multiply(x: int, factor: float) -> float:
    """Multiply an integer by a float factor."""
    return x * factor


@task(container_image=image)
def sum_list(values: List[int]) -> int:
    """Sum a list of integers."""
    return sum(values)


@task(container_image=image)
def build_metadata(name: str, count: int) -> Dict[str, str]:
    """Build a metadata dictionary."""
    return {"name": name, "count": str(count), "status": "completed"}


@task(container_image=image)
def maybe_double(x: int, should_double: Optional[int] = None) -> int:
    """Optionally double the input. If should_double is provided and non-zero, double x."""
    if should_double:
        return x * 2
    return x


@task(container_image=image)
def compute_summary(values: List[int], label: str) -> SummaryResult:
    """Compute summary statistics and return as NamedTuple."""
    total = sum(values)
    average = total / len(values) if values else 0.0
    return SummaryResult(total=total, average=average, label=label)


@task(container_image=image, enable_deck=True)
def report_results(summary: SummaryResult, metadata: Dict[str, str]) -> str:
    """Create a Deck report with HTML content summarizing the results."""
    html = f"""
    <h2>Workflow Results</h2>
    <table border="1" cellpadding="5">
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total</td><td>{summary.total}</td></tr>
        <tr><td>Average</td><td>{summary.average:.2f}</td></tr>
        <tr><td>Label</td><td>{summary.label}</td></tr>
    </table>
    <h3>Metadata</h3>
    <ul>
    """
    for k, v in metadata.items():
        html += f"<li><b>{k}</b>: {v}</li>"
    html += "</ul>"

    Deck("Results", html)
    Deck.publish()
    return f"Report generated: total={summary.total}, avg={summary.average:.2f}"


# --- Subworkflow ---


@workflow
def compute_subworkflow(values: List[int], label: str) -> SummaryResult:
    """A subworkflow that computes summary stats from a list of ints."""
    return compute_summary(values=values, label=label)


# --- Dynamic task ---


@dynamic(container_image=image)
def dynamic_process(n: int) -> List[int]:
    """Dynamic task that generates n subtasks, each adding one to its index."""
    results: List[int] = []
    for i in range(n):
        result = add_one(x=i)
        doubled = maybe_double(x=result, should_double=1)
        results.append(doubled)
    return results


# --- Main workflow ---


@workflow
def wf(n: int = 3, name: str = "test") -> str:
    """
    Main workflow that exercises:
    - dynamic tasks (dynamic_process)
    - subworkflows (compute_subworkflow)
    - typed I/O (str, int, float, List[int], Dict[str,str], Optional[int], NamedTuple)
    - Deck reports (report_results)
    - environment variables (add_one)
    """
    # Dynamic: generate n processed values
    processed = dynamic_process(n=n)

    # Subworkflow: compute summary of the processed values
    summary = compute_subworkflow(values=processed, label=name)

    # Build metadata - use sum_list to get the total as an int for build_metadata
    total = sum_list(values=processed)
    metadata = build_metadata(name=name, count=total)

    # Create deck report passing the full NamedTuple and metadata
    return report_results(summary=summary, metadata=metadata)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, n=3, name="test")
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
