# -*- coding: utf-8 -*-
"""QuadPype startup script."""
from quadpype.pipeline import install_host
from quadpype.hosts.houdini.api import HoudiniHost


def main():
    print("Installing {} ...".format("QuadPype"))
    install_host(HoudiniHost())


main()
