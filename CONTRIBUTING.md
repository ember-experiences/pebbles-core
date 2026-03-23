# Contributing to Pebbles

Thanks for considering contributing to Pebbles! This document covers how to extend the system with new sources, delivery adapters, and matching strategies.

---

## Adding a New Source

Sources fetch content from external platforms. All sources inherit from `BaseSource` and implement the `fetch()` method.

### 1. Create the source file

```bash
touch pebbles/sources/your_source.py
```

### 2. Implement the source class

```python
"""Your source description."""

import logging
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models import Pebble

logger = logging.getLogger(__name__)


class YourSource:
    """Fetches content from YourPlatform."""

    def __init__(self, config: dict):
        """Initialize with config dictionary."""
        self.config = config
        # Extract config fields here

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def fetch(self) -> List[Pebble]:
        """Fetch recent content.
        
        Returns:
            List of Pebble objects
        """
        logger.info("Fetching from YourSource")
        
        try:
            # Your fetching logic here
            # Return list of Pebble(title=..., context=..., url=..., source=...)
            pass
        except Exception as e:
            logger.error(f"Failed to fetch from YourSource: {e}")
            return []

    def close(self):
        """Clean up resources."""
        pass
```

### 3. Register the source

Add to `pebbles/sources/__init__.py`:

```python
from .your_source import YourSource

__all__ = [..., "YourSource"]
```

### 4. Update the config model

Add optional config fields to `pebbles/config.py`:

```python
class SourcesConfig(BaseModel):
    # ... existing sources
    your_source: Optional[YourSourceConfig] = None
```

### 5. Wire it into the engine

Update `pebbles/engine.py` to instantiate your source if configured.

### 6. Write tests

Create tests in `tests/test_sources.py`:

```python
def test_your_source_fetch(mocker):
    """Test YourSource fetches and parses correctly."""
    # Mock HTTP calls
    # Verify Pebble objects returned
    pass
```

---

## Adding a New Delivery Adapter

Delivery adapters send pebbles to recipients via different channels.

### 1. Create the adapter file

```bash
touch pebbles/delivery/your_delivery.py
```

### 2. Implement the adapter class

```python
"""Your delivery adapter description."""

import logging
from ..models import Pebble, Recipient
from ..config import Settings

logger = logging.getLogger(__name__)


class YourDelivery:
    """Delivers pebbles via YourChannel."""

    def __init__(self, settings: Settings):
        """Initialize with settings."""
        self.settings = settings
        # Extract delivery config here

    def send(self, pebble: Pebble, recipient: Recipient) -> bool:
        """Send a pebble to recipient.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Your sending logic here
            logger.info(f"Sent pebble to {recipient.name}: {pebble.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send pebble: {e}")
            return False

    def close(self):
        """Clean up resources."""
        pass
```

### 3. Register the adapter

Add to `pebbles/delivery/__init__.py`:

```python
from .your_delivery import YourDelivery

__all__ = [..., "YourDelivery"]
```

### 4. Update the config and engine

Wire it into delivery logic in `engine.py`.

---

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=pebbles --cov-report=html

# Run specific test file
pytest tests/test_sources.py
```

---

## Pull Request Process

1. Fork the repo and create a feature branch
2. Write tests for your changes
3. Ensure all tests pass (`pytest`)
4. Update documentation (README.md if user-facing)
5. Submit PR with clear description of what changed and why
6. Respond to review feedback

---

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public methods
- Keep functions focused and testable
- Log errors with context

---

## Questions?

Open an issue or start a discussion. We're here to help!