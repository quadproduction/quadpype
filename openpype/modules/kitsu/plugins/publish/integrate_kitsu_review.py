# -*- coding: utf-8 -*-
import re
import gazu
import pyblish.api

from openpype.pipeline.anatomy import Anatomy


class IntegrateKitsuReview(pyblish.api.InstancePlugin):
    """Integrate Kitsu Review"""

    order = pyblish.api.IntegratorOrder + 0.01
    label = "Kitsu Review"
    families = ["render", "image", "online", "plate", "kitsu"]
    optional = True

    def process(self, instance):
        if not getattr(self, 'enabled', True):
            return

        # Check comment has been created
        comment_id = instance.data.get("kitsu_comment", {}).get("id")
        if not comment_id:
            self.log.debug(
                "Comment not created, review not pushed to preview."
            )
            return

        # Add review representations as preview of comment
        task_id = instance.data["kitsu_task"]["id"]
        for representation in instance.data.get("representations", []):
            # Skip if not tagged as review
            if "kitsureview" not in representation.get("tags", []):
                continue

            filenames = representation.get("files")

            export_frames = instance.data.get("exportFrames", [])
            frame_start = instance.data["frameStart"]
            frame_end = instance.data["frameEnd"]

            # If only one frame force a list
            if not isinstance(filenames, list):
                filenames = [filenames]

            extension = representation.get("ext")
            if not extension:
                self.log.warning("No extension found in representation.")
                raise IndexError

            review_path = representation.get("published_path")
            if not review_path:
                self.log.warning("No publish path found in representation.")
                raise IndexError
            self.log.debug("Found review at: {}".format(review_path))

            if not export_frames:
                export_frames = list(range(frame_start, frame_end + 1))

            frame_padding = Anatomy().templates.get('frame_padding', 4)
            frame_file_format = f"{{:0{frame_padding}d}}.{{}}"
            if "burnin" in representation.get("tags", []):
                filenames = [frame_file_format.format(index, extension) for index in export_frames]

            subtract_pattern = rf"\d{{{frame_padding}}}\.{re.escape(extension)}"
            for filename in filenames:
                image_filepath = re.sub(subtract_pattern, filename, review_path)
                self.log.info(image_filepath)

                gazu.task.add_preview(
                    task_id, comment_id, image_filepath, normalize_movie=getattr(self, 'normalize', True)
                )

            self.log.info("Review upload on comment")
