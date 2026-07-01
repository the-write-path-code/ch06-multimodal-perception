# Section 6.2: Shared Testing Fixtures

import pytest
import os
from pathlib import Path

@pytest.fixture(autouse=True)
def setup_test_env():
    """Sets up standard environment overrides for all unit testing runs."""
    os.environ["PIPELINE_CONCURRENCY"] = "3"
    os.environ["SAMPLE_DATA_DIR"] = "data/samples"
    os.environ["REGISTRY_DB_PATH"] = "data/test_registry.db"
    os.environ["HIGH_CONFIDENCE_THRESHOLD"] = "0.80"
    os.environ["LOW_CONFIDENCE_THRESHOLD"] = "0.40"
    yield
    # Clean up test registry db if created
    db_file = Path("data/test_registry.db")
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass
