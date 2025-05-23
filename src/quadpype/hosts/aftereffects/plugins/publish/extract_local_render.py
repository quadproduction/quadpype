import os

from quadpype.pipeline import publish
from quadpype.hosts.aftereffects.api import get_stub


class ExtractLocalRender(publish.Extractor):
    """Render RenderQueue locally."""

    order = publish.Extractor.order - 0.47
    label = "Extract Local Render"
    hosts = ["aftereffects"]
    families = ["renderLocal", "render.local"]

    def process(self, instance):
        stub = get_stub()
        staging_dir = instance.data["stagingDir"]
        self.log.debug("staging_dir::{}".format(staging_dir))

        # pull file name collected value from Render Queue Output module
        if not instance.data["file_names"]:
            raise ValueError("No file extension set in Render Queue")

        comp_id = instance.data['comp_id']
        stub.render(staging_dir, comp_id)

        representations = []
        format = instance.data.get("format", None)
        for file_number, file_name in enumerate(instance.data["file_names"]):
            _, ext = os.path.splitext(os.path.basename(file_name))
            ext = ext[1:].lower()

            first_file_path = None
            files = []

            for found_file_name in os.listdir(staging_dir):

                if not found_file_name.endswith(ext):
                    continue

                self.log.info("found_file_name::{}".format(found_file_name))
                files.append(found_file_name)
                if first_file_path is None:
                    first_file_path = os.path.join(staging_dir,
                                                   found_file_name)

            if not files:
                self.log.info("no files")
                return

            # single file cannot be wrapped in array
            resulting_files = files
            if len(files) == 1:
                resulting_files = files[0]

            # Check if multiple format informations are passed
            if type(instance.data.get("format", None)) is list:
                format = instance.data["format"][file_number]

            repre_data = {
                "frameStart": instance.data["frameStart"],
                "frameEnd": instance.data["frameEnd"],
                "format": format,
                "name": ext,
                "ext": ext,
                "files": resulting_files,
                "stagingDir": staging_dir
            }

            first_repre = not representations
            if instance.data["review"] and first_repre:
                repre_data["tags"] = ["review"]
                # TODO return back when Extract from source same as regular
                thumbnail_path = os.path.join(staging_dir, files[0])
                instance.data["thumbnailSource"] = thumbnail_path

            representations.append(repre_data)

        instance.data["representations"] = representations
