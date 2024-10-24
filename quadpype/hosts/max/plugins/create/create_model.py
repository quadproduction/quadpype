# -*- coding: utf-8 -*-
"""Creator plugin for model."""
from quadpype.hosts.max.api import plugin


class CreateModel(plugin.MaxCreator):
    """Creator plugin for Model."""
    identifier = "io.quadpype.creators.max.model"
    label = "Model"
    family = "model"
    icon = "gear"
