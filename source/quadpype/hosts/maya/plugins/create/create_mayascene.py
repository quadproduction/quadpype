from quadpype.hosts.maya.api import plugin


class CreateMayaScene(plugin.MayaCreator):
    """Raw Maya Scene file export"""

    identifier = "io.quadpype.creators.maya.mayascene"
    name = "mayaScene"
    label = "Maya Scene"
    family = "mayaScene"
    icon = "file-archive-o"
