import os
import shutil
import collections
from PIL import Image, ImageChops


def backwards_id_conversion(data_by_layer_id):
    """Convert layer ids to strings from integers."""
    for key in tuple(data_by_layer_id.keys()):
        if not isinstance(key, str):
            data_by_layer_id[str(key)] = data_by_layer_id.pop(key)


def get_frame_filename_template(frame_end, filename_prefix=None, ext=None):
    """Get file template with the frame key for rendered files.

    This is a simple template contains `{frame}{ext}` for sequential outputs
    and `single_file{ext}` for single file output. Output is rendered to
    temporary folder so filename should not matter as integrator change
    them.
    """
    frame_padding = 4
    frame_end_str_len = len(str(frame_end))
    if frame_end_str_len > frame_padding:
        frame_padding = frame_end_str_len

    ext = ext or ".png"
    filename_prefix = filename_prefix or ""

    return "{}{{frame:0>{}}}{}".format(filename_prefix, frame_padding, ext)


def get_layer_pos_filename_template(range_end, filename_prefix=None, ext=None):
    filename_prefix = filename_prefix or ""
    new_filename_prefix = filename_prefix + "pos_{pos}."
    return get_frame_filename_template(range_end, new_filename_prefix, ext)


def _calculate_in_range_frames(
    range_start, range_end,
    exposure_frames, layer_frame_end,
    output_index_by_frame_index
):
    """Calculate frame references in defined range.

    Function may skip whole processing if last layer frame is after range_end.
    In that case post behavior does not make sense.

    Args:
        range_start(int): First frame of range which should be rendered.
        range_end(int): Last frame of range which should be rendered.
        exposure_frames(list): List of all exposure frames on layer.
        layer_frame_end(int): Last frame of layer.
        output_index_by_frame_index(dict): References to already prepared frames
            and where the result will be stored.
    """
    # Calculate in range frames
    in_range_frames = []
    for frame_index in exposure_frames:
        # if the range_start is in between 2 exposure frame
        if range_start > frame_index:
            output_index_by_frame_index[range_start] = frame_index
        if range_start <= frame_index <= range_end:
            output_index_by_frame_index[frame_index] = frame_index
            in_range_frames.append(frame_index)

    if in_range_frames:
        first_in_range_frame = min(in_range_frames)
        # Calculate frames from first exposure frames to range end or last
        #   frame of layer (post-behavior should be calculated since that time)
        previous_exposure = first_in_range_frame
        for frame_index in range(first_in_range_frame, range_end + 1):
            if frame_index > layer_frame_end:
                break

            if frame_index in exposure_frames:
                previous_exposure = frame_index
            else:
                output_index_by_frame_index[frame_index] = previous_exposure

        # There can be frames before the first exposure frame in range
        # First check if we don't already have first range frame filled
        if range_start in output_index_by_frame_index:
            return

    first_exposure_frame = max(exposure_frames)
    last_exposure_frame = max(exposure_frames)
    # Check if is first exposure frame smaller than defined range
    #   if not then skip
    if first_exposure_frame >= range_start:
        return

    # Check is if last exposure frame is also before range start
    #   in that case we can't use fill frames before out range
    if last_exposure_frame < range_start:
        return

    closest_exposure_frame = first_exposure_frame
    for frame_index in exposure_frames:
        if frame_index >= range_start:
            break
        if frame_index > closest_exposure_frame:
            closest_exposure_frame = frame_index

    output_index_by_frame_index[closest_exposure_frame] = closest_exposure_frame
    for frame_index in range(range_start, range_end + 1):
        if frame_index in output_index_by_frame_index:
            break
        output_index_by_frame_index[frame_index] = closest_exposure_frame


def _cleanup_frame_references(output_index_by_frame_index):
    """Cleanup frame references to frame reference.

    Cleanup undirect references to rendered frame.
    ```
    // Example input
    {
        1: 1,
        2: 1,
        3: 2
    }
    // Result
    {
        1: 1,
        2: 1,
        3: 1 // Changed reference to final rendered frame
    }
    ```
    Result is dictionary where keys leads to frame that should be rendered.
    """
    for frame_index in tuple(output_index_by_frame_index.keys()):
        reference_index = output_index_by_frame_index[frame_index]
        # Skip transparent frames
        if reference_index is None or reference_index == frame_index:
            continue

        real_reference_index = reference_index
        _tmp_reference_index = reference_index
        while True:
            _temp = output_index_by_frame_index.get(_tmp_reference_index)
            if not _temp:
                # Key outside the range, skip
                break
            if _temp == _tmp_reference_index:
                real_reference_index = _tmp_reference_index
                break
            _tmp_reference_index = _temp

        if real_reference_index != reference_index:
            output_index_by_frame_index[frame_index] = real_reference_index


def _cleanup_out_range_frames(output_index_by_frame_index, range_start, range_end):
    """Cleanup frame references to frames out of passed range.

    The first available frame in range is used
    ```
    // Example input. Range 2-3
    {
        1: 1,
        2: 1,
        3: 1
    }
    // Result
    {
        2: 2, // Redirect to self as is first that reference out range
        3: 2 // Redirect to first redirected frame
    }
    ```
    Result is dictionary where keys leads to frame that should be rendered.
    """
    in_range_frames_by_out_frames = collections.defaultdict(set)
    out_range_frames = set()
    for frame_index in tuple(output_index_by_frame_index.keys()):
        # Skip frames that are already out of range
        if frame_index < range_start or frame_index > range_end:
            out_range_frames.add(frame_index)
            continue

        reference_index = output_index_by_frame_index[frame_index]
        # Skip transparent frames
        if reference_index is None:
            continue

        # Skip references in range
        if reference_index < range_start or reference_index > range_end:
            in_range_frames_by_out_frames[reference_index].add(frame_index)

    for reference_index in tuple(in_range_frames_by_out_frames.keys()):
        frame_indexes = in_range_frames_by_out_frames.pop(reference_index)
        new_reference = None
        for frame_index in frame_indexes:
            if new_reference is None:
                new_reference = frame_index
            output_index_by_frame_index[frame_index] = new_reference

    # Finally, remove out of range frames
    for frame_index in out_range_frames:
        output_index_by_frame_index.pop(frame_index)


def calculate_frame_indexes_to_copy(fill_mode, frame_count, layer_frame_start, start_frame_index,
                                    end_frame_index, exposure_frame_index, output_indexes_by_frame_index):
    """Fill frame range with frame indexes based on a fill mode
        Args:
            fill_mode(str): Type of fill for the frames to copy
            frame_count(int): frame count (length) for the layer
            layer_frame_start(int): First frame of layer
            start_frame_index(int): Index of the first frame of the range to fill
            end_frame_index(int): Index of the last frame of the range to fill
            exposure_frame_index(list): Exposure frame to use
            output_indexes_by_frame_index(dict): Where result will be stored
    """

    if fill_mode == "none":
        # Just fill all frames with None
        for frame_index in range(start_frame_index, end_frame_index + 1):
            output_indexes_by_frame_index[frame_index] = None
    elif fill_mode == "hold":
        # Keep the exposure frame for whole time
        for frame_index in range(start_frame_index, end_frame_index + 1):
            output_indexes_by_frame_index[frame_index] = exposure_frame_index
    elif fill_mode == "repeat":
        # Repeat the frame range
        for frame_index in range(start_frame_index, end_frame_index + 1):
            output_indexes_by_frame_index[frame_index] = (((frame_index - layer_frame_start) % frame_count) +
                                                          layer_frame_start)
    elif fill_mode == "pingpong":
        # Repeat like a periodic function
        half_period = frame_count - 1
        for frame_index in range(start_frame_index, end_frame_index + 1):
            diff = abs(frame_index - layer_frame_start)
            half_period_count = int(diff / half_period)
            direction = -1 if (half_period_count % 2) else 1
            output_indexes_by_frame_index[frame_index] = (layer_frame_start + (half_period * (half_period_count % 2)) +
                                                          ((diff % half_period) * direction))


def calculate_layer_frame_references(
    range_start, range_end,
    layer_frame_start,
    layer_frame_end,
    exposure_frames,
    pre_beh, post_beh
):
    """Calculate frame references for one layer based on it's data.

    Output is dictionary where key is frame index referencing to rendered frame
    index. If frame index should be rendered then is referencing to self.

    ```
    // Example output
    {
        1: 1, // Reference to self - will be rendered
        2: 1, // Reference to frame 1 - will be copied
        3: 1, // Reference to frame 1 - will be copied
        4: 4, // Reference to self - will be rendered
        ...
        20: 4 // Reference to frame 4 - will be copied
        21: None // Has reference to None - transparent image
    }
    ```

    Args:
        range_start(int): First frame of range which should be rendered.
        range_end(int): Last frame of range which should be rendered.
        layer_frame_start(int)L First frame of layer.
        layer_frame_end(int): Last frame of layer.
        exposure_frames(list): List of all exposure frames on layer.
        pre_beh(str): Pre behavior of layer (enum of 4 strings).
        post_beh(str): Post behavior of layer (enum of 4 strings).
    """
    # Output variable
    output_indexes_by_frame_index = {}
    # Skip if layer does not have any exposure frames
    if not exposure_frames:
        return output_indexes_by_frame_index

    # First calculate in range layer frame indexes
    _calculate_in_range_frames(
        range_start, range_end,
        exposure_frames, layer_frame_end,
        output_indexes_by_frame_index
    )

    frame_count = (layer_frame_end - layer_frame_start) + 1

    # Calculate pre layer start frame indexes
    if layer_frame_start >= range_start and min(exposure_frames) >= range_start:
        calculate_frame_indexes_to_copy(
            fill_mode=pre_beh,
            frame_count=frame_count,
            layer_frame_start=layer_frame_start,
            start_frame_index=range_start,
            end_frame_index=(layer_frame_start - 1),
            exposure_frame_index=min(exposure_frames),
            output_indexes_by_frame_index=output_indexes_by_frame_index
        )

    # Calculate post layer end frame indexes
    if layer_frame_end < range_end and max(exposure_frames) < range_end:
        calculate_frame_indexes_to_copy(
            fill_mode=post_beh,
            frame_count=frame_count,
            layer_frame_start=layer_frame_start,
            start_frame_index=layer_frame_end + 1,
            end_frame_index=range_end,
            exposure_frame_index=max(exposure_frames),
            output_indexes_by_frame_index=output_indexes_by_frame_index
        )

    # Cleanup of referenced frames
    _cleanup_frame_references(output_indexes_by_frame_index)

    # Remove frames out of range
    _cleanup_out_range_frames(output_indexes_by_frame_index, range_start, range_end)

    return output_indexes_by_frame_index


def calculate_layers_extraction_data(
    layers_data,
    exposure_frames_by_layer_id,
    behavior_by_layer_id,
    range_start,
    range_end,
    skip_not_visible=True,
    filename_prefix=None,
    ext=None
):
    """Calculate extraction data for passed layers data.

    ```
    {
        <layer_id>: {
            "frame_references": {...},
            "filenames_by_frame_index": {...}
        },
        ...
    }
    ```

    Frame references contains frame index reference to rendered frame index.

    Filename by frame index represents filename under which should be frame
    stored. Directory is not handled here because each usage may need different
    approach.

    Args:
        layers_data(list): Layers data loaded from TVPaint.
        exposure_frames_by_layer_id(dict): Exposure frames of layers stored by
            layer id.
        behavior_by_layer_id(dict): Pre and Post behavior of layers stored by
            layer id.
        range_start(int): First frame of rendered range.
        range_end(int): Last frame of rendered range.
        skip_not_visible(bool): Skip calculations for hidden layers (Skipped
            by default).
        filename_prefix(str): Prefix before filename.
        ext(str): Extension which filenames will have ('.png' is default).

    Returns:
        dict: Prepared data for rendering by layer position.
    """
    # Make sure layer ids are strings
    #   backwards compatibility when layer ids were integers
    backwards_id_conversion(exposure_frames_by_layer_id)
    backwards_id_conversion(behavior_by_layer_id)

    layer_template = get_layer_pos_filename_template(
        range_end, filename_prefix, ext
    )
    output = {}
    for layer_data in layers_data:
        if skip_not_visible and not layer_data["visible"]:
            continue

        orig_layer_id = layer_data["layer_id"]
        layer_id = str(orig_layer_id)

        # Skip if does not have any exposure frames (empty layer)
        exposure_frames = exposure_frames_by_layer_id[layer_id]
        if not exposure_frames:
            continue

        layer_position = layer_data["position"]
        layer_frame_start = layer_data["frame_start"]
        layer_frame_end = layer_data["frame_end"]

        layer_behavior = behavior_by_layer_id[layer_id]

        pre_behavior = layer_behavior["pre"]
        post_behavior = layer_behavior["post"]

        frame_references = calculate_layer_frame_references(
            range_start, range_end,
            layer_frame_start,
            layer_frame_end,
            exposure_frames,
            pre_behavior, post_behavior
        )
        # All values in 'frame_references' reference to a frame that must be
        #   rendered out
        frames_to_render = set(frame_references.values())
        # Remove 'None' reference (transparent image)
        if None in frames_to_render:
            frames_to_render.remove(None)

        # Skip layer if has nothing to render
        if not frames_to_render:
            continue

        # All filenames that should be as output (not final output)
        filename_frames = (
            set(range(range_start, range_end + 1))
            | frames_to_render
        )
        filenames_by_frame_index = {}
        for frame_index in filename_frames:
            filenames_by_frame_index[frame_index] = layer_template.format(
                pos=layer_position,
                frame=frame_index
            )

        # Store objects under the layer id
        output[orig_layer_id] = {
            "frame_references": frame_references,
            "filenames_by_frame_index": filenames_by_frame_index
        }
    return output


def fill_reference_frames(frame_references, filepath_by_frame_index):
    # Store path to first transparent image if there is any
    for frame_index, ref_index in frame_references.items():
        # Frame referencing to self should be rendered and used as source
        #   and reference indexes with None can't be filled
        if ref_index is None or frame_index == ref_index:
            continue

        # Get destination filepath
        src_filepath = filepath_by_frame_index[ref_index]
        dst_filepath = filepath_by_frame_index[frame_index]

        if hasattr(os, "link"):
            os.link(src_filepath, dst_filepath)


def copy_render_file(src_path, dst_path):
    """Create copy file of an image."""
    if hasattr(os, "link"):
        os.link(src_path, dst_path)
    else:
        shutil.copy(src_path, dst_path)


def cleanup_rendered_layers(filepaths_by_layer_id):
    """Delete all files for each individual layer files after compositing."""
    # Collect all filepaths from data
    all_filepaths = []
    for filepaths_by_frame in filepaths_by_layer_id.values():
        all_filepaths.extend(filepaths_by_frame.values())

    # Loop over loop
    for filepath in set(all_filepaths):
        if filepath is not None and os.path.exists(filepath):
            os.remove(filepath)


def composite_rendered_layers(
    layers_data, filepaths_by_layer_id,
    range_start, range_end,
    dst_filepaths_by_frame, opacity_by_layer_id,
    export_frames=None, cleanup=True
):
    """Composite multiple rendered layers by their position.

    Result is single frame sequence with transparency matching content
    created in TVPaint. Missing source filepaths are replaced with transparent
    images but at least one image must be rendered and exist.

    Function can be used even if single layer was created to fill transparent
    filepaths.

    Args:
        layers_data(list): Layers data loaded from TVPaint.
        filepaths_by_layer_id(dict): Rendered filepaths stored by frame index
            per layer id. Used as source for compositing.
        range_start(int): First frame of rendered range.
        range_end(int): Last frame of rendered range.
        dst_filepaths_by_frame(dict): Output filepaths by frame where final
            image after compositing will be stored. Path must not clash with
            source filepaths.
        opacity_by_layer_id(dict): Opacity stored by layer id (0-255). Used as source for compositing.
        export_frames (list)
        cleanup(bool): Remove all source filepaths when done with compositing.
    """
    layer_ids_by_position = {}
    for layer in layers_data:
        layer_ids_by_position[layer["position"]] = layer["layer_id"]

    sorted_layer_ids_by_position = dict(sorted(layer_ids_by_position.items(), reverse=True))

    # Will store filepaths for transparent images
    transparent_filepaths = set()
    # Store image size to be used for transparent images
    image_size = None

    # Generate composited images
    if export_frames is None:
        export_frames = []

    for frame_index in range(range_start, range_end + 1):
        if export_frames and frame_index not in export_frames:
            continue
        dst_filepath = dst_filepaths_by_frame[frame_index]
        src_files_opacity = {}

        # Create a correlation array to store the required filepath of layers and there opacity
        # This will be used to composite the final image stored to dst_filepath
        for layer_id in sorted_layer_ids_by_position.values():
            cur_filepath = filepaths_by_layer_id[layer_id].get(frame_index)
            if not cur_filepath:
                continue

            src_files_opacity[cur_filepath] = opacity_by_layer_id.get(layer_id, 255)

        # No layers used for this frame index, no image to composite,
        # a transparent one will be generated after
        if not src_files_opacity:
            transparent_filepaths.add(dst_filepath)
            continue

        image_obj = composite_image(src_files_opacity)

        image_obj.save(dst_filepath)

        if image_size is None:
            image_size = image_obj.size

    if not image_size:
        raise ValueError("No image has been composited, this seems like an issue.")

    # Generate transparent images
    if transparent_filepaths:
        transparent_img_obj = Image.new("RGBA", image_size, (0, 0, 0, 0))

        for dst_filepath in transparent_filepaths:
            transparent_img_obj.save(dst_filepath)

    # Remove all files that were used as sources for compositing
    if cleanup:
        cleanup_rendered_layers(filepaths_by_layer_id)


def create_layer_alpha(input_image_file, alpha_value):
    """
    Create a Luminance image based on the image alpha and the tvpp layer opacity
    Args:
        input_image_file(str): path to the image
        alpha_value(int): value of the opacity of the tvpp layer (0-255)
    Returns:
        Image: A luminance image resulting as the true alpha of the tvpp layer
    """
    # Open the input image
    _img_obj = Image.open(input_image_file)
    # Get the alpha channel
    alpha = _img_obj.convert("RGBA").getchannel('A')
    # Create a Luminance image based on the alpha value of the tvpp layer
    layer_alpha_image = Image.new("L", _img_obj.size, alpha_value)
    # Multiply the 2 luminance's images
    return ImageChops.multiply(alpha, layer_alpha_image)


def composite_image(input_files_data):
    """Composite images in order from passed list.
    Raises:
        ValueError: When entered list is empty.
    """
    if not input_files_data:
        raise ValueError("Nothing to composite.")

    composited_image = None
    for file_path, opacity in input_files_data.items():
        image_obj = Image.open(file_path)
        # Create and apply a luminance mask if opacity is not 255 (or 100 in tvpp)
        if opacity < 255:
            image_obj.putalpha(create_layer_alpha(file_path, opacity))
        if composited_image is None:
            composited_image = image_obj
        else:
            composited_image.alpha_composite(image_obj)

    return composited_image


def rename_filepaths_by_frame_start(
    filepaths_by_frame, range_start, range_end, new_frame_start
):
    """Change frames in filenames of finished images to new frame start."""

    # Calculate frame end
    new_frame_end = range_end + (new_frame_start - range_start)
    # Create filename template
    filename_template = get_frame_filename_template(
        max(range_end, new_frame_end)
    )

    # Use different ranges based on Mark In and output Frame Start values
    # - this is to make sure that filename renaming won't affect files that
    #   are not renamed yet
    if range_start < new_frame_start:
        source_range = range(range_end, range_start - 1, -1)
        output_range = range(new_frame_end, new_frame_start - 1, -1)
    else:
        # This is less possible situation as frame start will be in most
        #   cases higher than Mark In.
        source_range = range(range_start, range_end + 1)
        output_range = range(new_frame_start, new_frame_end + 1)

    # Skip if the source first frame is the same as the destination first frame
    new_dst_filepaths = {}
    for src_frame, dst_frame in zip(source_range, output_range):
        if not filepaths_by_frame.get(src_frame):
            continue
        src_filepath = os.path.normpath(filepaths_by_frame[src_frame])
        dirpath, src_filename = os.path.split(src_filepath)
        dst_filename = filename_template.format(frame=dst_frame)
        dst_filepath = os.path.join(dirpath, dst_filename)

        if src_filename != dst_filename:
            os.rename(src_filepath, dst_filepath)

        new_dst_filepaths[dst_frame] = dst_filepath

    return new_dst_filepaths
