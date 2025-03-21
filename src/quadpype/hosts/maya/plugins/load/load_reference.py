import os
import difflib
import contextlib

from maya import cmds
import qargparse

from quadpype.settings import get_project_settings
import quadpype.hosts.maya.api.plugin
from quadpype.hosts.maya.api.lib import (
    maintained_selection,
    get_container_members,
    parent_nodes,
    create_rig_animation_instance
)


@contextlib.contextmanager
def preserve_modelpanel_cameras(container, log=None):
    """Preserve camera members of container in the modelPanels.

    This is used to ensure a camera remains in the modelPanels after updating
    to a new version.

    """

    # Get the modelPanels that used the old camera
    members = get_container_members(container)
    old_cameras = set(cmds.ls(members, type="camera", long=True))
    if not old_cameras:
        # No need to manage anything
        yield
        return

    panel_cameras = {}
    for panel in cmds.getPanel(type="modelPanel"):
        cam = cmds.ls(cmds.modelPanel(panel, query=True, camera=True),
                      long=True)[0]

        # Often but not always maya returns the transform from the
        # modelPanel as opposed to the camera shape, so we convert it
        # to explicitly be the camera shape
        if cmds.nodeType(cam) != "camera":
            cam = cmds.listRelatives(cam,
                                     children=True,
                                     fullPath=True,
                                     type="camera")[0]
        if cam in old_cameras:
            panel_cameras[panel] = cam

    if not panel_cameras:
        # No need to manage anything
        yield
        return

    try:
        yield
    finally:
        new_members = get_container_members(container)
        new_cameras = set(cmds.ls(new_members, type="camera", long=True))
        if not new_cameras:
            return

        for panel, cam_name in panel_cameras.items():
            new_camera = None
            if cam_name in new_cameras:
                new_camera = cam_name
            elif len(new_cameras) == 1:
                new_camera = next(iter(new_cameras))
            else:
                # Multiple cameras in the updated container but not an exact
                # match detected by name. Find the closest match
                matches = difflib.get_close_matches(word=cam_name,
                                                    possibilities=new_cameras,
                                                    n=1)
                if matches:
                    new_camera = matches[0]  # best match
                    if log:
                        log.info("Camera in '{}' restored with "
                                 "closest match camera: {} (before: {})"
                                 .format(panel, new_camera, cam_name))

            if not new_camera:
                # Unable to find the camera to re-apply in the modelpanel
                continue

            cmds.modelPanel(panel, edit=True, camera=new_camera)


class ReferenceLoader(quadpype.hosts.maya.api.plugin.ReferenceLoader):
    """Reference file"""

    families = ["model",
                "pointcache",
                "proxyAbc",
                "animation",
                "mayaAscii",
                "mayaScene",
                "setdress",
                "layout",
                "camera",
                "rig",
                "camerarig",
                "staticMesh",
                "skeletalMesh",
                "mvLook",
                "matchmove"]

    representations = ["ma", "abc", "fbx", "mb"]

    label = "Reference"
    order = -10
    icon = "code-fork"
    color = "orange"

    def process_reference(self, context, name, namespace, options):
        import maya.cmds as cmds

        try:
            family = context["representation"]["context"]["family"]
        except ValueError:
            family = "model"

        project_name = context["project"]["name"]
        # True by default to keep legacy behaviours
        attach_to_root = options.get("attach_to_root", True)
        group_name = options["group_name"]

        # no group shall be created
        if not attach_to_root:
            group_name = namespace

        kwargs = {}
        if "file_options" in options:
            kwargs["options"] = options["file_options"]
        if "file_type" in options:
            kwargs["type"] = options["file_type"]

        path = self.filepath_from_context(context)
        with maintained_selection():
            cmds.loadPlugin("AbcImport.mll", quiet=True)

            file_url = self.prepare_root_value(path, project_name)
            nodes = cmds.file(file_url,
                              namespace=namespace,
                              sharedReferenceFile=False,
                              reference=True,
                              returnNewNodes=True,
                              groupReference=attach_to_root,
                              groupName=group_name,
                              **kwargs)

            shapes = cmds.ls(nodes, shapes=True, long=True)

            new_nodes = (list(set(nodes) - set(shapes)))

            # if there are cameras, try to lock their transforms
            self._lock_camera_transforms(new_nodes)

            current_namespace = cmds.namespaceInfo(currentNamespace=True)

            if current_namespace != ":":
                group_name = current_namespace + ":" + group_name

            self[:] = new_nodes

            if attach_to_root:
                group_name = "|" + group_name
                roots = cmds.listRelatives(group_name,
                                           children=True,
                                           fullPath=True) or []

                if family not in {"layout", "setdress",
                                  "mayaAscii", "mayaScene"}:
                    # QUESTION Why do we need to exclude these families?
                    with parent_nodes(roots, parent=None):
                        cmds.xform(group_name, zeroTransformPivots=True)

                settings = get_project_settings(project_name)

                display_handle = settings['maya']['load'].get(
                    'reference_loader', {}
                ).get('display_handle', True)
                cmds.setAttr(
                    "{}.displayHandle".format(group_name), display_handle
                )

                colors = settings['maya']['load']['colors']
                c = colors.get(family)
                if c is not None:
                    cmds.setAttr("{}.useOutlinerColor".format(group_name), 1)
                    cmds.setAttr("{}.outlinerColor".format(group_name),
                                 (float(c[0]) / 255),
                                 (float(c[1]) / 255),
                                 (float(c[2]) / 255))

                cmds.setAttr(
                    "{}.displayHandle".format(group_name), display_handle
                )
                # get bounding box
                bbox = cmds.exactWorldBoundingBox(group_name)
                # get pivot position on world space
                pivot = cmds.xform(group_name, q=True, sp=True, ws=True)
                # center of bounding box
                cx = (bbox[0] + bbox[3]) / 2
                cy = (bbox[1] + bbox[4]) / 2
                cz = (bbox[2] + bbox[5]) / 2
                # add pivot position to calculate offset
                cx = cx + pivot[0]
                cy = cy + pivot[1]
                cz = cz + pivot[2]
                # set selection handle offset to center of bounding box
                cmds.setAttr("{}.selectHandleX".format(group_name), cx)
                cmds.setAttr("{}.selectHandleY".format(group_name), cy)
                cmds.setAttr("{}.selectHandleZ".format(group_name), cz)

            if family == "rig":
                self._post_process_rig(namespace, context, options)
            else:
                if "translate" in options:
                    if not attach_to_root and new_nodes:
                        root_nodes = cmds.ls(new_nodes, assemblies=True,
                                             long=True)
                        # we assume only a single root is ever loaded
                        group_name = root_nodes[0]
                    cmds.setAttr("{}.translate".format(group_name),
                                 *options["translate"])
            return new_nodes

    def switch(self, container, representation):
        self.update(container, representation)

    def update(self, container, representation):
        with preserve_modelpanel_cameras(container, log=self.log):
            super(ReferenceLoader, self).update(container, representation)

        # We also want to lock camera transforms on any new cameras in the
        # reference or for a camera which might have changed names.
        members = get_container_members(container)
        self._lock_camera_transforms(members)

    def _post_process_rig(self, namespace, context, options):

        nodes = self[:]
        animation_instance = create_rig_animation_instance(
            nodes, context, namespace, options=options, log=self.log
        )
        if animation_instance:
            active = options.get("active")
            if active is not None:
                cmds.setAttr("{}.active".format(animation_instance), active)

    def _lock_camera_transforms(self, nodes):
        cameras = cmds.ls(nodes, type="camera")
        if not cameras:
            return

        # Check the Maya version, lockTransform has been introduced since
        # Maya 2016.5 Ext 2
        version = int(cmds.about(version=True))
        if version >= 2016:
            for camera in cameras:
                cmds.camera(camera, edit=True, lockTransform=True)
        else:
            self.log.warning("This version of Maya does not support locking of"
                             " transforms of cameras.")


class MayaUSDReferenceLoader(ReferenceLoader):
    """Reference USD file to native Maya nodes using MayaUSDImport reference"""

    label = "Reference Maya USD"
    families = ["usd"]
    representations = ["usd"]
    extensions = {"usd", "usda", "usdc"}

    options = ReferenceLoader.options + [
        qargparse.Boolean(
            "readAnimData",
            label="Load anim data",
            default=True,
            help="Load animation data from USD file"
        ),
        qargparse.Boolean(
            "useAsAnimationCache",
            label="Use as animation cache",
            default=True,
            help=(
                "Imports geometry prims with time-sampled point data using a "
                "point-based deformer that references the imported "
                "USD file.\n"
                "This provides better import and playback performance when "
                "importing time-sampled geometry from USD, and should "
                "reduce the weight of the resulting Maya scene."
            )
        ),
        qargparse.Boolean(
            "importInstances",
            label="Import instances",
            default=True,
            help=(
                "Import USD instanced geometries as Maya instanced shapes. "
                "Will flatten the scene otherwise."
            )
        ),
        qargparse.String(
            "primPath",
            label="Prim Path",
            default="/",
            help=(
                "Name of the USD scope where traversing will begin.\n"
                "The prim at the specified primPath (including the prim) will "
                "be imported.\n"
                "Specifying the pseudo-root (/) means you want "
                "to import everything in the file.\n"
                "If the passed prim path is empty, it will first try to "
                "import the defaultPrim for the rootLayer if it exists.\n"
                "Otherwise, it will behave as if the pseudo-root was passed "
                "in."
            )
        )
    ]

    file_type = "USD Import"

    def process_reference(self, context, name, namespace, options):
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)

        def bool_option(key, default):
            # Shorthand for getting optional boolean file option from options
            value = int(bool(options.get(key, default)))
            return "{}={}".format(key, value)

        def string_option(key, default):
            # Shorthand for getting optional string file option from options
            value = str(options.get(key, default))
            return "{}={}".format(key, value)

        options["file_options"] = ";".join([
            string_option("primPath", default="/"),
            bool_option("importInstances", default=True),
            bool_option("useAsAnimationCache", default=True),
            bool_option("readAnimData", default=True),
            # TODO: Expose more parameters
            # "preferredMaterial=none",
            # "importRelativeTextures=Automatic",
            # "useCustomFrameRange=0",
            # "startTime=0",
            # "endTime=0",
            # "importUSDZTextures=0"
        ])
        options["file_type"] = self.file_type

        return super(MayaUSDReferenceLoader, self).process_reference(
            context, name, namespace, options
        )
