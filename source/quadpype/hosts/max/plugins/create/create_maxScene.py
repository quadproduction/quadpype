# -*- coding: utf-8 -*-
"""Creator plugin for creating raw max scene."""
from quadpype.hosts.max.api import plugin


class CreateMaxScene(plugin.MaxCreator):
    """Creator plugin for 3ds max scenes."""
    identifier = "io.quadpype.creators.max.maxScene"
    label = "Max Scene"
    family = "maxScene"
    icon = "gear"
