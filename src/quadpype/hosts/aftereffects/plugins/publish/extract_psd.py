import os
import threading

from quadpype.pipeline import publish
from quadpype.hosts.aftereffects.api import get_stub
from quadpype.widgets.message_notification import notify_message
from quadpype.hosts.aftereffects.api.automate import save_frame_dialog_clic


class ExtractCompAsPsd(publish.Extractor):
    """Render PSD Sequence for a comp with layers."""

    order = publish.Extractor.order - 0.47
    label = "Extract Comp as PSD"
    hosts = ["aftereffects"]
    families = ["render"]

    init_path = True
    filename_edit = None

    def process(self, instance):

        if not instance.data["creator_attributes"].get("extract_psd", False):
            return

        representations = instance.data.get("representations", [])

        stub = get_stub()
        self.staging_dir = instance.data["stagingDir"]
        self.log.debug("staging_dir::{}".format(self.staging_dir))

        # pull file name collected value from Render Queue Output module
        if not instance.data["file_names"]:
            raise ValueError("No file extension set in Render Queue")

        comp_id = instance.data['comp_id']
        if not stub.comp_as_layers(comp_id):
            raise ValueError("Sequence for {} doesn't have any layers".format(instance.data.get("name")))

        stub.open_comp_by_id(comp_id)

        duration = (instance.data["frameEnd"] - instance.data["frameStart"]) + 1

        file_name = instance.data.get("name", "temp")
        stub.set_viewer_mode_wire()
        for i in range(duration):
            frame_str = str(i).zfill(4)
            self.base_name = f"{file_name}_{frame_str}"
            auto_clic_thread = self.trigger_auto_clic_thread(
                3,
                False
            )
            stub.save_comp_image_as_with_dialog(comp_id, i)
            auto_clic_thread.join()
            self.init_path = False
        notify_message(
            "AE Export PSD File Succeed",
            "Export has ended with success !"
        )
        stub.set_viewer_mode_adaptive()

        ext = "psd"
        first_file_path = None
        files = []

        for found_file_name in os.listdir(self.staging_dir):

            if not found_file_name.endswith(ext):
                continue

            self.log.info("found_file_name::{}".format(found_file_name))
            files.append(found_file_name)
            if first_file_path is None:
                first_file_path = os.path.join(self.staging_dir,
                                               found_file_name)

        if not files:
            self.log.info("no files")
            return

        # single file cannot be wrapped in array
        resulting_files = files
        if len(files) == 1:
            resulting_files = files[0]

        repre_data = {
            "frameStart": instance.data["frameStart"],
            "frameEnd": instance.data["frameEnd"],
            "name": ext,
            "ext": ext,
            "files": resulting_files,
            "stagingDir": self.staging_dir
        }

        first_repre = not representations
        if (instance.data["review"] and first_repre
                and not instance.data["creator_attributes"].get("bypass_classic_render", False)):
            repre_data["tags"] = ["review"]
            # TODO return back when Extract from source same as regular
            thumbnail_path = os.path.join(self.staging_dir, files[0])
            instance.data["thumbnailSource"] = thumbnail_path

        representations.append(repre_data)

        instance.data["representations"] = representations

    def trigger_auto_clic_thread(self, attempts_number):
        auto_clic_thread = threading.Thread(
            target=self.launch_auto_click,
            args=(attempts_number,)
        )
        auto_clic_thread.start()
        return auto_clic_thread

    def launch_auto_click(self, tries):
        import time
        time.sleep(.5)
        for _ in range(tries):
            success = save_frame_dialog_clic(self.staging_dir, self.base_name, True, self.init_path)
            if success:
                return

        self.log.warning(f"Maximum tries value {tries} reached.")
        notify_message(
            "AE Import File Failed",
            "Auto clic has failed. You will need to end import file process by yourself."
        )
