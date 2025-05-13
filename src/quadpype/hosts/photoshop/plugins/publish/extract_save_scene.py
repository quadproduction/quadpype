from quadpype.pipeline import publish
from quadpype.hosts.photoshop import api as photoshop
from pathlib import Path

class ExtractSaveScene(publish.Extractor):
    """Save scene before extraction."""

    order = publish.Extractor.order - 0.49
    label = "Extract Save Scene"
    hosts = ["photoshop"]
    families = ["workfile"]

    def process(self, instance):
        current_path = Path(photoshop.stub().get_active_document_full_name())
        current_ext = current_path.suffix.lstrip('.')

        photoshop.stub().saveAs(str(current_path), current_ext, as_copy=False)
