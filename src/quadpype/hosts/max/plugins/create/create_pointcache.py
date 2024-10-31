# -*- coding: utf-8 -*-
"""Creator plugin for creating pointcache alembics."""
from quadpype.hosts.max.api import plugin


class CreatePointCache(plugin.MaxCreator):
    """Creator plugin for Point caches."""
    identifier = "io.quadpype.creators.max.pointcache"
    label = "Point Cache"
    family = "pointcache"
    icon = "gear"
