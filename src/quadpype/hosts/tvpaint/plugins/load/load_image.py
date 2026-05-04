from quadpype.lib.attribute_definitions import BoolDef
from quadpype.hosts.tvpaint.api import plugin
from quadpype.hosts.tvpaint.api.lib import (
    execute_george_through_file,
    get_layers_data,
    correct_pixel_ratio_after_stretch_load,
    is_image_larger_than_project
)
from quadpype.hosts.tvpaint.api.pipeline import LOADED_ICON


class ImportImage(plugin.Loader):
    """Load image or image sequence to TVPaint as new layer."""

    families = ["render", "image", "background", "plate", "review"]
    representations = ["*"]

    label = "Import Image"
    order = 1
    icon = "image"
    color = "white"

    import_script = (
        "filepath = \"{}\"\n"
        "layer_name = \"{}\"\n"
        "tv_loadsequence filepath {}PARSE layer_id\n"
        "tv_layerrename layer_id layer_name"
    )

    defaults = {
        "stretch": False,
        "timestretch": True,
        "preload": True
    }

    @classmethod
    def get_options(cls, contexts):
        return [
            BoolDef(
                "stretch",
                label="Stretch to project size",
                default=cls.defaults["stretch"],
                tooltip="Stretch loaded image/s to project resolution?"
            ),
            BoolDef(
                "timestretch",
                label="Stretch to timeline length",
                default=cls.defaults["timestretch"],
                tooltip="Clip loaded image/s to timeline length?"
            ),
            BoolDef(
                "preload",
                label="Preload loaded image/s",
                default=cls.defaults["preload"],
                tooltip="Preload image/s?"
            )
        ]

    def load(self, context, name, namespace, options):
        stretch = options.get("stretch", self.defaults["stretch"])
        timestretch = options.get("timestretch", self.defaults["timestretch"])
        preload = options.get("preload", self.defaults["preload"])
        path = self.filepath_from_context(context).replace("\\", "/")

        load_options = []
        if stretch or is_image_larger_than_project(path):
            load_options.append("\"STRETCH\"")
        if timestretch:
            load_options.append("\"TIMESTRETCH\"")
        if preload:
            load_options.append("\"PRELOAD\"")

        load_options_str = ""
        for load_option in load_options:
            load_options_str += (load_option + " ")

        # Prepare layer name
        asset_name = context["asset"]["name"]
        version_name = context["version"]["name"]
        layer_name = "{}{}_{}_v{:0>3}".format(
            LOADED_ICON,
            asset_name,
            name,
            version_name
        )
        # Fill import script with filename and layer name
        # - filename mus not contain backwards slashes

        george_script = self.import_script.format(
            path,
            layer_name,
            load_options_str
        )

        loaded_layer = None
        layers = get_layers_data(
            layer_ids=None,
            communicator=None,
            only_names=True
        )
        for layer in layers:
            if layer["name"] == layer_name:
                loaded_layer = layer
                break

        if loaded_layer is None:
            raise AssertionError(
                "Loading probably failed during execution of george script."
            )

        if stretch or is_image_larger_than_project(path):
            correct_pixel_ratio_after_stretch_load(loaded_layer["layer_id"], path)

        return execute_george_through_file(george_script)
