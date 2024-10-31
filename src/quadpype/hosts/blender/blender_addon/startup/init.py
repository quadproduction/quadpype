from quadpype.pipeline import install_host
from quadpype.hosts.blender.api import BlenderHost


def register():
    install_host(BlenderHost())


def unregister():
    pass
