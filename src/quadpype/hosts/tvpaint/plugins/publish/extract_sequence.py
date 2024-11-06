import os
import copy
import tempfile
import speedcopy
import re
from pathlib import Path

from PIL import Image

import pyblish.api

from quadpype.pipeline.publish import (
    KnownPublishError
)
from quadpype.hosts.tvpaint.api.plugin import (
    TVPaintReviewType
)
from quadpype.hosts.tvpaint.api.lib import (
    execute_george,
    execute_george_through_file,
    get_layers_pre_post_behavior,
    get_layers_exposure_frames
)
from quadpype.hosts.tvpaint.lib import (
    calculate_layers_extraction_data,
    get_frame_filename_template,
    fill_reference_frames,
    composite_rendered_layers,
    rename_filepaths_by_frame_start,
    get_layer_pos_filename_template,
)


class ExtractSequence(pyblish.api.Extractor):
    label = "Extract Sequence"
    hosts = ["tvpaint"]
    families = ["review", "render"]

    def process(self, instance):
        self.log.info(
            "* Processing instance \"{}\"".format(instance.data["label"])
        )

        # Get all layers and filter out not visible
        layers = instance.data["layers"]
        filtered_layers = [
            layer
            for layer in layers
            if layer["visible"]
        ]
        layer_names = [str(layer["name"]) for layer in filtered_layers]
        if not layer_names:
            self.log.info(
                "None of the layers from the instance"
                " are visible. Extraction skipped."
            )
            return

        joined_layer_names = ", ".join(
            ["\"{}\"".format(name) for name in layer_names]
        )
        self.log.debug(
            "Instance has {} layers with names: {}".format(
                len(layer_names), joined_layer_names
            )
        )

        ignore_layers_transparency = instance.data.get(
            "ignoreLayersTransparency", False
        )

        # For the scene render subsets, an option has been added to override the ignore_layers_transparency
        # So a "render.scene" subset instance can allow transparency while the global value ignore transparency
        # for the other subsets
        if instance.data["creator_identifier"] == "render.scene":
            ignore_layers_transparency = instance.data["creator_attributes"].get("ignore_layers_transparency", False)

        mark_in = instance.context.data["sceneMarkIn"]
        mark_out = instance.context.data["sceneMarkOut"]
        # Stock the origin marks in case the marks are modified
        origin_mark_in = instance.context.data["sceneMarkIn"]
        origin_mark_out = instance.context.data["sceneMarkOut"]

        # Resolution of the tvpp project (width, height)
        resolution = (instance.context.data["sceneWidth"], instance.context.data["sceneHeight"])

        # Change scene Start Frame to 0 to prevent frame index issues
        #   - issue is that TVPaint versions deal with frame indexes in a
        #     different way when Start Frame is not `0`
        # NOTE It will be set back after rendering
        scene_start_frame = instance.context.data["sceneStartFrame"]
        execute_george("tv_startframe 0")

        # Frame start/end may be stored as float
        frame_start = int(instance.data["frameStart"])

        # Handles are not stored per instance but on Context
        handle_start = instance.context.data["handleStart"]

        scene_bg_color = instance.context.data["sceneBgColor"]

        # Prepare output frames
        output_frame_start = frame_start - handle_start

        # Change output frame start to 0 if handles cause it's negative number
        if output_frame_start < 0:
            self.log.warning((
                "Frame start with handles has negative value."
                " Changed to \"0\". Frames start: {}, Handle Start: {}"
            ).format(frame_start, handle_start))
            output_frame_start = 0

        # Calculate frame end
        output_frame_end = output_frame_start + (mark_out - mark_in)

        # Reduce the mark position in case of user specified a list of frames to export
        export_frames = instance.data.get("exportFrames", [])
        export_frames_without_offset = []

        if export_frames:
            # List of frames to export without the sceneStartFrame offset
            export_frames_without_offset = [(frame - instance.context.data["sceneStartFrame"]) for frame in
                                            export_frames]

            instance.data["ExportFramesWithoutOffset"] = export_frames_without_offset
            if export_frames_without_offset[0] < mark_in:
                instance.data["originFrameStart"] = export_frames[0]
            if export_frames_without_offset[-1] > mark_out:
                instance.data["originFrameEnd"] = export_frames[-1]

            mark_in = export_frames_without_offset[0]
            mark_out = export_frames_without_offset[-1]

        # Save to staging dir
        output_dir = instance.data.get("stagingDir").replace("\\", "/")
        if not output_dir:
            # Create temp folder if staging dir is not set
            output_dir = (
                tempfile.mkdtemp(prefix="tvpaint_render_")
            ).replace("\\", "/")
            instance.data["stagingDir"] = output_dir

        self.log.debug(
            "Files will be rendered to folder: {}".format(output_dir)
        )

        make_playblast = instance.data["creator_attributes"].get("make_playblast", False)
        export_type = instance.data["creator_attributes"].get("export_type", "scene")
        apply_background = instance.data["creator_attributes"].get("apply_background", True)
        is_review = instance.data["family"] == "review"

        if is_review or make_playblast:
            result = self.render_review(
                output_dir,
                export_type,
                mark_in,
                mark_out,
                scene_bg_color if apply_background else None,
                ignore_layers_transparency,
                layers,
                export_frames_without_offset,
                origin_mark_in,
                origin_mark_out
            )
        else:
            # Render output
            result = self.render(
                output_dir,
                mark_in,
                mark_out,
                filtered_layers,
                ignore_layers_transparency,
                apply_background,
                resolution,
                export_frames_without_offset
            )

        output_filepaths_by_frame_index, thumbnail_fullpath = result

        # Change scene frame Start back to previous value
        execute_george("tv_startframe {}".format(scene_start_frame))

        # Sequence of one frame
        if not output_filepaths_by_frame_index:
            self.log.warning("Extractor did not create any output.")
            return

        repre_files = self._rename_output_files(
            output_filepaths_by_frame_index,
            mark_in,
            mark_out,
            output_frame_start
        )

        # Fill tags and new families from project settings
        #instance_families = get_publish_instance_families(instance)
        tags = []
        custom_tags = []
        if "review" in instance.data["families"]:
            tags.append("review")

        # Retrieving review media type, default is video
        review_media_type = instance.data["creator_attributes"].get("review_media_type", None)
        if review_media_type is None:
            review_media_type = TVPaintReviewType(review_media_type)

        # Sequence of one frame
        single_file = len(repre_files) == 1
        if single_file:
            repre_files = repre_files[0]

        # if a custom_mark_range is given, always make the review a seq and not a video
        # It makes no sense to make a video of discontinuous frame range
        if review_media_type == TVPaintReviewType.Seq_Img.name and not single_file:
            if export_frames_without_offset:
                custom_tags.append("extract_frames")
            else:
                custom_tags.append("extract_sequence")

        # Extension is hardcoded
        #   - changing extension would require change code
        new_repre = {
            "name": "png",
            "ext": "png",
            "files": repre_files,
            "stagingDir": output_dir,
            "tags": tags,
            "custom_tags": custom_tags
        }

        if not single_file:
            if not export_frames_without_offset:
                # We only want to add frame start information if it's a sequence without gap
                # Because if frameStart is present in the repr data an index remapping while occur
                # We don't want this in case of list of frames with gap(s)
                new_repre["frameStart"] = output_frame_start
            new_repre["frameEnd"] = output_frame_end

        self.log.debug("Creating new representation: {}".format(new_repre))

        instance.data["representations"].append(new_repre)

        if not thumbnail_fullpath:
            return

        thumbnail_ext = os.path.splitext(
            thumbnail_fullpath
        )[1].replace(".", "")
        # Create thumbnail representation
        thumbnail_repre = {
            "name": "thumbnail",
            "ext": thumbnail_ext,
            "outputName": "thumb",
            "files": os.path.basename(thumbnail_fullpath),
            "stagingDir": output_dir,
            "tags": ["thumbnail"]
        }
        instance.data["representations"].append(thumbnail_repre)

    def _rename_output_files(
        self, filepaths_by_frame, mark_in, mark_out, output_frame_start
    ):
        new_filepaths_by_frame = rename_filepaths_by_frame_start(
            filepaths_by_frame, mark_in, mark_out, output_frame_start
        )

        repre_filenames = []
        for filepath in new_filepaths_by_frame.values():
            repre_filenames.append(os.path.basename(filepath))

        if mark_in < output_frame_start:
            repre_filenames = list(reversed(repre_filenames))

        return repre_filenames

    def render_review(
        self, output_dir, export_type, mark_in, mark_out, scene_bg_color,
        ignore_layers_transparency, layers, export_frames_without_offset, origin_mark_in, origin_mark_out
    ):
        """ Export images from TVPaint using `tv_savesequence` command.

        Args:
            output_dir (str): Directory where files will be stored.
            mark_in (int): Starting frame index from which export will begin.
            mark_out (int): On which frame index export will end.
            scene_bg_color (list): Bg color set in scene. Result of george
                script command `tv_background`.
            ignore_layers_transparency (bool): Layer's opacity will be ignored.
            layers (list): List of layers to be exported.
            export_frames_without_offset (list): List of frame indexes to process, if any is given
            origin_mark_in (int): Original markIn position before modification if custom_mark_range is given
            origin_mark_out (int): Original markOut position before modification if custom_mark_range is given
        Returns:
            tuple: With 2 items first is list of filenames second is path to
                thumbnail.
        """
        filename_template = get_frame_filename_template(mark_out, filename_prefix="review.")

        self.log.debug("Preparing data for rendering.")
        origin_first_filename = filename_template.format(frame=mark_in)
        origin_first_frame_filepath = os.path.join(
            output_dir,
            origin_first_filename
        ).replace("\\", "/")

        george_script_lines = []

        # Set all layers to opacity 100 if ignore_layers_transparency
        if ignore_layers_transparency:
            layers_ids = [layer["layer_id"] for layer in layers]
            layers_ids_max = max(layers_ids)
            layers_ids_min = min(layers_ids)
            george_script_lines.extend([
                "FOR id = {} TO {}".format(layers_ids_min, layers_ids_max),
                "tv_layerset id",
                "set_success = result",
                "IF (CMP(set_success, \"ERROR -1\") == 0)",
                "tv_layerdensity 100",
                "END",
                "END"
            ])

        # Calculate the lenght of the portion to export
        export_lenght = mark_out - mark_in

        # TvPaint seems to consider software markin as frame 0. If we set a frame start at export,
        # it will add the frame start to the markin frame and will add an offset for the rest of the export.
        tv_export = "tv_projectsavesequence '\"'export_path'\"' \"{}\" {} {}".format(export_type, 0, export_lenght)

        george_script_lines.extend([
            "tv_SaveMode \"PNG\"",
            "export_path = \"{}\"".format(
                origin_first_frame_filepath
            ),
            tv_export
        ])

        if scene_bg_color:
            bg_color = self._get_settings_bg_color(review=True)

            # Change bg color to color from settings
            george_script_lines.insert(0, "tv_background \"color\" {} {} {}".format(*bg_color)),

            # Change bg color back to previous scene bg color
            _scene_bg_color = copy.deepcopy(scene_bg_color)
            bg_type = _scene_bg_color.pop(0)
            orig_color_command = [
                "tv_background",
                "\"{}\"".format(bg_type)
            ]
            orig_color_command.extend(_scene_bg_color)

            george_script_lines.append(" ".join(orig_color_command))

        # Put back the origin opacity on each layer
        if ignore_layers_transparency:
            for layer in layers:
                george_script_lines.extend([
                    "tv_layerset {}".format(layer["layer_id"]),
                    "tv_layerdensity {}".format(layer["opacity"]),
                ])

        # Change the mark in place if a selection of frame indexes are specified
        if export_frames_without_offset:
            george_script_lines.insert(0, "tv_markin {}".format(mark_in))
            george_script_lines.insert(0, "tv_markout {}".format(mark_out))
            george_script_lines.extend(["tv_markin {}".format(origin_mark_in)])
            george_script_lines.extend(["tv_markout {}".format(origin_mark_out)])

        george_script_lines = "\n".join(george_script_lines)
        execute_george_through_file(george_script_lines)

        output_filepaths_by_frame_index = {}

        # Check if frames has been properly created on the disk
        for frame_index in range(mark_in, mark_out + 1):
            if export_frames_without_offset and frame_index not in export_frames_without_offset:
                # TODO?: Maybe we should delete from disk the file
                continue

            filename = filename_template.format(frame=frame_index)
            filepath = os.path.join(output_dir, filename)

            output_filepaths_by_frame_index[frame_index] = filepath

            # Ensure the frame has been properly created
            if os.path.exists(filepath):
                continue

            if export_type == "camera" and frame_index == mark_out:
                # There is a bug in TVPaint, it seems to NOT render the last frame in camera mode sometimes

                # TODO: We should recreate a clean george_script_lines with only info to render the last frame
                # Replace the export filepath
                last_frame_filename = filename_template.format(frame=mark_out)
                george_script_lines = re.sub(origin_first_filename, last_frame_filename, george_script_lines)

                # set the mark in to mark_out
                if "tv_markin" not in george_script_lines:
                    george_script_lines = "{}\n{}".format("tv_markin {}".format(mark_out), george_script_lines)
                    george_script_lines = "{}\n{}".format(george_script_lines,
                                                          "tv_markin {}".format(origin_mark_in))
                else:
                    george_script_lines = re.sub("tv_markin {}".format(mark_in),
                                                 "tv_markin {}".format(mark_out),
                                                 george_script_lines, count=1)

                george_script_lines = re.sub(tv_export, tv_export.replace(str(export_lenght), "0"),
                                             george_script_lines)

                execute_george_through_file(george_script_lines)

            # If the frame has still not been generated,
            # this is a true issue we need to crash and notify the user
            if not os.path.exists(filepath):
                raise KnownPublishError("Output ('{}') was not rendered and exported to disk.".format(filepath))

        thumbnail_filepath = None
        if output_filepaths_by_frame_index:
            thumbnail_filepath = os.path.join(output_dir, "thumbnail.jpg")
            source_img = Image.open(next(iter(output_filepaths_by_frame_index.values())))
            if source_img.mode.lower() != "rgb":
                source_img = source_img.convert("RGB")
            source_img.save(thumbnail_filepath)

        return output_filepaths_by_frame_index, thumbnail_filepath

    def render(
        self, output_dir, mark_in, mark_out, layers, ignore_layers_transparency, apply_background, resolution, export_frames
    ):
        """ Export images from TVPaint.

        Args:
            output_dir (str): Directory where files will be stored.
            mark_in (int): Starting frame index from which export will begin.
            mark_out (int): On which frame index export will end.
            layers (list): List of layers to be exported.
            ignore_layers_transparency (bool): Layer's opacity will be ignored.
            apply_background (bool): Apply a bg color to the render set in settings of OP.
            resolution (tuple): Resolution of the tvpaint project (Width, Height).
            export_frames (list)

        Returns:
            tuple: With 2 items first is list of filenames second is path to
                thumbnail.
        """
        self.log.debug("Preparing data for rendering.")

        # Map layers by position
        layers_by_position = {}
        layers_by_id = {}
        layer_ids = []
        for layer in layers:
            if ignore_layers_transparency:
                layer["opacity"] = 100
            layer_id = layer["layer_id"]
            position = layer["position"]
            layers_by_position[position] = layer
            layers_by_id[layer_id] = layer

            layer_ids.append(layer_id)

        # Sort layer positions in reverse order
        sorted_positions = list(reversed(sorted(layers_by_position.keys())))
        if not sorted_positions:
            return [], None

        self.log.debug("Collecting pre/post behavior of individual layers.")
        behavior_by_layer_id = get_layers_pre_post_behavior(layer_ids)
        exposure_frames_by_layer_id = get_layers_exposure_frames(
            layer_ids, layers
        )
        extraction_data_by_layer_id = calculate_layers_extraction_data(
            layers,
            exposure_frames_by_layer_id,
            behavior_by_layer_id,
            mark_in,
            mark_out
        )
        # Render layers
        filepaths_by_layer_id = {}
        opacity_by_layer_id = {}

        # in case some layers are visible, but nothing is rendered,
        # for example, if the post-behavior is on none, and the layer exposure frames
        # are not in the custom_mark_range
        output_used_layers_id = []
        for layer_id, render_data in extraction_data_by_layer_id.items():
            layer = layers_by_id[layer_id]
            output_used_layers_id.append(layer_id)
            filepaths_by_layer_id[layer_id] = self._render_layer(
                render_data, layer, output_dir, export_frames
            )

            opacity_by_layer_id[layer_id] = self._convert_opacity_range(layer["opacity"])

            # filter the layers to compose to remove those who didn't have a render
        filtered_layers = [layer for layer in layers if layer['layer_id'] in output_used_layers_id]

        # Prepare bg image if apply_background enabled
        if apply_background:
            # Create and add to Layers
            bg_layer = {}
            layer_positions = []
            layer_ids = []
            for layer in layers:
                layer_positions.append(layer["position"])
                layer_ids.append(layer["layer_id"])

            bg_position = max(layer_positions) + 1
            bg_id = max(layer_ids) + 1

            bg_layer["frame_end"] = mark_out
            bg_layer["frame_start"] = mark_in
            bg_layer["layer_id"] = bg_id
            bg_layer["position"] = bg_position
            bg_layer["opacity"] = 100
            bg_layer["name"] = "BG_OP_Layer"

            filtered_layers.append(bg_layer)

            # Add to extraction_data_by_layer_id
            filepaths_by_layer_id[bg_id] = self._create_bg_images(bg_layer, output_dir, resolution)
            opacity_by_layer_id[bg_id] = 255

        # Prepare final filepaths where compositing should store the result
        output_filepath_by_frame_index = {}
        thumbnail_src_filepath = None
        finale_template = get_frame_filename_template(mark_out, filename_prefix="render.")
        for frame_index in range(mark_in, mark_out + 1):
            if export_frames and frame_index not in export_frames:
                continue

            filename = finale_template.format(frame=frame_index)

            filepath = os.path.join(output_dir, filename)
            output_filepath_by_frame_index[frame_index] = filepath

            if thumbnail_src_filepath is None:
                thumbnail_src_filepath = filepath

        self.log.info("Started compositing of layer frames.")

        filepath_by_frame_index: dict
        for filepath_by_frame_index in filepaths_by_layer_id.values():
            new_filepath_by_frame_index = self.fill_sequence_gaps(
                filepath_by_frame_index=filepath_by_frame_index,
                start_frame=mark_in,
                end_frame=mark_out
            )
            filepath_by_frame_index.update(new_filepath_by_frame_index)

        composite_rendered_layers(
            filtered_layers, filepaths_by_layer_id,
            mark_in, mark_out,
            output_filepath_by_frame_index,
            opacity_by_layer_id,
            export_frames=export_frames
        )

        self.log.info("Compositing finished")
        thumbnail_filepath = None
        if thumbnail_src_filepath and os.path.exists(thumbnail_src_filepath):
            source_img = Image.open(thumbnail_src_filepath)
            thumbnail_filepath = os.path.join(output_dir, "thumbnail.jpg")
            # Composite background only on rgba images
            # - just making sure
            if source_img.mode.lower() == "rgba":
                bg_color = self._get_settings_bg_color(review=True)
                self.log.debug("Adding thumbnail background color {}.".format(
                    " ".join([str(val) for val in bg_color])
                ))
                bg_image = Image.new("RGBA", source_img.size, bg_color)
                thumbnail_obj = Image.alpha_composite(bg_image, source_img)
                thumbnail_obj.convert("RGB").save(thumbnail_filepath)

            else:
                self.log.info((
                    "Source for thumbnail has mode \"{}\" (Expected: RGBA)."
                    " Can't use thubmanail background color."
                ).format(source_img.mode))
                source_img.save(thumbnail_filepath)

        return output_filepath_by_frame_index, thumbnail_filepath

    def _get_settings_bg_color(self, review=True):
        """Return the review_bg_color set in OP settings if review=True
        else, will return the render_bg_color
        Args:
            review (bool): Must return the review_bg_color or not
        Returns:
            tuple of bg value R, G, B
        """
        red = green = blue = 255
        bg_color = self.review_bg if review else self.render_bg

        if bg_color:
            if len(bg_color) == 4:
                red, green, blue, _ = bg_color
            elif len(bg_color) == 3:
                red, green, blue = bg_color
        return red, green, blue

    def _render_layer(self, render_data, layer, output_dir, export_frames):
        frame_references = render_data["frame_references"]
        filenames_by_frame_index = render_data["filenames_by_frame_index"]

        layer_id = layer["layer_id"]
        george_script_lines = [
            "tv_layerset {}".format(layer_id),
            "tv_SaveMode \"PNG\""
        ]
        filepath_by_frame_index = {}
        frames_to_render = []
        for frame_index, ref_index in frame_references.items():
            # Skip because does not have a ref_index
            if ref_index is None:
                filepath_by_frame_index[frame_index] = None
                continue
            filename = filenames_by_frame_index[frame_index]
            dst_path = "/".join([output_dir, filename])
            filepath_by_frame_index[frame_index] = dst_path

            # Set the ref_index depending on the custom_mark_range given
            # To avoid error if the given frame in custom_mark_range is not a ref_index
            frame_to_render = frame_index
            if frame_index != ref_index:
                if not export_frames:
                    continue
                frame_to_render = ref_index

            frames_to_render.append(str(frame_index))
            # Go to frame
            george_script_lines.append("tv_layerImage {}".format(frame_to_render))
            # Store image to output
            george_script_lines.append("tv_saveimage '{}'".format(dst_path))

        self.log.debug("Rendering Exposure frames {} of layer {} ({})".format(
            ",".join(frames_to_render), layer_id, layer["name"]
        ))
        # Let TVPaint render layer's image
        execute_george_through_file("\n".join(george_script_lines))

        # Fill frames between `frame_start_index` and `frame_end_index` only if no custom_mark_range is given
        self.log.debug("Filling frames not rendered frames.")
        if not export_frames:
            fill_reference_frames(frame_references, filepath_by_frame_index)

        return filepath_by_frame_index

    @staticmethod
    def fill_sequence_gaps(filepath_by_frame_index, start_frame, end_frame):
        """Fill missing files in sequence by duplicating existing ones.
        This will take the nearest frame file and copy it to fill
        gaps in sequence. The last existing file is used to for the
        hole ahead.
        Args:
            filepath_by_frame_index (dict): Dict associating a frame to a filepath.
            start_frame (int): Sequence start (no matter what files are there)
            end_frame (int): Sequence end (no matter what files are there)
        Returns:
            list of added files. Those should be cleaned after work
                is done.
        """
        hole_frame_to_nearest = {}

        # Frame existing in the staging_dir.
        frame_list = [frame for frame, filepath in filepath_by_frame_index.items() if filepath]

        # Frame to not copy if None is present (Pre or Post behavior set to None).
        frame_to_avoid = [frame for frame, filepath in filepath_by_frame_index.items() if not filepath]

        # Set the previous frame as the first of the existing ones.
        prev_frame = frame_list[0]

        for frame in range(int(start_frame), int(end_frame) + 1):
            if frame in frame_to_avoid:
                continue
            # if the frame is in existing ones, set it as the new previous one.
            if frame in frame_list:
                prev_frame = frame
                continue

            # complete the frame to fill.
            hole_frame_to_nearest[frame] = prev_frame

        # Calculate paths
        added_filepath_by_frame_index = {}
        finale_template = get_frame_filename_template(end_frame)

        for hole_frame, src_frame in hole_frame_to_nearest.items():
            src_file_path = filepath_by_frame_index[src_frame]

            hole_file_name = finale_template.format(frame=hole_frame)
            src_file_name = finale_template.format(frame=src_frame)

            hole_file_path = re.sub(src_file_name, hole_file_name, src_file_path)

            if not os.path.isfile(src_file_path):
                raise KnownPublishError(
                    "Missing previously detected file: {}".format(src_file_path))

            speedcopy.copyfile(src_file_path, hole_file_path)
            added_filepath_by_frame_index[hole_frame] = hole_file_path

        return added_filepath_by_frame_index

    def _create_bg_images(self, bg_layer, output_dir, resolution):

        bg_color = self._get_settings_bg_color(review=False)

        filepath_by_frame_index = {}

        layer_template = get_layer_pos_filename_template(range_end=bg_layer["frame_end"])

        for frame_index in range(bg_layer["frame_start"], bg_layer["frame_end"] + 1):
            filename = layer_template.format(pos=bg_layer["position"], frame=frame_index)
            dst_path = Path(output_dir).joinpath(filename)
            filepath_by_frame_index[frame_index] = dst_path

            bg_image = Image.new("RGBA", resolution, bg_color)
            bg_image.save(dst_path, "PNG")

        return filepath_by_frame_index

    @staticmethod
    def _convert_opacity_range(value):
        """
        Convert a value range 0-100 to a value range 0-255 for applying alpha in PIL.Image,
        in the compositing of the final image frame
        Args:
            value(int): value of the alpha 0-100
        Returns:
            Int: New value between 0-255
        """
        return max(0, min(int(round(value * 2.55)), 255))
