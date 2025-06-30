#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charmed Operator for Pyroscope; a lightweight object storage based profiling backend."""

import logging

from ops.charm import CharmBase

from pyroscope import PyroscopeWorker

logger = logging.getLogger(__name__)


class PyroscopeWorkerCharm(CharmBase):
    """Charmed Operator for Pyroscope; a distributed profiling backend."""

    def __init__(self, *args):
        super().__init__(*args)
        self.worker = PyroscopeWorker(self)


if __name__ == "__main__":  # pragma: nocover
    from ops import main

    main(PyroscopeWorkerCharm)  # noqa
