from quadpype.hosts.maya.api import plugin


class CreateXgen(plugin.MayaCreator):
    """Xgen"""

    identifier = "io.quadpype.creators.maya.xgen"
    label = "Xgen"
    family = "xgen"
    icon = "pagelines"
