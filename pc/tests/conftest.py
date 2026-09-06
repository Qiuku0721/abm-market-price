import sys
from pathlib import Path

# 保证以 pc/ 为工作目录时能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.database import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import app, configure_db_for_tests

    configure_db_for_tests(tmp_path / "api.db")
    with TestClient(app) as c:
        yield c
