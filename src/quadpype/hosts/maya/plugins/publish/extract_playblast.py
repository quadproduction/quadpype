import os

import clique

from quadpype.settings import PROJECT_SETTINGS_KEY
from quadpype.pipeline import publish
from quadpype.hosts.maya.api import lib

from maya import cmds
from maya.plugin.evaluator.cache_preferences import CachePreferenceEnabled

class ExtractPlayblast(publish.Extractor):
    """Extract viewport playblast.

    Takes review camera and creates review Quicktime video based on viewport
    capture.

    """

    label = "Extract Playblast"
    hosts = ["maya"]
    families = ["review"]
    optional = True
    capture_preset = {}
    profiles = None

    def process(self, instance):
        self.log.debug("Extracting playblast..")

        # get scene fps
        fps = instance.data.get("fps") or instance.context.data.get("fps")

        # if start and end frames cannot be determined, get them
        # from Maya timeline
        start = instance.data.get("frameStartFtrack")
        end = instance.data.get("frameEndFtrack")
        if start is None:
            start = cmds.playbackOptions(query=True, animationStartTime=True)
        if end is None:
            end = cmds.playbackOptions(query=True, animationEndTime=True)

        self.log.debug("start: {}, end: {}".format(start, end))
        task_data = instance.data["anatomyData"].get("task", {})
        capture_preset = lib.get_capture_preset(
            task_data.get("name"),
            task_data.get("type"),
            instance.data["subset"],
            instance.context.data[PROJECT_SETTINGS_KEY],
            self.log
        )
        stagingdir = self.staging_dir(instance)
        filename = instance.name
        path = os.path.join(stagingdir, filename)
        self.log.debug("Outputting images to %s" % path)
        # get cameras
        camera = instance.data["review_camera"]
        preset = lib.generate_capture_preset(
            instance, camera, path,
            start=start, end=end,
            capture_preset=capture_preset)
        preset["filename"] = path
        preset["overwrite"] = True

        # Bugfix: to avoid playblast generation issues with sequence image plane,
        # cached playblack need to be enabled
        # Firstly, save and switch the anim evaluation mode to parallel
        # (needed for the cached playback option)
        prev_evaluation_mode_info = cmds.evaluationManager(query=True, mode=True)
        # Switch to parallel
        cmds.evaluationManager(mode="parallel")
        # Then, save the current cachedPlayback value to be able to apply it again after playblast capture
        prev_cached_playblast_status = cmds.optionVar(query="cachedPlaybackEnable")
        # Force the value cachedPlayback value to ON
        cmds.optionVar(intValue=("cachedPlaybackEnable", 1))

        cmds.refresh(force=True)

        # Update the engine with the set value
        CachePreferenceEnabled().set_state_from_preference()


        lib.render_capture_preset(preset)

        # Restoring the cached playback option value
        cmds.optionVar(intValue=("cachedPlaybackEnable", int(prev_cached_playblast_status)))

        # Restore anim evaluation mode
        # (directly access index 0 sice it should be a list with a least one value)
        cmds.evaluationManager(mode=prev_evaluation_mode_info[0])

        # Update the engine internal value for the cached playback option

        # Find playblast sequence
        collected_files = os.listdir(stagingdir)
        patterns = [clique.PATTERNS["frames"]]
        collections, remainder = clique.assemble(collected_files,
                                                 minimum_items=1,
                                                 patterns=patterns)

        self.log.debug("Searching playblast collection for: %s", path)
        frame_collection = None
        for collection in collections:
            filebase = collection.format("{head}").rstrip(".")
            self.log.debug("Checking collection head: %s", filebase)
            if filebase in path:
                frame_collection = collection
                self.log.debug(
                    "Found playblast collection: %s", frame_collection
                )

        tags = ["review"]
        if not instance.data.get("keepImages"):
            tags.append("delete")

        # Add camera node name to representation data
        camera_node_name = cmds.listRelatives(camera, parent=True)[0]

        collected_files = list(frame_collection)
        # single frame file shouldn't be in list, only as a string
        if len(collected_files) == 1:
            collected_files = collected_files[0]

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": capture_preset["Codec"]["compression"].lower(),
            "ext": capture_preset["Codec"]["compression"].lower(),
            "files": collected_files,
            "stagingDir": stagingdir,
            "frameStart": int(start),
            "frameEnd": int(end),
            "fps": fps,
            "tags": tags,
            "camera_name": camera_node_name
        }
        instance.data["representations"].append(representation)
