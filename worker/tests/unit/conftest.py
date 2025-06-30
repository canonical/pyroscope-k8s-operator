from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import socket
import pytest
from ops.testing import Context, Exec, Container
from functools import partial

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


@pytest.fixture
def ctx():
    return Context(charm_type=PyroscopeWorkerCharm)


@pytest.fixture
def pyroscope_container():
    return Container(
        "pyroscope",
        can_connect=True,
        execs={
            PYROSCOPE_VERSION_EXEC_OUTPUT,
        },
    )


@contextmanager
def endpoint_ready(tls: bool = False):
    with patch(
        "urllib.request.urlopen", new=partial(_urlopen_patch, tls=tls, resp="ready")
    ):
        yield


@contextmanager
def config_on_disk():
    with patch(
        "coordinated_workers.worker.Worker._running_worker_config",
        new=lambda _: True,
    ):
        yield
