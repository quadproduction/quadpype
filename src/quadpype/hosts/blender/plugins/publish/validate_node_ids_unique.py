from collections import defaultdict

import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError
)
from quadpype.hosts.blender.api.action import SelectInvalidAction, GenerateUUIDsOnInvalidAction
from quadpype.hosts.blender.api.lib import get_id


class ValidateNodeIdsUnique(pyblish.api.InstancePlugin):
    """Validate the nodes in the instance have a unique Id

    Here we ensure that what has been added to the instance is unique
    """

    order = ValidateContentsOrder
    label = 'Non Duplicate IDs'
    hosts = ['blender']
    families = ["model",
                "look",
                "rig",
                "yetiRig"]

    actions = [SelectInvalidAction, GenerateUUIDsOnInvalidAction]

    def process(self, instance):
        """Process all meshes"""

        # Ensure all nodes have a cbId
        invalid = self.get_invalid(instance)
        if invalid:
            names = "\n".join(
                "- {}".format(entity) for entity in invalid
            )
            label = "Entities found with non-unique IDs"
            raise PublishValidationError(
                message="{}: {}".format(label, invalid),
                title="Non-unique ids on nodes",
                description="{}\n- {}".format(label, names)
            )

    @classmethod
    def get_invalid(cls, instance):
        """Return the member nodes that are invalid"""

        # Collect each id with their members
        ids = defaultdict(list)
        for member in instance:
            cls.log.warning(member)
            object_id = get_id(member)
            if not object_id:
                continue
            ids[object_id].append(member)

        # Take only the ids with more than one member
        invalid = list()
        _iteritems = getattr(ids, "iteritems", ids.items)
        for _ids, members in _iteritems():
            if len(members) > 1:
                cls.log.error("ID found on multiple entities : '%s'" % members)
                invalid.extend(members)

        return invalid
