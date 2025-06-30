# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import socket
from contextlib import ExitStack, contextmanager
from functools import partial
from unittest.mock import MagicMock, patch

import pytest
from interface_tester import InterfaceTester
from ops.testing import Exec
from scenario.state import Container, State

from charm import PyroscopeWorkerCharm


PYROSCOPE_VERSION_EXEC_OUTPUT = Exec(
    command_prefix=("/usr/bin/pyroscope", "-version"), stdout="1.13.4"
)


@contextmanager
def _urlopen_patch(url: str, resp, tls: bool = False):
    if url == f"{'https' if tls else 'http'}://{socket.getfqdn()}:4040/ready":
        mm = MagicMock()
        mm.read = MagicMock(return_value=resp.encode("utf-8"))
        yield mm
    else:
        raise RuntimeError("unknown path")


@pytest.fixture(autouse=True)
def interface_test_config(interface_tester: InterfaceTester):
    interface_tester.configure(
        # override to use http instead of https, else it asks for ssh key password on every test.
        repo="http://github.com/canonical/charm-relation-interfaces",
        branch="feat/pyroscope_cluster_interface",
    )

    # apply all necessary patches
    with ExitStack() as stack:
        stack.enter_context(patch("lightkube.core.client.GenericSyncClient"))
        stack.enter_context(
            patch(
                "coordinated_workers.worker.Worker._running_worker_config",
                new=lambda _: True,
            )
        )
        stack.enter_context(
            patch("urllib.request.urlopen", new=partial(_urlopen_patch, resp="ready"))
        )

        yield


# Interface tests are centrally hosted at https://github.com/canonical/charm-relation-interfaces.
# this fixture is used by the test runner of charm-relation-interfaces to test pyroscope's compliance
# with the interface specifications.
# DO NOT MOVE OR RENAME THIS FIXTURE! If you need to, you'll need to open a PR on
# https://github.com/canonical/charm-relation-interfaces and change pyroscope's test configuration
# to include the new identifier/location.
@pytest.fixture
def cluster_tester(interface_tester: InterfaceTester):
    interface_tester.configure(
        charm_type=PyroscopeWorkerCharm,
        state_template=State(
            leader=True,
            containers=[
                Container(
                    "pyroscope",
                    can_connect=True,
                    execs={
                        PYROSCOPE_VERSION_EXEC_OUTPUT,
                    },
                )
            ],
        ),
    )
    yield interface_tester
