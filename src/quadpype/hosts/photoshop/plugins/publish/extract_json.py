from pathlib import Path

from quadpype.pipeline import publish
from quadpype.hosts.photoshop import api as photoshop
from quadpype.pipeline.publish import (
    OptionalPyblishPluginMixin
)

class ExtractJson(publish.Extractor,
                  OptionalPyblishPluginMixin):
    """Extract all layers (groups) marked for publish.

    Usually publishable instance is created as a wrapper of layer(s). For each
    publishable instance so many images as there is 'formats' is created.

    Logic tries to hide/unhide layers minimum times.

    Called once for all publishable instances.
    """

    order = publish.Extractor.order - 0.47
    label = "Extract Json"
    hosts = ["photoshop"]

    families = ["image", "background"]
    formats = ["json"]
    optional = True

    def process(self, instance):
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
