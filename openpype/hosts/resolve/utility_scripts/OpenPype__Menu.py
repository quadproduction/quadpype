import os
import sys

from quadpype.pipeline import install_host
from quadpype.lib import Logger

log = Logger.get_logger(__name__)


def main(env):
    from quadpype.hosts.resolve.api import ResolveHost, launch_pype_menu

    # activate resolve from quadpype
    host = ResolveHost()
    install_host(host)

    launch_pype_menu()


if __name__ == "__main__":
    result = main(os.environ)
    sys.exit(not bool(result))
