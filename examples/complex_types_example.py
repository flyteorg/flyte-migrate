import flyte_migrate  # noqa: F401, I001
import logging
from dataclasses import dataclass
from typing import List

from flytekit import task, workflow


@dataclass
class TrainingConfig:
    """Configuration for a training run."""

    learning_rate: float
    epochs: int
    batch_size: int
    model_name: str


@dataclass
class TrainingResult:
    """Results from a training run."""

    accuracy: float
    loss: float
    epochs_completed: int
    config: TrainingConfig


@task
def create_configs(
    learning_rates: List[float],
    epochs: int,
    batch_size: int,
    model_name: str,
) -> List[TrainingConfig]:
    """Create a list of training configurations with different learning rates."""
    return [
        TrainingConfig(
            learning_rate=lr,
            epochs=epochs,
            batch_size=batch_size,
            model_name=model_name,
        )
        for lr in learning_rates
    ]


@task
def train_model(config: TrainingConfig) -> TrainingResult:
    """Simulate training a model with the given configuration."""
    # Simulated training - in real code this would train a model
    simulated_accuracy = 0.95 - config.learning_rate * 0.1
    simulated_loss = config.learning_rate * 0.5
    return TrainingResult(
        accuracy=simulated_accuracy,
        loss=simulated_loss,
        epochs_completed=config.epochs,
        config=config,
    )


@task
def select_best(results: List[TrainingResult]) -> TrainingResult:
    """Select the best model based on accuracy."""
    return max(results, key=lambda r: r.accuracy)


@workflow
def training_wf(
    learning_rates: List[float] = [0.01, 0.001, 0.0001],
    epochs: int = 10,
    batch_size: int = 32,
    model_name: str = "simple_nn",
) -> TrainingResult:
    """
    Demonstrates using dataclasses as complex types in Flyte workflows.

    Creates training configurations, trains models, and selects the best one.
    Exercises: @dataclass serialization, List types, nested dataclasses.
    """
    configs = create_configs(
        learning_rates=learning_rates,
        epochs=epochs,
        batch_size=batch_size,
        model_name=model_name,
    )
    # Train each config individually and collect results
    result_1 = train_model(config=configs[0])
    result_2 = train_model(config=configs[1])
    result_3 = train_model(config=configs[2])
    best = select_best(results=[result_1, result_2, result_3])
    return best


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(training_wf)
    print(run.name)
    print(run.url)
