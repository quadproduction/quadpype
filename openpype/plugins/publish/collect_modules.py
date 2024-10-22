# -*- coding: utf-8 -*-
"""Collect QuadPype modules."""
from quadpype.modules import ModulesManager
import pyblish.api


class CollectModules(pyblish.api.ContextPlugin):
    """Collect QuadPype modules."""

    order = pyblish.api.CollectorOrder - 0.5
    label = "QuadPype Modules"

    def process(self, context):
        manager = ModulesManager()
        context.data["quadpypeModules"] = manager.modules_by_name
