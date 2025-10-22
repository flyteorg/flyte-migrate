# 🚀 flyte-migrate

**Seamlessly migrate your FlyteKit v1 workflows to Flyte v2 without rewriting your code.** ✨

## 🤔 What is flyte-migrate?

`flyte-migrate` is a compatibility layer that allows your existing flyte v1 workflows to run on Flyte v2 infrastructure. Instead of rewriting thousands of lines of workflow code, simply import `flyte_migrate` alongside your existing code and continue using familiar v1 APIs.

Think of it as a translator 🌐: your v1 code speaks to `flyte-migrate`, and `flyte-migrate` speaks to Flyte v2.

## 💡 Why use flyte-migrate?

- ✅ **Zero Code Rewrites**: Keep using flytekit syntax you already know
- 🔄 **Gradual Migration**: Migrate workflows incrementally at your own pace
- 🛡️ **Reduced Risk**: Test v2 infrastructure without changing your codebase
- ⚡ **Full Feature Support**: Tasks, workflows, dynamic tasks, map tasks, and plugins all work
- 🔌 **Plugin Compatibility**: Ray, Spark, and other plugins are automatically translated

## 🚀 Quick Start

### 📦 Installation

```bash
pip install flyte-migrate
```

### 💻 Basic Usage

Your existing FlyteKit v1 code:

```python
from flytekit import task, workflow

@task
def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow
def hello_workflow(name: str) -> str:
    return greet(name=name)
```

To run on Flyte v2, just add one import:

```python
import flyte_migrate  # Add this line
from flytekit import task, workflow

@task
def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow
def hello_workflow(name: str) -> str:
    return greet(name=name)
```

That's it! Your v1 workflow now runs on Flyte v2. ✨

### ▶️ Running Workflows

Execute locally:

```bash
python hello.py hello_workflow --name "World"
```

Register with Flyte:

```bash
flyte register hello.py
```

## 🔧 How It Works

`flyte-migrate` provides shimmed implementations of flytekit v1 APIs that:

1. ✅ Accept v1-style configurations
2. 🔄 Translate them to Flyte v2 equivalents
3. 🚀 Execute using the Flyte v2 engine

This means you get:
- The familiarity of v1 syntax
- The performance and features of v2 infrastructure
- A clear path to eventual full v2 adoption

## 📋 Requirements

- 🐍 Python 3.10 or higher
- 🚀 Flyte v2 sdk (`flyte` package)
- 📦 flytekit

## 🛠️ Development

### 🏗️ Setup

```bash
# Clone the repository
git clone https://github.com/flyteorg/flyte-migrate.git
cd flyte-migrate

# Install in development mode
pip install -e .
```
## ❓ FAQ

**Q: Will this work with all my v1 workflows?** 🤔
A: Most v1 workflows should work. If you encounter issues, please open an issue on GitHub.

**Q: Is there a performance penalty?** ⚡
A: The translation overhead is minimal. Your tasks run directly on Flyte v2 infrastructure.

**Q: When should I fully migrate to v2?** 📅
A: Use `flyte-migrate` to buy time and reduce risk. Migrate to native v2 APIs when convenient.

**Q: Can I mix v1 and v2 code?** 🔄
A: Yes! You can gradually introduce v2 code while keeping v1 code working via `flyte-migrate`.

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
