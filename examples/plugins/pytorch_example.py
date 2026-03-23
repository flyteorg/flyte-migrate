import flyte_migrate  # noqa: F401, I001
import logging
import os

import torch
from flytekit import ImageSpec, Resources, task, workflow
from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy
from torch import nn, optim
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, DistributedSampler, TensorDataset

# Image with dependencies
custom_image = ImageSpec(
    packages=[
        "torch",
        "torchvision",
        "flytekitplugins-kfpytorch",
        "tensorboardX",
        "matplotlib",
    ],
    registry="ghcr.io/flyteorg",
)


# Model Definition
class LinearRegressionModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(1, 1)

    def forward(self, x):
        return self.linear(x)


# DataLoader Preparation
def prepare_dataloader(rank: int, world_size: int, batch_size: int = 2) -> DataLoader:
    x_train = torch.tensor([[1.0], [2.0], [3.0], [4.0]])
    y_train = torch.tensor([[3.0], [5.0], [7.0], [9.0]])
    dataset = TensorDataset(x_train, y_train)

    sampler = DistributedSampler(
        dataset,
        num_replicas=world_size,
        rank=rank,
        shuffle=True,
    )

    return DataLoader(dataset, batch_size=batch_size, sampler=sampler)


# Training Loop
def train_ddp_model(epochs: int = 3, log_dir: str = "/tmp/logs") -> float:
    # Flyte Elastic sets environment variables automatically.
    os.makedirs(log_dir, exist_ok=True)

    torch.distributed.init_process_group("gloo")

    rank = torch.distributed.get_rank()
    world_size = torch.distributed.get_world_size()

    # Model + DDP
    model = LinearRegressionModel()
    model = DDP(model)

    dataloader = prepare_dataloader(rank, world_size, batch_size=2)

    criterion = nn.MSELoss()
    optimizer = optim.SGD(model.parameters(), lr=0.05)

    final_loss = 0.0

    for epoch in range(epochs):
        dataloader.sampler.set_epoch(epoch)  # ensure sampler shuffles correctly

        for x, y in dataloader:
            optimizer.zero_grad()

            outputs = model(x)
            loss = criterion(outputs, y)

            loss.backward()
            optimizer.step()

            final_loss = loss.item()

        # Rank 0 logs only
        if rank == 0:
            print(f"[Epoch {epoch}] loss={final_loss}")

    # Return final loss for rank 0 only
    return final_loss


# --- Basic single-node Elastic task ---
@task(
    task_config=Elastic(
        rdzv_configs={"timeout": "30000"},
        run_policy=RunPolicy(clean_pod_policy=CleanPodPolicy.ALL),
    ),
    retries=2,
    cache=True,
    cache_version="0.2",
    requests=Resources(cpu="1000m", mem="2500Mi"),
    limits=Resources(mem="2500Mi"),
    container_image=custom_image,
)
def train_task(epochs: int = 5) -> float:
    return train_ddp_model(epochs=epochs)


# --- Multi-node Elastic task with full RunPolicy ---
@task(
    task_config=Elastic(
        nnodes=2,
        nproc_per_node=4,
        max_restarts=3,
        monitor_interval=10,
        rdzv_configs={"timeout": "60000", "join_timeout": "30000"},
        run_policy=RunPolicy(
            clean_pod_policy=CleanPodPolicy.RUNNING,
            ttl_seconds_after_finished=1800,
            active_deadline_seconds=7200,
            backoff_limit=5,
        ),
    ),
    retries=3,
    requests=Resources(cpu="2", mem="8Gi"),
    limits=Resources(cpu="4", mem="16Gi"),
    container_image=custom_image,
)
def train_multinode_task(epochs: int = 10) -> float:
    return train_ddp_model(epochs=epochs)


# --- Elastic task with CleanPodPolicy.NONE and no restarts ---
@task(
    task_config=Elastic(
        nnodes=1,
        nproc_per_node=2,
        max_restarts=0,
        monitor_interval=30,
        run_policy=RunPolicy(
            clean_pod_policy=CleanPodPolicy.NONE,
            ttl_seconds_after_finished=600,
            backoff_limit=0,
        ),
    ),
    requests=Resources(cpu="1", mem="4Gi"),
    container_image=custom_image,
)
def train_no_restart_task(epochs: int = 3) -> float:
    return train_ddp_model(epochs=epochs)


# Evaluation (non-distributed)
@task(container_image=custom_image)
def evaluate_model() -> float:
    # Load model weights (already very simple model)
    model = LinearRegressionModel()
    x = torch.tensor([[5.0]])
    with torch.no_grad():
        y_pred = model(x).item()

    print(f"Model(5) = {y_pred}")
    return y_pred


@workflow
def pytorch_training_wf(epochs: int = 5) -> float:
    """
    Full Flyte workflow:
    1. Train distributed
    2. Evaluate
    3. Return combined score
    """
    final_loss = train_task(epochs=epochs)
    evaluation = evaluate_model()

    return (final_loss + evaluation) / 2.0


@workflow
def pytorch_multinode_wf(epochs: int = 10) -> float:
    """Multi-node training workflow."""
    final_loss = train_multinode_task(epochs=epochs)
    evaluation = evaluate_model()
    return (final_loss + evaluation) / 2.0


@workflow
def pytorch_no_restart_wf(epochs: int = 3) -> float:
    """No-restart training workflow with strict cleanup."""
    final_loss = train_no_restart_task(epochs=epochs)
    evaluation = evaluate_model()
    return (final_loss + evaluation) / 2.0


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    ctx = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG)

    print("--- Running basic pytorch workflow ---")
    run = ctx.run(pytorch_training_wf)
    print(run.name)
    print(run.url)

    print("--- Running multi-node pytorch workflow ---")
    run2 = ctx.run(pytorch_multinode_wf)
    print(run2.name)
    print(run2.url)

    print("--- Running no-restart pytorch workflow ---")
    run3 = ctx.run(pytorch_no_restart_wf)
    print(run3.name)
    print(run3.url)
