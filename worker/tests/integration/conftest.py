import logging

from pytest import fixture
from tests.integration.helpers import get_worker_charm

logger = logging.getLogger(__name__)


@fixture(scope="session")
def worker_charm():
    """Pyroscope worker charm used for integration testing.

    Build once per session and reuse it in all integration tests to save some minutes/hours.
    You can also set `CHARM_PATH` env variable to use an already existing built charm.
    """
    return get_worker_charm()
