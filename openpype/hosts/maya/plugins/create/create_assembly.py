from quadpype.hosts.maya.api import plugin


class CreateAssembly(plugin.MayaCreator):
    """A grouped package of loaded content"""

    identifier = "io.quadpype.creators.maya.assembly"
    label = "Assembly"
    family = "assembly"
    icon = "cubes"
