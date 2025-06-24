"""Plugin exporting json file.
"""
import os
import tempfile
import json

import pyblish.api
from quadpype.hosts.tvpaint.api import lib
from quadpype.settings import get_project_settings


class ExtractJson(pyblish.api.ContextPlugin):
    """ Extract a JSON file and add it to the instance representation.
    """
    order = pyblish.api.ExtractorOrder + 0.01
    label = "Extract JSON"
    hosts = ["tvpaint"]
    families = ["imagesequence"]

    project_name = os.environ['AVALON_PROJECT']
    project_settings = get_project_settings(project_name)

    enabled = project_settings['tvpaint']['publish']['ExtractJson']['enabled']

    def process(self, context):
        # Create temp folder
        output_dir = (
            tempfile.mkdtemp(prefix="tvpaint_render_")
        ).replace("\\", "/")

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

        for instance in context:
            if instance.data.get('family') == 'imagesequence':
                instance.data.get('representations').append(json_repres)

        self.log.debug("Add json representation: {}".format(json_repres))

        files_path = self.get_files(raw_json_path)
        for subfolder, files in files_path.items():
            output = os.path.join(output_dir, subfolder)
            if len(files) < 2:
                files = files[0]

            files_repre = {
                "name": subfolder,
                "ext": "png",
                "files": files,
                "stagingDir": output,
                "tags": ["json_png"]
            }
            for instance in context:
                if instance.data.get('family') == "imagesequence":
                    instance.data.get('representations').append(files_repre)
                    self.log.debug("Add json representation: {}".format(files_repre))

    def get_files(self, json_path):
        all_links = {}
        with open(json_path) as tvpaint_json:
            tvpaint_data = json.load(tvpaint_json)

        layers = tvpaint_data['project']['clip']['layers']
        for layer in layers:
            links = [l['file'] for l in layer['link']]
            subfolder = links[0].split('/')[0]
            files = [l.split('/')[-1] for l in links]
            all_links[subfolder] = files

        return all_links
