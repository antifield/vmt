import pytest

from vmt.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(path=str(tmp_path / "test.db"))
    await database.connect()
    yield database
    await database.close()
