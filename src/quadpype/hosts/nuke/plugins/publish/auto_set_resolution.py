import pyblish.api

from quadpype.pipeline.settings import extract_width_and_height
from quadpype.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)

from quadpype.hosts.nuke.api.lib import AUTORESIZE_LABEL, get_custom_res


class AutoSetResolution(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validates Output Resolution.

    It is making sure the resolution of write's input is the same as
    Format definition of script in Root node.
    """

    order = pyblish.api.IntegratorOrder - 0.2
    optional = True
    families = ["render"]
    label = "Auto set resolution"
    hosts = ["nuke"]

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        instance_data = instance.data
        resolution_override = instance_data.get("creator_attributes", {}).get('resolution')
        if not resolution_override:
            self.log.warning('Can not find resolution creator attribute from instance data. Process has been aborted.')
            return

        auto_resize_node = self.get_auto_resize_node(instance)
        assert auto_resize_node, "Can not found auto resize node in child nodes."

        width, height = extract_width_and_height(resolution_override)
        if self._resolutions_are_identical(auto_resize_node, width, height):
            self.log.info("Given resolution and node format are identical. Process has been aborted.")
            return

        custom_res_name = get_custom_res(width, height)
        auto_resize_node["format"].setValue(custom_res_name)

        self.log.info(f"Format on auto resize node set to {custom_res_name}")

    @staticmethod
    def _resolutions_are_identical(current_node, width, height):
        write_width = current_node.format().width()
        write_height = current_node.format().height()
        return int(width) == int(write_width) and int(height) == int(write_height)

    @staticmethod
    def get_auto_resize_node(instance):
        child_nodes = (
            instance.data.get("transientData", {}).get("childNodes")
            or instance
        )
        for inode in child_nodes:
            if inode.name() == AUTORESIZE_LABEL:
                return inode

        return
