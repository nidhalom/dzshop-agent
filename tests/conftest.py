import pytest

from dzshop.db import Database
from dzshop.offline import OfflineAgent
from dzshop.tools import ShopTools


@pytest.fixture()
def db():
    return Database(":memory:")


@pytest.fixture()
def tools(db):
    return ShopTools(db)


@pytest.fixture()
def agent(db):
    return OfflineAgent(db)
