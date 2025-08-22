from pathlib import Path
import os

from quadpype.pipeline import publish
from quadpype.hosts.photoshop import api as photoshop
from quadpype.settings import get_project_settings


class ExtractJson(publish.Extractor):
    """Extract all layers (groups) marked for publish.

    Usually publishable instance is created as a wrapper of layer(s). For each
    publishable instance so many images as there is 'formats' is created.

    Logic tries to hide/unhide layers minimum times.

    Called once for all publishable instances.
    """

    order = publish.Extractor.order - 0.47
    label = "Extract Json"
    hosts = ["photoshop"]

    formats = ["json"]
    optional = True

    project_name = os.environ['AVALON_PROJECT']
    project_settings = get_project_settings(project_name)

    enabled = project_settings['photoshop']['publish']['ExtractJson']['enabled']

    def process(self, instance):

        if not self.enabled:
            return

        if not instance.data["creator_attributes"].get("extract_json", False):
            return

        staging_dir = self.staging_dir(instance)
        self.log.info("Outputting json to {}".format(staging_dir))

        file_name = "photoshop.json"
        file_path = Path(staging_dir, file_name).as_posix()

        stub = photoshop.stub()
        stub.export_scene_to_json(file_path)

        json_repres = {
            "name": "json",
            "ext": "json",
            "files": file_name,
            "stagingDir": staging_dir,
            "tags": ["json"]
        }
        instance.data.get('representations').append(json_repres)
