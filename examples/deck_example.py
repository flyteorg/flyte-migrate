import flyte_migrate
import time, logging, flytekit
import pandas as pd
from flytekitplugins.deck.renderer import FrameProfilingRenderer

"""
These are packages for frame_renderer example
"""
custom_image = flytekit.ImageSpec(
    packages=[
        "flytekitplugins-deck-standard",
        "pandas",
        "ydata_profiling",
        "setuptools",
    ]
)

@flytekit.task(enable_deck=True, container_image=custom_image)
def simple_example() -> None:
    """
    Created A, B two non default TABs using Deck Class
    Added content to default(main) TAB
    Called default TAB will return main TAB in v2
    Iterating publish->flush method to visualize UI
    """
    flytekit.Deck("A", '<p>tab-a</p>')
    flytekit.Deck("B", '<p>tab-b</p>')
    flytekit.current_context().default_deck.append('<p>tab-main</p>')
    deck = flytekit.current_context().default_deck
    for i in range(3):
        deck.append(f"<h3>Step {i+1}</h3>\n<p>Working…</p>")
        flytekit.Deck.publish()
        time.sleep(5)
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

    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="flyte")
    print(run.name)
    print(run.url)
