#!/usr/bin/env python
import os
import sys

from quadpype.pipeline import install_host


def main(env):
    from quadpype.hosts.resolve.utils import setup
    import quadpype.hosts.resolve.api as bmdvr
    # Registers quadpype's Global pyblish plugins
    install_host(bmdvr)
    setup(env)


if __name__ == "__main__":
    result = main(os.environ)
    sys.exit(not bool(result))
