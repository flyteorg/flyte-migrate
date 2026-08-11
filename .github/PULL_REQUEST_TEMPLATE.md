# Why are the changes needed?

<!-- Describe the problem. If this fixes a migration gap, include a minimal
repro: v1 code that fails (or behaves differently) when migrated to v2. -->

```python
import flyte_migrate  # noqa
from flytekit import task, workflow

# minimal v1 example that fails to migrate on v2
```

**Error / wrong behavior before this change:**

```text
paste the error or describe the incorrect behavior
```

# What changes were made?

<!-- Summarize what you changed and why this approach. Call out any behavior
changes visible to users of the shim. -->

# How was this tested?

- [ ] Added/updated unit tests (`uv run pytest`)
- [ ] Added/updated integration tests (`tests/integration/`), or explain why not needed
- [ ] Verified the repro above now works on v2

# Checklist

- [ ] `make fmt-check`, `make lint`, and `make mypy` pass
- [ ] Commits are signed (`git commit -s`)
