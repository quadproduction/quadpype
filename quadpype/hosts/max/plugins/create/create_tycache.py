# -*- coding: utf-8 -*-
"""Creator plugin for creating TyCache."""
from quadpype.hosts.max.api import plugin


class CreateTyCache(plugin.MaxCreator):
    """Creator plugin for TyCache."""
    identifier = "io.quadpype.creators.max.tycache"
    label = "TyCache"
    family = "tycache"
    icon = "gear"
