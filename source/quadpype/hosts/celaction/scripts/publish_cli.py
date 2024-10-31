import os
import sys

import pyblish.api
import pyblish.util

import quadpype.hosts.celaction
from quadpype.lib import Logger
from quadpype.tools.utils import host_tools
from quadpype.pipeline import install_quadpype_plugins


log = Logger.get_logger("celaction")

PUBLISH_HOST = "celaction"
HOST_DIR = os.path.dirname(os.path.abspath(quadpype.hosts.celaction.__file__))
PLUGINS_DIR = os.path.join(HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")


def main():
    # Registers pype's Global pyblish plugins
    install_quadpype_plugins()

    if os.path.exists(PUBLISH_PATH):
        log.info(f"Registering path: {PUBLISH_PATH}")
        pyblish.api.register_plugin_path(PUBLISH_PATH)

    pyblish.api.register_host(PUBLISH_HOST)
    pyblish.api.register_target("local")

    return host_tools.show_publish()


if __name__ == "__main__":
    result = main()
    sys.exit(not bool(result))
