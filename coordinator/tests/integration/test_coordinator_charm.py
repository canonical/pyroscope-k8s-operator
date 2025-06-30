import logging
import pytest
from jubilant import Juju, all_blocked
from pathlib import Path
from helpers import PYROSCOPE_APP, PYROSCOPE_RESOURCES

logger = logging.getLogger(__name__)


@pytest.mark.setup
def test_deploy_pyroscope(juju: Juju, coordinator_charm: Path):
    juju.deploy(
        coordinator_charm, PYROSCOPE_APP, resources=PYROSCOPE_RESOURCES, trust=True
    )

    # coordinator will be blocked because of missing s3 and workers integration
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_APP),
        timeout=1000,
        delay=5,
        successes=3,
    )


def test_scale_pyroscope_up_stays_blocked(juju: Juju):
    juju.cli("add-unit", PYROSCOPE_APP, "-n", "1")
    juju.wait(
        lambda status: all_blocked(status, PYROSCOPE_APP),
        timeout=1000,
        delay=5,
        successes=3,
    )


@pytest.mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(PYROSCOPE_APP)
