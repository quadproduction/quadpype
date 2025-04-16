from pathlib import Path

from quadpype.style import get_default_entity_icon_color
from quadpype.pipeline import load
from quadpype.lib import open_in_explorer


class OpenParentFolder(load.LoaderPlugin):
    """Open file parent folder"""
    representations = ["*"]
    families = ["*"]

    label = "Open Parent Folder"
    order = 25
    icon = "folder"
    color = get_default_entity_icon_color()

    def load(self, context, name=None, namespace=None, data=None):
        path = Path(self.filepath_from_context(context))
        self.log.info("File path '{0}' open in explorer".format(path))

        if path.is_dir():
            open_in_explorer(str(path.resolve()))
        else:
            open_in_explorer(str(path.parent.resolve()))
