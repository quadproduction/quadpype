import clique

import pyblish.api
from quadpype.lib.attribute_definitions import (
    TextDef,
    BoolDef
)

from quadpype.pipeline.publish import QuadPypePyblishPluginMixin
from quadpype.client import (
    get_last_version_by_subset_name,
    get_representations
)


class CollectFramesFixDef(
    pyblish.api.InstancePlugin,
    QuadPypePyblishPluginMixin
):
    """Provides text field to insert frame(s) to be rerendered.

    Published files of last version of an instance subset are collected into
    instance.data["last_version_published_files"]. All these but frames
    mentioned in text field will be reused for new version.

    -> Must have rewrite_version activated for fix to be applied.

    Can also auto-search for missing frames.
    """
    order = pyblish.api.CollectorOrder + 0.495
    label = "Collect Frames to Fix"
    targets = ["local", "farm"]
    hosts = ["nuke"]
    families = ["render", "prerender"]

    rewrite_version_enable = False

    def process(self, instance):
        attribute_values = self.get_attr_values_from_data(instance.data)
        frames_to_fix = attribute_values.get("frames_to_fix")
        auto_fix = attribute_values.get("auto_fix")
        rewrite_version = attribute_values.get("rewrite_version")

        if not rewrite_version:
            self.log.warning(
                "Option Rewrite Last Version disabled, abort Frame To Fix."
            )
            return

        subset_name = instance.data["subset"]
        asset_name = instance.data["asset"]

        project_entity = instance.data["projectEntity"]
        project_name = project_entity["name"]

        version = get_last_version_by_subset_name(
            project_name,
            subset_name,
            asset_name=asset_name
        )
        if not version:
            self.log.warning(
                "No last version found, re-render not possible"
            )
            return

        if self.rewrite_version_enable and rewrite_version:
            instance.data["version"] = version["name"]
            # limits triggering version validator
            instance.data.pop("latestVersion")
            self.log.info(
                f"Instance version switched to {version['name']} to be rewrite"
            )

        representations = get_representations(
            project_name, version_ids=[version["_id"]]
        )
        representations = list(representations)
        published_files = []

        for repre in representations:
            if repre["context"]["family"] not in self.families:
                continue

            for file_info in repre.get("files"):
                published_files.append(file_info["path"])

        instance.data["last_version_published_files"] = published_files
        self.log.debug("last_version_published_files::{}".format(
            instance.data["last_version_published_files"]))


        if not frames_to_fix and not auto_fix:
            self.log.warning(
                "No Frames to fix found, all Frames would be rewrite"
            )
            return

        if (frames_to_fix and auto_fix) or auto_fix:
            frames_to_fix = self._get_auto_frames_to_fix(instance)

        if not frames_to_fix:
            self.log.info(
                f"No Frames to fix found, all frames will be re-written {instance.data['frameStartHandle']}-"
                f"{instance.data['frameEndHandle']}."
            )
            return

        self.log.info(
            f"Frames {frames_to_fix} will be fixed and re-written"
        )
        instance.data["frames_to_fix"] = frames_to_fix
        instance.data["transientData"]["frames_to_fix"] = frames_to_fix

    def _get_auto_frames_to_fix(self, instance):
        """
        Will scan the existing files to retrieve the missing frames
        """
        for repre in instance.data["representations"]:
            if not repre.get("files"):
                raise ValueError("No frames were collected, "
                       "you need to render them once.\n"
                       "Check properties of write node (group) and"
                       "select untoggle 'Rewrite Last Version' option in 'Publish'.")

            if isinstance(repre["files"], str):
                continue

            collections, remainder = clique.assemble(repre["files"])
            self.log.info("collections: {}".format(str(collections)))
            self.log.info("remainder: {}".format(str(remainder)))

            collection = collections[0]

            if len(collections) != 1:
                raise ValueError("There are multiple collections in the folder")

            if not collection.is_contiguous():
                self.log.info("Some frames appear to be missing")
                present_frames = sorted(collection.indexes)
                expected_frames = set(range(instance.data["frameStartHandle"], instance.data["frameEndHandle"] + 1))
                return  self.frames_to_ranges(sorted(expected_frames - set(present_frames)))

            return None

    @staticmethod
    def frames_to_ranges(frames):
        """
        Convert a list of int frames to a string compressed version
        Example : [1,2,3,5,6,7] -> "1-3,5-7"
        """
        if not frames:
            return ""
        frames = sorted(set(frames))
        ranges = []
        start = prev = frames[0]

        for f in frames[1:]:
            if f == prev + 1:
                prev = f
            else:
                if start == prev:
                    ranges.append(f"{start}")
                else:
                    ranges.append(f"{start}-{prev}")
                start = prev = f

        if start == prev:
            ranges.append(f"{start}")
        else:
            ranges.append(f"{start}-{prev}")

        return ",".join(ranges)

    @classmethod
    def get_attribute_defs(cls):
        attributes = [
            TextDef("frames_to_fix", label="Frames to fix",
                    placeholder="5,10-15",
                    regex="[0-9,-]+"),
            BoolDef(
                "auto_fix",
                label="Auto Fix Missing Frames",
                default=False
            )
        ]

        if cls.rewrite_version_enable:
            attributes.append(
                BoolDef(
                    "rewrite_version",
                    label="Rewrite latest version",
                    default=False
                )
            )

        return attributes
