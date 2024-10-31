from maya import cmds

import pyblish.api
import quadpype.hosts.maya.api.action
from quadpype.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)


class ValidateShadingEngine(pyblish.api.InstancePlugin,
                            OptionalPyblishPluginMixin):
    """Validate all shading engines are named after the surface material.

    Shading engines should be named "{surface_shader}SG"
    """
    order = ValidateContentsOrder
    families = ["look"]
    hosts = ["maya"]
    label = "Look Shading Engine Naming"
    actions = [
        quadpype.hosts.maya.api.action.SelectInvalidAction, RepairAction
    ]
    optional = True

    # The default connections to check
    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "Found shading engines with incorrect naming:"
                "\n{}".format(invalid)
            )

    @classmethod
    def get_invalid(cls, instance):
        shapes = cmds.ls(instance, type=["nurbsSurface", "mesh"], long=True)
        invalid = []
        for shape in shapes:
            shading_engines = cmds.listConnections(
                shape, destination=True, type="shadingEngine"
            ) or []
            for shading_engine in shading_engines:
                name = (
                    cmds.listConnections(shading_engine + ".surfaceShader")[0]
                    + "SG"
                )
                if shading_engine != name:
                    invalid.append(shading_engine)

        return list(set(invalid))

    @classmethod
    def repair(cls, instance):
        shading_engines = cls.get_invalid(instance)
        for shading_engine in shading_engines:
            name = (
                cmds.listConnections(shading_engine + ".surfaceShader")[0]
                + "SG"
            )
            cmds.rename(shading_engine, name)
