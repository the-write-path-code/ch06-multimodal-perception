# Section 6.2: Perception Dispatcher Unit Tests

import os
import pytest
from ch6.perception.dispatcher import PerceptionDispatcher
from ch6.models import ModalityType

@pytest.mark.asyncio
async def test_dispatcher_nonexistent_file():
    """Verifies that the dispatcher gracefully handles nonexistent files, returning empty list without throwing."""
    dispatcher = PerceptionDispatcher()
    chunks = await dispatcher.perceive("nonexistent_file_path.pdf")
    assert chunks == []

@pytest.mark.asyncio
async def test_dispatcher_unknown_extension(tmp_path):
    """Verifies that unknown file extensions are ignored safely."""
    dispatcher = PerceptionDispatcher()
    test_file = tmp_path / "data_feed.json"
    test_file.write_text("{}")
    
    chunks = await dispatcher.perceive(str(test_file))
    assert chunks == []
