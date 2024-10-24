import pyblish.api
import re


class CollectOutputFrameRange(pyblish.api.InstancePlugin):
    """Collect frame start/end from context.

    When instances are collected context does not contain `frameStart` and
    `frameEnd` keys yet. They are collected in global plugin
    `CollectContextEntities`.
    """

    label = "Collect output frame range"
    order = pyblish.api.CollectorOrder + 0.4999
    hosts = ["tvpaint"]
    families = ["review", "render"]

    def process(self, instance):
        asset_doc = instance.data.get("assetEntity")
        if not asset_doc:
            return

        context = instance.context

        frame_start = asset_doc["data"]["frameStart"]
        fps = asset_doc["data"]["fps"]
        frame_end = frame_start + (
            context.data["sceneMarkOut"] - context.data["sceneMarkIn"]
        )
        instance.data["fps"] = fps
        instance.data["frameStart"] = frame_start
        instance.data["frameEnd"] = frame_end
        self.log.info(
            "Set frames {}-{} on instance {} ".format(
                frame_start, frame_end, instance.data["subset"]
            )
        )

        export_frames_selection = instance.data["creator_attributes"].get("export_frames_selection")
        keep_frame_index = instance.data["creator_attributes"].get("keep_frame_index", False)

        # If we want to keep the frame index from the tvpp scene and not recalculate them
        if keep_frame_index:
            frame_start = (instance.context.data["sceneMarkIn"] + instance.context.data["sceneStartFrame"])
            frame_end = (instance.context.data["sceneMarkOut"] + instance.context.data["sceneStartFrame"])
            instance.data["keepFrameIndex"] = keep_frame_index
            instance.data["frameStart"] = frame_start
            instance.data["frameEnd"] = frame_end

        if not export_frames_selection:
            instance.data["exportFrames"] = []
            return

        # Create a list of the frames to render
        export_frames = self.list_frames_to_export(
            export_frames_selection,
            context.data["sceneStartFrame"] + context.data["sceneMarkIn"],
            context.data["sceneStartFrame"] + context.data["sceneMarkOut"],
        )

        start_frame_index = max(asset_doc["data"]["frameStart"], instance.context.data["sceneStartFrame"])
        # Avoid exporting frame before the tracker frameStart or scene sceneStartFrame
        if export_frames[0] < start_frame_index:
            self.log.warning(
                "The custom frames to export start BEFORE the scene Tracking Start Frame or the tvpp scene Start Frame")
            self.log.info("An auto clean will be applied to start at {}".format(start_frame_index))
            # Remove frames lower that the tracker start_frame_index
            export_frames = [frame for frame in export_frames if (frame > start_frame_index)]
            # Insert the true start_frame_index
            export_frames.insert(0, start_frame_index)

        instance.data["exportFrames"] = export_frames

        # Update the instance data
        instance.data["frameStart"] = export_frames[0]
        instance.data["frameEnd"] = export_frames[-1]
        self.log.info("Export Custom frames {}".format(export_frames))

        if keep_frame_index:
            self.log.info("Changed frames Start/End {}-{} on instance {} ".format(instance.data["frameStart"],
                                                                                  instance.data["frameEnd"],
                                                                                  instance.data["subset"]))

    @staticmethod
    def list_frames_to_export(export_frames_selection, start_frame_index, end_frame_index):
        """
        Create a list of frame to export based on a string
        Args:
            export_frames_selection(str): frames to export, can be :
                                "1, 4, 6"
                                "[1-6], 15"
                                "[:-4], 6"
                                "1, 4, [6-:]"
                                the ":" implies that it will go to the mark_in or to the mark_out
            start_frame_index(int)
            end_frame_index(int)
        Returns:
            list: A interpreted list of int based on the str input, sorted
        """
        # Check if custom_frames is correctly written and no illegal character is present
        character_pattern = r'^[\d\[\],: -]+$'
        match = re.fullmatch(character_pattern, export_frames_selection)

        if not match:
            raise ValueError(
                "Unauthorized character(s) found, selection string should contains positive numbers "
                "separated by commas, and you can specify range(s) with the following format: [4-12]\n"
                "In a range you can include all the frame before or after a frame index with the character ':'\n"
                "This is used like this: [:-12] (This will add all frame from the start frame up to "
                "the 12 in the selection)\n"
                "To create a range including all the frame from one specific frame to the end_frame use: [4-:]")

        # Prepare a list to separate each element
        export_frames_selection = re.sub(r'\s+', '', export_frames_selection)
        export_frames_selection_elements = export_frames_selection.split(",")

        export_frames = set()
        for element in export_frames_selection_elements:
            matches = re.findall(r'\[(\d+|:)-(\d+|:)]', element)

            if not matches:
                # First handle classic individual frame selection
                if element in [":", "-"]:
                    raise ValueError("The character '{}' can only be used in the following patterns: "
                                     "'[:-X]' or '[X-:]'".format(element))
                frame_index = int(element)
                if frame_index < 0:
                    raise IndexError("Numbers can't be negatives")

                export_frames.add(frame_index)
                continue

            # Now handle range(s): [X-X] / [:-X] / [X-:]
            # There can be multiple range selections not separated by a comma, this is tolerated
            # (this is why we use a for loop)
            for match_group in matches:
                start_element, end_element = match_group[0], match_group[1]
                if start_element == ':':
                    range_start_frame = start_frame_index
                else:
                    range_start_frame = int(start_element)

                if end_element == ":":
                    range_end_frame = end_frame_index
                else:
                    range_end_frame = int(end_element)

                # Check if the range end frame index is before the start
                if range_end_frame < range_start_frame:
                    raise IndexError(
                        "The range end frame index is lower than the start frame index: "
                        "{} < {}".format(range_end_frame, range_start_frame))

                # Add frame_index in custom_frames_list for frame_index in [X-X]
                for frame_index in range(range_start_frame, range_end_frame + 1):
                    export_frames.add(frame_index)

        return list(sorted(export_frames))
