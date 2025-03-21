import pyblish.api
import quadpype.hosts.maya.api.action
from quadpype.pipeline.publish import (
    PublishValidationError,
    ValidateContentsOrder
)


from maya import cmds  # noqa


class ValidateLookContents(pyblish.api.InstancePlugin):
    """Validate look instance contents

    Rules:
        * Look data must have `relationships` and `attributes` keys.
        * At least one relationship must be collection.
        * All relationship object sets at least have an ID value

    Tip:
        * When no node IDs are found on shadingEngines please save your scene
        and try again.

    """

    order = ValidateContentsOrder
    families = ['look']
    hosts = ['maya']
    label = 'Look Data Contents'
    actions = [quadpype.hosts.maya.api.action.SelectInvalidAction]

    def process(self, instance):
        """Process all the nodes in the instance"""

        if not instance[:]:
            raise PublishValidationError("Instance is empty")
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError("'{}' has invalid look "
                               "content".format(instance.name))

    @classmethod
    def get_invalid(cls, instance):
        """Get all invalid nodes"""

        # check if data has the right attributes and content
        attributes = cls.validate_lookdata_attributes(instance)
        # check the looks for ID
        looks = cls.validate_looks(instance)
        # check if file nodes have valid files
        files = cls.validate_files(instance)

        invalid = looks + attributes + files

        return invalid

    @classmethod
    def validate_lookdata_attributes(cls, instance):
        """Check if the lookData has the required attributes

        Args:
            instance

        """

        invalid = set()

        keys = ["relationships", "attributes"]
        lookdata = instance.data["lookData"]
        for key in keys:
            if key not in lookdata:
                cls.log.error("Look Data has no key "
                              "'{}'".format(key))
                invalid.add(instance.name)

        # Validate at least one single relationship is collected
        if not lookdata["relationships"]:
            cls.log.error("Look '%s' has no "
                          "`relationships`" % instance.name)
            invalid.add(instance.name)

        # Check if attributes are on a node with an ID, crucial for rebuild!
        for attr_changes in lookdata["attributes"]:
            if not attr_changes["uuid"] and not attr_changes["attributes"]:
                cls.log.error("Node '%s' has no cbId, please set the "
                              "attributes to its children if it has any"
                              % attr_changes["name"])
                invalid.add(instance.name)

        return list(invalid)

    @classmethod
    def validate_looks(cls, instance):

        looks = instance.data["lookData"]["relationships"]
        invalid = []
        for name, data in looks.items():
            if not data["uuid"]:
                cls.log.error("Look '{}' has no UUID".format(name))
                invalid.append(name)

        return invalid

    @classmethod
    def validate_files(cls, instance):

        invalid = []

        resources = instance.data.get("resources", [])
        for resource in resources:
            files = resource["files"]
            if len(files) == 0:
                node = resource["node"]
                cls.log.error("File node '%s' uses no or non-existing "
                              "files" % node)
                invalid.append(node)

        return invalid

    @classmethod
    def validate_renderer(cls, instance):
        # TODO: Rewrite this to be more specific and configurable
        renderer = cmds.getAttr(
            'defaultRenderGlobals.currentRenderer').lower()
        do_maketx = instance.data.get("maketx", False)
        do_rstex = instance.data.get("rstex", False)
        processors = []

        if do_maketx:
            processors.append('arnold')
        if do_rstex:
            processors.append('redshift')

        for processor in processors:
            if processor == renderer:
                continue
            else:
                cls.log.error("Converted texture does not match current renderer.") # noqa
