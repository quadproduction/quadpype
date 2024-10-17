import os
import json
from maya import cmds

from openpype.pipeline import publish
from openpype.hosts.maya.api import lib


class ExtractCameraAlembic(publish.Extractor,
                           publish.OptionalPyblishPluginMixin):
    """Extract a Camera as Alembic.

    The camera gets baked to world space by default. Only when the instance's
    `bakeToWorldSpace` is set to False it will include its full hierarchy.

    'camera' family expects only single camera, if multiple cameras are needed,
    'matchmove' is better choice.

    """

    label = "Extract Camera (Alembic)"
    hosts = ["maya"]
    families = ["camera", "matchmove"]
    bake_attributes = []

    def process(self, instance):

        # Collect the start and end including handles
        start = instance.data["frameStartHandle"]
        end = instance.data["frameEndHandle"]

        step = instance.data.get("step", 1.0)
        bake_to_worldspace = instance.data("bakeToWorldSpace", True)

        # get cameras
        members = instance.data['setMembers']
        cameras = cmds.ls(members, leaf=True, long=True,
                          dag=True, type="camera")

        # validate required settings
        assert isinstance(step, float), "Step must be a float value"

        if not cameras:
            self.log.error("No camera found")
            return

        camera = cameras[0]

        # create focal value dict throught time for blender
        camera_data_dict = {"focal_data": {}}

        for frame in range (start, (end+1)):
            camera_data_dict["focal_data"][frame] = cmds.getAttr('{0}.focalLength'.format(camera), time=frame)

        # Define extract output file path
        dir_path = self.staging_dir(instance)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        filename = "{0}.abc".format(instance.name)
        jsonname = "{0}.json".format(instance.name)
        path = os.path.join(dir_path, filename)
        json_path = os.path.join(dir_path, jsonname)

        # Performe json extraction
        # Serializing json
        json_object = json.dumps(camera_data_dict, indent=4)

        # Writing to json
        with open(json_path, "w") as outfile:
            outfile.write(json_object)

        # Perform alembic extraction
        member_shapes = cmds.ls(
            members, leaf=True, shapes=True, long=True, dag=True)
        with lib.maintained_selection():
            cmds.select(
                member_shapes,
                replace=True, noExpand=True)

            # Enforce forward slashes for AbcExport because we're
            # embedding it into a job string
            path = path.replace("\\", "/")

            job_str = ' -selection -dataFormat "ogawa" '
            job_str += ' -attrPrefix cb'
            job_str += ' -frameRange {0} {1} '.format(start, end)
            job_str += ' -step {0} '.format(step)

            if bake_to_worldspace:
                job_str += ' -worldSpace'

                # if baked, drop the camera hierarchy to maintain
                # clean output and backwards compatibility
                camera_roots = cmds.listRelatives(
                    cameras, parent=True, fullPath=True)
                for camera_root in camera_roots:
                    job_str += ' -root {0}'.format(camera_root)

                for member in members:
                    descendants = cmds.listRelatives(member,
                                                     allDescendents=True,
                                                     fullPath=True) or []
                    shapes = cmds.ls(descendants, shapes=True,
                                     noIntermediate=True, long=True)
                    cameras = cmds.ls(shapes, type="camera", long=True)
                    if cameras:
                        if not set(shapes) - set(cameras):
                            continue
                        self.log.warning((
                            "Camera hierarchy contains additional geometry. "
                            "Extraction will fail.")
                        )
                    transform = cmds.listRelatives(
                        member, parent=True, fullPath=True)
                    transform = transform[0] if transform else member
                    job_str += ' -root {0}'.format(transform)

            job_str += ' -file "{0}"'.format(path)

            # bake specified attributes in preset
            assert isinstance(self.bake_attributes, (list, tuple)), (
                "Attributes to bake must be specified as a list"
            )
            for attr in self.bake_attributes:
                self.log.debug("Adding {} attribute".format(attr))
                job_str += " -attr {0}".format(attr)

            with lib.evaluation("off"):
                with lib.suspended_refresh():
                    cmds.AbcExport(j=job_str, verbose=False)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'abc',
            'ext': 'abc',
            'files': filename,
            "stagingDir": dir_path,
        }
        instance.data["representations"].append(representation)

        json_representation = {
            'name': 'jsonCam',
            'ext': 'json',
            'files': jsonname,
            "stagingDir": dir_path,
        }
        instance.data["representations"].append(json_representation)

        self.log.debug("Extracted instance '{0}' to: {1}\nExtracted instance '{2}' to: {3}".format(
            instance.name, path, jsonname, json_path))
