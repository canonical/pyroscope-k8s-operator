# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from pathlib import Path
import tempfile

from pytest import fixture

from tests.integration.helpers import charm_and_channel_and_resources, SSC_APP
from jubilant import Juju


logger = logging.getLogger(__name__)


@fixture(scope="session")
def coordinator_charm():
    """Pyroscope coordinator used for integration testing."""
    return charm_and_channel_and_resources(
        "coordinator", "COORDINATOR_CHARM_PATH", "COORDINATOR_CHARM_CHANNEL"
    )


@fixture(scope="session")
def worker_charm():
    """Pyroscope worker used for integration testing."""
    return charm_and_channel_and_resources(
        "worker", "WORKER_CHARM_PATH", "WORKER_CHARM_CHANNEL"
    )


@fixture(scope="module")
def ca_cert_path(juju: Juju):
    """Provides a temporary file path to a CA certificate obtained from a deployed self-signed-certificates charm."""
    result = juju.run(f"{SSC_APP}/0", "get-ca-certificate")
    ca_cert = result.results["ca-certificate"]
    tmp_file_path = Path(tempfile.mkstemp(suffix=".pem")[1])
    tmp_file_path.write_text(ca_cert)

    yield tmp_file_path

    tmp_file_path.unlink(missing_ok=True)
