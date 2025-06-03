import pyblish.api

from quadpype.hosts.aftereffects.api.lib import set_settings
from quadpype.pipeline.settings import extract_width_and_height
from quadpype.pipeline import OptionalPyblishPluginMixin


class AutoSetResolution(OptionalPyblishPluginMixin, pyblish.api.InstancePlugin):
    """Set resolution to given comp as defined by subset
    """

    label = "Auto set resolution"
    hosts = ["aftereffects"]
    order = pyblish.api.Extractor.order - 0.5
    optional = True
    families = ["render.farm", "render.local", "render"]

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        instance_data = instance.data
        resolution_override = instance_data.get("creator_attributes", {}).get('resolution')
        if not resolution_override:
            self.log.warning('Can not find resolution creator attribute from instance data. Process has been aborted.')
            return

        width, height = extract_width_and_height(resolution_override)
        set_settings(
            frames=False,
            resolution=True,
            comp_ids=[instance_data["comp_id"]],
            print_msg=False,
            override_width=width,
            override_height=height
        )

        self.log.info(f"Resolution for comp with '{instance_data['comp_id']}' has been set to '{resolution_override}'.")
