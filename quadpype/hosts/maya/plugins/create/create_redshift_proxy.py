# -*- coding: utf-8 -*-
"""Creator of Redshift proxy subset types."""

from quadpype.hosts.maya.api import plugin, lib
from quadpype.lib import BoolDef


class CreateRedshiftProxy(plugin.MayaCreator):
    """Create instance of Redshift Proxy subset."""

    identifier = "io.quadpype.creators.maya.redshiftproxy"
    label = "Redshift Proxy"
    family = "redshiftproxy"
    icon = "gears"

    def get_instance_attr_defs(self):

        defs = [
            BoolDef("animation",
                    label="Export animation",
                    default=False)
        ]

        defs.extend(lib.collect_animation_defs())
        return defs
