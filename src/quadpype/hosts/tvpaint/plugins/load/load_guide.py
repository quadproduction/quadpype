import math

from quadpype.hosts.tvpaint.api import plugin
from quadpype.hosts.tvpaint.api.lib import execute_george_through_file, get_project_size

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
        'tv_guidelineadd "image" "path" "{0}" "x" {1} "y" {2} "scale" 100\n'
    )

    def load(self, context, name, namespace, options):
        path = self.filepath_from_context(context).replace("\\", "/")
        project_width, project_height = get_project_size()
        position_x = math.ceil(project_width / 2)
        position_y = math.ceil(project_height / 2)
        george_script = self.import_script.format(path, position_x, position_y)
        response = execute_george_through_file(george_script)

        if response is False:
            raise AssertionError(
                "Commande echouée."
            )

        return
