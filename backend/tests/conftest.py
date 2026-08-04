import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """Fixture to provide a TestClient instance for API tests."""
    with TestClient(app) as c:
        yield c
