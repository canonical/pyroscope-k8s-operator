import logging
import pytest
from jubilant import Juju, all_blocked
from pathlib import Path
from helpers import PYROSCOPE_WORKER_APP, PYROSCOPE_RESOURCES

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_deploy_pyroscope_worker(juju: Juju, worker_charm: Path):
    juju.deploy(
        worker_charm, PYROSCOPE_WORKER_APP, resources=PYROSCOPE_RESOURCES, trust=True
    )

    # worker will be blocked because of missing coordinator integration
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_WORKER_APP),
        timeout=1000,
        delay=5,
        successes=3,
    )


def test_scale_worker_up_stays_blocked(juju: Juju):
    juju.cli("add-unit", PYROSCOPE_WORKER_APP, "-n", "1")
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_WORKER_APP),
        timeout=1000,
        delay=5,
        successes=3,
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(PYROSCOPE_WORKER_APP)
