import pyblish.api

from quadpype.hosts.nuke import api as napi
from quadpype.pipeline.publish import RepairAction
from quadpype.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from quadpype.pipeline.settings import extract_width_and_height
from quadpype.hosts.nuke.api.lib import AUTORESIZE_LABEL, get_custom_res

import nuke


class ValidateOutputResolution(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validates Output Resolution.

    It is making sure the resolution of write's input is the same as
    Format definition of script in Root node.
    """

    order = pyblish.api.ValidatorOrder
    optional = True
    families = ["render"]
    label = "Validate Write resolution"
    hosts = ["nuke"]
    actions = [RepairAction]

    missing_msg = "Missing Reformat node in render group node"
    resolution_msg = "Reformat is set to wrong format"

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        publish_attributes = instance.data.get("publish_attributes")
        auto_set_resolution_state = publish_attributes.get("AutoSetResolution", {}).get("active", None)
        if auto_set_resolution_state is True:
            self.log.info("Bypassing output resolution validator because auto set resolution is active.")

        resolution_override = instance.data.get("creator_attributes", {}).get('resolution', None)
        if resolution_override:
            self.log.info("Will consider resolution override from render creator as defined by user to compare with.")

        invalid = self.get_invalid(
            instance=instance,
            resolution_override=resolution_override,
            node_name=AUTORESIZE_LABEL if resolution_override else None
        )
        if invalid:
            raise PublishXmlValidationError(self, invalid)

    @classmethod
    def get_reformat(cls, instance, node_name=None):
        child_nodes = (
            instance.data.get("transientData", {}).get("childNodes")
            or instance
        )

        for inode in child_nodes:
            if inode.Class() == "Reformat" and cls._name_is_correct(inode, node_name):
                return inode

        return None

    @staticmethod
    def _name_is_correct(node, node_name):
        return node_name is None or node.name() == node_name

    @classmethod
    def get_invalid(cls, instance, resolution_override=None, node_name=None):
        def _check_resolution(instance, reformat, resolution_override):
            if resolution_override:
                root_width, root_height = extract_width_and_height(resolution_override)
            else:
                root_width = instance.data["resolutionWidth"]
                root_height = instance.data["resolutionHeight"]

            write_width = reformat.format().width()
            write_height = reformat.format().height()

            if (root_width != write_width) or (root_height != write_height):
                return None
            else:
                return True

        # check if reformat is in render node
        reformat = cls.get_reformat(instance, node_name)
        if not reformat:
            return cls.missing_msg

        # check if reformat is set to correct root format
        correct_format = _check_resolution(instance, reformat, resolution_override)
        if not correct_format:
            return cls.resolution_msg

    @classmethod
    def repair(cls, instance):
        child_nodes = (
            instance.data.get("transientData", {}).get("childNodes")
            or instance
        )

        invalid = cls.get_invalid(instance)
        grp_node = instance.data["transientData"]["node"]

        if cls.missing_msg == invalid:
            # make sure we are inside of the group node
            with grp_node:
                # find input node and select it
                _input = None
                for inode in child_nodes:
                    if inode.Class() != "Input":
                        continue
                    _input = inode

                # add reformat node under it
                with napi.maintained_selection():
                    _input['selected'].setValue(True)
                    _rfn = nuke.createNode("Reformat", "name Reformat01")
                    _rfn["resize"].setValue(0)
                    _rfn["black_outside"].setValue(1)

                cls.log.info("Adding reformat node")

        if cls.resolution_msg == invalid:
            nuke_format = nuke.root()["format"].value()

            resolution_override = instance.data.get("creator_attributes", {}).get('resolution', None)
            if resolution_override:
                root_width, root_height = extract_width_and_height(resolution_override)
                nuke_format = get_custom_res(root_width, root_height)

            reformat = cls.get_reformat(instance)
            reformat["format"].setValue(nuke_format)
            cls.log.info(f"Fixing reformat to {nuke_format}")
