import os
import tempfile
import subprocess

from quadpype.lib import (
    get_ffmpeg_tool_args,
    run_subprocess
)

import pyblish.api

from quadpype.hosts.tvpaint.api.lib import (
    execute_george,
    execute_george_through_file,
)


class ExtractAudioForReview(pyblish.api.Extractor):
    label = "Extract Audio For Review"
    hosts = ["tvpaint"]
    families = ["review", "render"]

    sound_for_review = False
    apply_bg_back_command = False

    def process(self, instance):
        self.sound_for_review = instance.data["creator_attributes"].get("sound_for_review", False)
        if not self.sound_for_review:
            return

        self.log.info(
            "* Processing instance \"{}\"".format(instance.data["label"])
        )
        scene_start_frame = instance.context.data["sceneStartFrame"]

        mark_in = instance.context.data["sceneMarkIn"]
        mark_out = instance.context.data["sceneMarkOut"]
        export_frames = instance.data.get("exportFrames", [])

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

        execute_george("tv_startframe 0")

        # Save to staging dir
        output_dir = instance.data.get("stagingDir")
        if not output_dir:
            # Create temp folder if staging dir is not set
            output_dir = (
                tempfile.mkdtemp(prefix="tvpaint_render_")
            ).replace("\\", "/")
            instance.data["stagingDir"] = output_dir
        else:
            output_dir = output_dir.replace("\\", "/")

        self.log.debug(
            "Files will be rendered to folder: {}".format(output_dir)
        )

        # Special render to get audio from TvPP
        audio_george_script_lines = []
        audio_tv_export = "tv_SaveSequence '\"'export_path'\"' {} {}".format(mark_in, mark_out)
        audio_avi_filepath = os.path.join(
            output_dir,
            "audio_review.avi"
        ).replace("\\", "/")

        audio_george_script_lines.extend([
            "export_path = \"{}\"".format(
                audio_avi_filepath
            ),
            # Necessity to export an AVI, since MP4 not available in script
            "tv_SaveMode \"AVI\" \"MPEG\" 100 \"Sound\"",
            audio_tv_export
        ])

        audio_george_script_lines = "\n".join(audio_george_script_lines)
        execute_george_through_file(audio_george_script_lines)

        # Convert AVI to WAV
        audio_wav_filepath = os.path.join(
            output_dir,
            "audio_review.wav"
        ).replace("\\", "/")

        ffmpeg_args = [
            subprocess.list2cmdline(get_ffmpeg_tool_args("ffmpeg")),
            "-y",
            "-i",
            f"{audio_avi_filepath}",
            "-vn",
            "-c:a",
            "pcm_s16le",
            f"{audio_wav_filepath}"
        ]

        subprcs_cmd = " ".join(ffmpeg_args)
        if os.getenv("SHELL") in ("/bin/bash", "/bin/sh"):
            # Escape parentheses for bash
            subprcs_cmd = (
                subprcs_cmd
                .replace("(", "\\(")
                .replace(")", "\\)")
            )

        # run subprocess
        self.log.debug("Executing: {}".format(subprcs_cmd))
        run_subprocess(subprcs_cmd, shell=True, logger=self.log)

        execute_george("tv_startframe {}".format(scene_start_frame))

        # Audio add to instance
        instance.data["audio"] = [{
            "offset": 0,
            "filename": audio_wav_filepath
        }]
        self.log.debug("Audio Data added to instance ...")
