"""Plugin exporting json file.
"""
import os
import tempfile
import shutil
import json

import pyblish.api
from quadpype.hosts.tvpaint.api import lib
from quadpype.settings import get_project_settings
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin
)


class ExtractJson(pyblish.api.InstancePlugin,
                  OptionalPyblishPluginMixin):
    """ Extract a JSON file and add it to the instance representation.
    """
    order = pyblish.api.ExtractorOrder + 0.01
    label = "Extract JSON"
    hosts = ["tvpaint"]
    family = "render"
    optional = True

    project_name = os.environ['AVALON_PROJECT']
    project_settings = get_project_settings(project_name)

    enabled = project_settings['tvpaint']['publish']['ExtractJson']['enabled']

    def process(self, instance):
        # Create temp folder
        output_dir = (
            tempfile.mkdtemp(prefix="tvpaint_render_")
        ).replace("\\", "/")

        context = instance.context
        context.data["tvpaint_export_json"] = {"stagingDir": output_dir}

        context_data = context.data.get("tvpaint_export_json")

        self.log.info('Extract Json')
        # TODO: george script in list
        george_script_lines = "tv_clipsavestructure \"{}\" \"JSON\" \"onlyvisiblelayers\" \"true\" \"patternfolder\" \"{}\" \"patternfile\" \"{}\"".format(  # noqa
            os.path.join(output_dir, 'tvpaint'), "%ln", "%pfn_%ln.%4ii"
        )

        self.log.debug("Execute: {}".format(george_script_lines))
        lib.execute_george_through_file(george_script_lines)

        raw_json_path = os.path.join(output_dir, 'tvpaint.json')

        instance_layer = [
            layer['name'] for layer in context.data.get('layersData')
        ]

        if context_data.get('instance_layers'):
            context_data['instance_layers'].extend(instance_layer)
        else:
            context_data['instance_layers'] = instance_layer

        json_repres = {
            "name": "json",
            "ext": "json",
            "files": "tvpaint.json",
            "stagingDir": output_dir,
            "tags": ["json"]
        }
        instance.data.get('representations').append(json_repres)
        instance.context.data["cleanupFullPaths"].append(output_dir)

        self.log.debug("Add json representation: {}".format(json_repres))
