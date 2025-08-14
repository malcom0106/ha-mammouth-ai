"""Tests pour le coordinator."""
import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from custom_components.mammouth_ai.coordinator import MammouthDataUpdateCoordinator

@pytest.fixture
def hass():
    """Home Assistant fixture."""
    return AsyncMock(spec=HomeAssistant)

@pytest.fixture
def mock_entry():
    """Config entry fixture."""
    entry = AsyncMock()
    entry.data = {
        "api_key": "test_key",
        "base_url": "https://test.api",
        "model": "test-model"
    }
    entry.options = {}
    return entry

@pytest.mark.asyncio
async def test_chat_completion(hass, mock_entry):
    """Test chat completion."""
    coordinator = MammouthDataUpdateCoordinator(hass, mock_entry)
    
    with patch.object(coordinator._session, 'post') as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await coordinator.async_chat_completion([
            {"role": "user", "content": "Test"}
        ])
        
        assert result == "Test response"