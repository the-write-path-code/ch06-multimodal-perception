# Section 6.2: AppConfig Unit Tests

import os
import pytest
from pydantic import ValidationError
from ch6.config import AppConfig

def test_config_defaults(monkeypatch):
    """Verifies that the configuration system loads reasonable defaults."""
    monkeypatch.delenv("PIPELINE_CONCURRENCY", raising=False)
    cfg = AppConfig()
    assert cfg.pipeline_concurrency == 5
    assert cfg.enable_sparse_embeddings is True
    assert cfg.use_local_vlm is False

def test_config_env_overrides():
    """Verifies that environment overrides change loaded values."""
    os.environ["PIPELINE_CONCURRENCY"] = "12"
    os.environ["USE_LOCAL_VLM"] = "True"
    
    cfg = AppConfig()
    assert cfg.pipeline_concurrency == 12
    assert cfg.use_local_vlm is True

    # Clean up environment
    del os.environ["PIPELINE_CONCURRENCY"]
    del os.environ["USE_LOCAL_VLM"]

def test_config_validation_error():
    """Verifies that invalid configuration inputs raise ValidationError."""
    os.environ["PIPELINE_CONCURRENCY"] = "invalid-integer-here"
    try:
        with pytest.raises(ValidationError):
            AppConfig()
    finally:
        del os.environ["PIPELINE_CONCURRENCY"]
