"""Plugin exporting psd files.
"""
import os
import json
import tempfile
from pathlib import Path

import pyblish.api
from quadpype.settings import get_project_settings
from quadpype.hosts.tvpaint.api import lib


class ExtractPsd(pyblish.api.InstancePlugin):
    order = pyblish.api.ExtractorOrder + 0.02
    label = "Extract PSD"
    hosts = ["tvpaint"]
    families = ["renderLayer", "review", "render"]

    project_name = os.environ['AVALON_PROJECT']
    project_settings = get_project_settings(project_name)

    enabled = project_settings['tvpaint']['publish'][
        'ExtractPsd'].get('enabled', False)

    staging_dir_prefix = "tvpaint_export_json_psd_"

    def process(self, instance):
        if not self.enabled:
            return

        if not instance.data["creator_attributes"].get("extract_psd", False):
            return

        george_script_lines = []
        # Sorting repre to only take the png once
        # This is directly link to the extract process of tvpaint
        repres = [repre for repre in instance.data.get("representations") if repre['name'] == 'png']
        if not repres:
            return

        scene_mark_in = int(instance.context.data["sceneMarkIn"])
        scene_mark_out = int(instance.context.data["sceneMarkOut"])
        output_dir = instance.data.get("stagingDir")

        export_indexes = list(range(scene_mark_in, scene_mark_out+1))

        export_frames_without_offset = instance.data.get("ExportFramesWithoutOffset", [])
        if export_frames_without_offset:
            export_indexes = export_frames_without_offset

        if output_dir:
            # Only convert to a Path object if not None or empty
            output_dir = Path(output_dir)

        if not output_dir or not output_dir.exists():
            # Create temp folder if staging dir is not set
            output_dir = Path(tempfile.mkdtemp(
                prefix=self.staging_dir_prefix).replace("\\", "/"))
            instance.data['stagingDir'] = str(output_dir.resolve())

        new_psd_repres = []
        for repre in repres:
            self.log.info("Processing representation: {}".format(
                json.dumps(repre, sort_keys=True, indent=4)
            ))

            filenames = repre['files']

            if not isinstance(filenames, list):
                filenames = [filenames]

            new_filenames = []
            for frame_index, filename in zip(export_indexes, filenames):
                new_filename = Path(filename).stem
                dst_filepath = output_dir.joinpath(new_filename)
                new_filenames.append(new_filename + '.psd')
                # george command to export psd files for each image
                george_script_lines.append(
                    "tv_clipsavestructure \"{}\" \"PSD\" \"image\" {}".format(
                        dst_filepath.resolve(),
                        frame_index
                    )
                )

            # Convert list to str if there's only one item
            if len(new_filenames) == 1:
                new_filenames = new_filenames[0]

            new_psd_repres.append(
                {
                    "name": "psd",
                    "ext": "psd",
                    "files": new_filenames,
                    "stagingDir": str(output_dir.resolve()),
                    "tags": "psd"
                }
            )

        lib.execute_george_through_file("\n".join(george_script_lines))

        instance.data["representations"].extend(new_psd_repres)

        self.log.info(
            "Representations: {}".format(
                json.dumps(
                    instance.data["representations"], sort_keys=True, indent=4
                )
            )
        )
