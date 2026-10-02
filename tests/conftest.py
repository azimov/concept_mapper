from pathlib import Path

import pytest

from concept_mapper.repository import DuckDBRepository

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def repo() -> DuckDBRepository:
    r = DuckDBRepository(csv_dir=str(FIXTURES))
    yield r
    r.close()
