import pytest

# All tests in test_platform/ require a live PostgreSQL database
pytestmark = pytest.mark.integration
