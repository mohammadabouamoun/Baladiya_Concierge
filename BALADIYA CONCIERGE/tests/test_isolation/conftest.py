import pytest

# All tests in test_isolation/ require a live PostgreSQL database
pytestmark = pytest.mark.integration
