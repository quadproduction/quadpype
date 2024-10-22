from maya import cmds

import pyblish.api
import quadpype.hosts.maya.api.action
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    OptionalPyblishPluginMixin,
    PublishValidationError
)


def _as_report_list(values, prefix="- ", suffix="\n"):
    """Return list as bullet point list for a report"""
    if not values:
        return ""
    return prefix + (suffix + prefix).join(values)


class ValidateNoUnknownNodes(pyblish.api.InstancePlugin,
                             OptionalPyblishPluginMixin):
    """Checks to see if there are any unknown nodes in the instance.

    This often happens if nodes from plug-ins are used but are not available
    on this machine.

    Note: Some studios use unknown nodes to store data on (as attributes)
        because it's a lightweight node.

    """

    order = ValidateContentsOrder
    hosts = ['maya']
    families = ['model', 'rig']
    optional = True
    label = "Unknown Nodes"
    actions = [quadpype.hosts.maya.api.action.SelectInvalidAction]

    @staticmethod
    def get_invalid(instance):
        return cmds.ls(instance, type='unknown')

    def process(self, instance):
        """Process all the nodes in the instance"""
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "Unknown nodes found:\n\n{0}".format(
                    _as_report_list(sorted(invalid))
                ),
                title="Unknown nodes"
            )
