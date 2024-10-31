# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
from quadpype.hosts.max.api import plugin
from quadpype.pipeline import CreatedInstance


class CreateRedshiftProxy(plugin.MaxCreator):
    identifier = "io.quadpype.creators.max.redshiftproxy"
    label = "Redshift Proxy"
    family = "redshiftproxy"
    icon = "gear"
