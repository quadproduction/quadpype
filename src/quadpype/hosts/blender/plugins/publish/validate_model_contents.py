import inspect
import bpy

from quadpype.hosts.blender.api import plugin, action

from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishValidationError,
    RepairAction
)

from quadpype.hosts.blender.api import (
    get_resolved_name,
    get_task_collection_template
)

class ValidateModelContents(plugin.BlenderInstancePlugin):
    """Validates Model instance contents.

    A Model instance should have everything that is in the {parent}-{asset} collection
    """

    order = ValidateContentsOrder
    families = ['model']
    hosts = ['blender']
    label = 'Validate Model Contents'

    actions = [action.SelectInvalidAction, RepairAction]

    @staticmethod
    def get_invalid(instance):
        # Get collection template from task/variant
        template = get_task_collection_template(instance.data)
        coll_name = get_resolved_name(instance.data, template)

        # Get collection
        asset_model_coll = bpy.data.collections.get(coll_name)
        if not asset_model_coll:
            raise RuntimeError("No collection found with name :"
                               "{}".format(asset_model_coll))

        asset_model_list = asset_model_coll.objects

        # Get objects in instance
        objects = [obj for obj in instance]

        # Compare obj in instance and obj in scene model collection
        invalid = [missing_obj for missing_obj in asset_model_list if missing_obj not in objects]

        return invalid

    def process(self, instance):

        invalid = self.get_invalid(instance)

        if invalid:
            names = ", ".join(obj.name for obj in invalid)
            raise PublishValidationError(
                "Objects found in collection which are not"
                f" in instance: {names}",
                description=self.get_description()
            )

    @classmethod
    def repair(cls, instance):

        invalid = cls.get_invalid(instance)
        if not invalid:
            return

        instance_object = instance.data.get("transientData").get("instance_node")
        if not instance_object:
            raise RuntimeError ("No instance object found for {}".format(instance.name))

        for object in invalid:
            if isinstance(instance_object, bpy.types.Object):
                object.parent = instance_object
                continue
            instance_object.objects.link(object)

    def get_description(self):
        return inspect.cleandoc(
            """## Some objects are missing in the publish instance.

            Based on the variant name, it appears that all the objects
            in the model collection are not present in the
            publish instance.

            You can either:
            - Select them with the Select Invalid button
            - Auto Repair and put them in the corresponding publish instance
            """
        )
