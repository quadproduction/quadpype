from quadpype.hosts.maya.api import plugin
from quadpype.lib import BoolDef


class CreateSetDress(plugin.MayaCreator):
    """A grouped package of loaded content"""

    identifier = "io.quadpype.creators.maya.setdress"
    label = "Set Dress"
    family = "setdress"
    icon = "cubes"
    default_variants = ["Main", "Anim"]

    def get_instance_attr_defs(self):
        return [
            BoolDef("exactSetMembersOnly",
                    label="Exact Set Members Only",
                    default=True)
        ]
