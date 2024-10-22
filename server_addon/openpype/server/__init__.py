from ayon_server.addons import BaseServerAddon

from .version import __version__


class QuadPypeAddon(BaseServerAddon):
    name = "quadpype"
    title = "QuadPype"
    version = __version__
