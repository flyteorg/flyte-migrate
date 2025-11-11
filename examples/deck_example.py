import flyte_migrate
import time, logging, flytekit
import plotly.express as px
import pandas as pd
from flytekitplugins.deck.renderer import FrameProfilingRenderer
from flytekit.core.context_manager import FlyteContextManager


custom_image = flytekit.ImageSpec(
    platform="linux/arm64",
    registry="localhost:30000",
    packages=[
        "flytekitplugins-deck-standard",
        "markdown",
        "pandas",
        "pillow",
        "plotly",
        "pyarrow",
        "scikit-learn",
        "ydata_profiling",
        "flytekitplugins-deck-standard",
        "setuptools",
    ]
)

@flytekit.task(enable_deck=True, container_image=custom_image)
def simple_example() -> None:
    a = flytekit.Deck("A", '<p>You can install flytekit using this command: <code>import flytekit-a</code></p>')
    b = flytekit.Deck("B", '<p>You can install flytekit using this command: <code>import flytekit-b</code></p>')
    d = flytekit.current_context().default_deck.append('<p>You can install flytekit using this command: <code>import flytekit-c</code></p>')
    deck = flytekit.current_context().default_deck
    for i in range(3):
        deck.append(f"<h3>Step {i+1}</h3>\n<p>Working…</p>")
        time.sleep(3)
        flytekit.Deck.publish()
    deck.append(f"<h3>✅ Done!<h3>")



@flytekit.task(enable_deck=True, container_image=custom_image)
def frame_renderer() -> None:
    df = pd.DataFrame(data={"col1": [1, 2], "col2": [3, 4]})
    flytekit.Deck("Frame Renderer", FrameProfilingRenderer().to_html(df=df))

@flytekit.workflow
def wf(name: str):
    simple_example()
    frame_renderer()

if __name__ == "__main__":
    """
    uv pip install -e .  # flyte-migrate
    uv pip install -e .  # flyte-sdk
    python examples/hello.py
    """
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="flyte")
    print(run.name)
    print(run.url)
