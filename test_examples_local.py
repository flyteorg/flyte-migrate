#!/usr/bin/env python3
"""Test examples in local mode with flyte v2 SDK."""

import logging
import sys

print("=" * 70)
print("Testing Examples in Local Mode")
print("=" * 70)

# Configure logging
logging.basicConfig(level=logging.WARNING)

import flyte_migrate  # noqa: F401, I001
import flyte

flyte.init_from_config(log_level=logging.WARNING)


def test_example(name, workflow_fn, **kwargs):
    """Test a workflow in local mode."""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    try:
        result = flyte.with_runcontext(mode="local").run(workflow_fn, **kwargs)
        print(f"✓ {name} PASSED")
        print(f"  Result: {result}")
        return True
    except Exception as e:
        print(f"✗ {name} FAILED")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# Test 1: File I/O Example
try:
    from examples.file_io_example import file_io_wf, directory_wf
    test_example("file_io_wf", file_io_wf, data="alice,100\nbob,200\n")
    test_example("directory_wf", directory_wf, items=["hello", "world"])
except Exception as e:
    print(f"✗ file_io_example import failed: {e}")

# Test 2: Complex Types Example
try:
    from examples.complex_types_example import training_wf
    test_example(
        "training_wf",
        training_wf,
        learning_rates=[0.01, 0.001, 0.0001],
        epochs=5,
        batch_size=32,
    )
except Exception as e:
    print(f"✗ complex_types_example import failed: {e}")

# Test 3: Nested Workflow Example
try:
    from examples.nested_workflow_example import multi_sensor_wf
    test_example("multi_sensor_wf", multi_sensor_wf)
except Exception as e:
    print(f"✗ nested_workflow_example import failed: {e}")

# Test 4: Error Handling Example
try:
    from examples.error_handling_example import error_handling_wf
    test_example("error_handling_wf", error_handling_wf, value=42, failure_rate=0.0)
except Exception as e:
    print(f"✗ error_handling_example import failed: {e}")

# Test 5: Map Task Example
try:
    from examples.map_task import map_workflow
    test_example("map_workflow", map_workflow, list_q=[1, 2, 3], p=2.0, s=3.0)
except Exception as e:
    print(f"✗ map_task import failed: {e}")

# Test 6: Hello Example
try:
    from examples.hello import wf as hello_wf
    result = flyte.with_runcontext(mode="local").run(hello_wf, name="Test")
    print(f"\n{'='*70}")
    print(f"Testing: hello_wf")
    print(f"{'='*70}")
    print(f"✓ hello_wf PASSED")
    print(f"  Result: {result}")
except Exception as e:
    print(f"✗ hello example failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Launch Plan Example
try:
    from examples.launchplan_example import greeting_wf
    result = flyte.with_runcontext(mode="local").run(
        greeting_wf, name="World", greeting="Hello", uppercase=False
    )
    print(f"\n{'='*70}")
    print(f"Testing: greeting_wf")
    print(f"{'='*70}")
    print(f"✓ greeting_wf PASSED")
    print(f"  Result: {result}")
except Exception as e:
    print(f"✗ launchplan_example failed: {e}")
    import traceback
    traceback.print_exc()

# Test 8: Secret Example (will fail without secrets but should import)
try:
    from examples.secret_example import secret_wf
    print("\n" + "=" * 70)
    print("secret_wf imported successfully (skipping execution - needs secrets)")
    print("=" * 70)
except Exception as e:
    print(f"✗ secret_example import failed: {e}")

print("\n" + "=" * 70)
print("Testing Complete!")
print("=" * 70)
