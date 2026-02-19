import pyblish.api
import shutil
from pathlib import Path

class ExtractSource(pyblish.api.InstancePlugin):
    """Extract instances sources for traypublisher host to a stagingDir."""

    label = "Extract source"
    order = pyblish.api.ExtractorOrder - 0.5
    hosts = ["traypublisher"]
    families = ["workfile",
                "pointcache",
                "pointcloud",
                "proxyAbc",
                "camera",
                "animation",
                "model",
                "maxScene",
                "mayaAscii",
                "mayaScene",
                "setdress",
                "layout",
                "ass",
                "assProxy",
                "vdbcache",
                "scene",
                "vrayproxy",
                "vrayscene_layer",
                "render",
                "prerender",
                "imagesequence",
                "review",
                "rendersetup",
                "rig",
                "plate",
                "look",
                "ociolook",
                "audio",
                "yetiRig",
                "yeticache",
                "nukenodes",
                "gizmo",
                "source",
                "matchmove",
                "image",
                "assembly",
                "fbx",
                "gltf",
                "textures",
                "action",
                "harmony.template",
                "harmony.palette",
                "background",
                "camerarig",
                "redshiftproxy",
                "effect",
                "xgen",
                "hda",
                "usd",
                "staticMesh",
                "skeletalMesh",
                "mvLook",
                "mvUsd",
                "mvUsdComposition",
                "mvUsdOverride",
                "online",
                "uasset",
                "blendScene",
                "yeticacheUE",
                "tycache",
                "lensDistortion",
                ]

    def process(self, instance):
        dst_staging = Path(instance.data.get("stagingDir"))
        for repre in instance.data.get("representations"):
            repre_files = repre["files"]
            if isinstance(repre_files, str):
                repre_files = [repre_files]

            src_staging = Path(repre["stagingDir"])
            for file in repre_files:
                src_full_path = src_staging / file
                dst_full_path = dst_staging / file
                shutil.copy(src_full_path.resolve(strict=False),
                            dst_full_path.resolve(strict=False))

                self.log.info(f"{file} has been transferred from {src_staging} to {dst_staging}")

            repre["stagingDir"] = dst_staging
            self.log.info(f"stagingDir has been updated to {dst_staging}")
