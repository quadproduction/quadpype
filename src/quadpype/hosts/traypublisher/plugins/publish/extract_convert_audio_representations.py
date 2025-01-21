from pathlib import Path

import pyblish.api

from quadpype.lib import (
    get_ffmpeg_tool_args,
    run_subprocess,
)
from quadpype.pipeline import publish


class ExtractConvertAudioRepresentations(publish.Extractor):
    """Convert audio representations to the setting specified format."""

    label = "Convert Audio Representations"
    order = pyblish.api.ExtractorOrder + 0.48
    hosts = ["traypublisher"]
    families = ["audio"]

    output_file_type = "wav"

    def process(self, instance):
        representations = instance.data.get("representations")
        if not representations:
            return

        staging_dir = self.staging_dir(instance)
        ffmpeg_tool_args = get_ffmpeg_tool_args("ffmpeg")

        for representation in representations:
            if "thumbnail" in representation.get("tags", []):
                continue

            source_extension = representation["ext"]

            representation: dict
            if representation["ext"] == self.output_file_type:
                # No convertion required, skip.
                continue

            source_filename = representation["files"]
            source_file_path = Path(representation["stagingDir"]).joinpath(source_filename)

            converted_filename = str(Path(source_filename).with_suffix(f'.{self.output_file_type}'))
            converted_file_path = Path(staging_dir).joinpath(converted_filename)

            ffmpeg_args = ffmpeg_tool_args + [
                "-i", source_file_path,
                "-vn", "-ac", "2",
                converted_file_path
            ]

            # Run the convertion
            _output = run_subprocess(ffmpeg_args)

            # Update the representation
            representation.update({
                "ext": self.output_file_type,
                "files": converted_filename,
                "name": self.output_file_type,
                "stagingDir": staging_dir,
            })
