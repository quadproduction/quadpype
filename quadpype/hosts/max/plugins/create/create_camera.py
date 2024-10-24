# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
from quadpype.hosts.max.api import plugin


class CreateCamera(plugin.MaxCreator):
    """Creator plugin for Camera."""
    identifier = "io.quadpype.creators.max.camera"
    label = "Camera"
    family = "camera"
    icon = "gear"
