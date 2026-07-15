from quadpype.lib.attribute_definitions import BoolDef
from quadpype.hosts.tvpaint.api import plugin
from quadpype.hosts.tvpaint.api.lib import execute_george_through_file

from quadpype.hosts.tvpaint.api.pipeline import (
    containerise
)

class LoadGuide(plugin.Loader):
    """Load image reference into TVPaint as a Guid."""

    families = ["render", "image", "background", "plate", "review"]
    representations = ["*"]

    label = "Load Image Guide"
    order = 1
    icon = "image"
    color = "yellow"

    size_script = ()

    import_script = (
        'tv_guidelineadd "image" "path" "{0}" "x" 960 "y" 540 "scale" 100\n'
    )

    def load(self, context, name, namespace, options):
        path = self.filepath_from_context(context).replace("\\", "/")

        george_script = self.import_script.format(path)
        response = execute_george_through_file(george_script)

        if response is False:
            raise AssertionError(
                "Commande echouée."
            )

        return
