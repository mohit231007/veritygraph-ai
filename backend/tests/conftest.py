from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix="veritygraph-tests-")

# Set test-only defaults before test modules import app settings/repository singletons.
os.environ.setdefault(
    "VERITYGRAPH_DATABASE_PATH",
    str(Path(_TEST_DATA_DIR.name) / "veritygraph-test.db"),
)
os.environ.setdefault("VERITYGRAPH_WIKIPEDIA_PROVIDER", "fixture")
os.environ.setdefault("VERITYGRAPH_WEB_PROVIDER", "fixture")
