"""Put the repo root on sys.path so the tests can `from examples.<name> import <entrypoint>`.

pytest only adds the test file's own directory, and `examples` is not an installed package.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
