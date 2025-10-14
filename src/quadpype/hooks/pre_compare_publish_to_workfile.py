import os
import re
from pathlib import Path
import shutil
from datetime import datetime, timezone
import copy
from qtpy import QtWidgets

from quadpype.client.mongo.entities import get_last_version_by_subset_name

from quadpype.lib.applications import PreLaunchHook, LaunchTypes

from quadpype.pipeline.publish.lib import get_publish_workfile_representations_from_session
from quadpype.pipeline.publish import get_publish_template_name
from quadpype.pipeline.workfile.path_resolving import get_workdir_from_session
from quadpype.pipeline.workfile.path_resolving import get_workfile_template_key

from quadpype.widgets.message_window import Window
from quadpype.lib import StringTemplate


class ComparePublishToWorkfile(PreLaunchHook):
    """Check if last WorkFile is older than the last Publish.

    If it's the case, this will propose to you to copy the published file as the new version of WorkFile.
    """

    # Execute after workfile template copy
    order = 10
    app_groups = {
        "3dsmax", "adsk_3dsmax",
        "maya",
        "nuke",
        "nukex",
        "hiero",
        "houdini",
        "nukestudio",
        "fusion",
        "blender",
        "photoshop",
        "tvpaint",
        "substancepainter",
        "aftereffects",
        "wrap",
        "openrv"
    }
    launch_types = {LaunchTypes.local}

    def execute(self):

        if not self.data.get("start_last_workfile"):
            self.log.info("It is set to not start last workfile on start.")
            return

        last_workfile = self.data.get("last_workfile_path")
        if not last_workfile:
            self.log.warning("Last workfile was not collected.")
            return

        if not os.path.exists(last_workfile):
            self.log.info("Current context does not have any workfile yet.")
            return

        # Get last WorkFile
        last_workfile_path = Path(last_workfile)
        creation_time = last_workfile_path.stat().st_ctime
        workfile_creation = datetime.fromtimestamp(creation_time, tz=timezone.utc)

        # Get last Published WorkFile
        publish_representations = get_publish_workfile_representations_from_session({
                        "AVALON_PROJECT":self.data["project_name"],
                        "AVALON_TASK": self.data["task_name"],
                        "AVALON_ASSET": self.data["asset_name"]
                    })
        subset = f"workfile{self.data['task_name']}"
        if publish_representations:
            subset = publish_representations[0]["context"]["subset"]

        last_published_repr = get_last_version_by_subset_name(self.data["project_name"],
                                                              subset,
                                                              self.data.get("asset_doc").get("_id"),
                                                              self.data["asset_name"])

        if not last_published_repr:
            self.log.info("No Published Workfile found, continuing.")
            return

        creation_time = last_published_repr["data"]["time"]
        publish_version = last_published_repr["name"]

        try:
            # Retro-compatibility, for published elements before version 4.0.13
            creation_time = datetime.strptime(creation_time, "%Y%m%dT%H%M%SZ")
        except ValueError:
            creation_time = datetime.fromisoformat(creation_time)

        publish_creation = creation_time.astimezone(timezone.utc)

        # Compare creation times
        if publish_creation < workfile_creation:
            self.log.info("Workfile is newer than Published Workfile, continuing")
            return

        else:
            self.log.info("Workfile is older than Published Workfile, do something !")

            parents = {
                widget.objectName(): widget
                for widget in QtWidgets.QApplication.topLevelWidgets()
            }
            msg = (f"The WorkFile:\n {last_workfile} \nis older than the last published file for {self.data['asset_name']} "
                   f"on Task {self.data['task_name']}\n\nWould you like to Copy and Open the most recent Published WF "
                   f"(Click Yes)\nOr Procced with the older workfile on this machine(Click No)")

            ask_window = Window(title="WF older than Published WF",
                                message=msg,
                                parent=parents.get("LauncherWindow"),
                                level="ask")

            if not ask_window.answer:
                return

            # Get new WorkFile Path
            version_template = (self.data.get("anatomy").templates.get("version"))
            parts = re.split(r"\{.*?\}", version_template)
            version_prefix = "".join(parts)

            last_version = self.get_version_from_path(last_workfile, prefix=version_prefix)
            version = last_version + 1

            wf_template_key = get_workfile_template_key(
                self.data["task_name"],
                host_name=self.data["workdir_data"].get("app", None),
                project_name=self.data["project_name"]
            )
            anatomy = self.data.get("anatomy")
            template = anatomy.templates[wf_template_key]["file"]
            wf_data = copy.deepcopy(self.data.get("workdir_data"))
            wf_data["version"] = version
            wf_data["ext"] = last_workfile_path.suffix
            work_filename = self.get_work_file(wf_data, template)

            workdir = get_workdir_from_session(
                {
                    "AVALON_PROJECT": self.data["project_name"],
                    "AVALON_TASK": self.data["task_name"],
                    "AVALON_ASSET": self.data["asset_name"]
                }
                , wf_template_key
            )

            workfile_file_path = os.path.join(os.path.normpath(workdir), work_filename)
            workfile_path = Path(str(workfile_file_path))

            # Compute Published WorkFile Path
            publish_template_key = get_publish_template_name(
                self.data["project_name"],
                self.data["workdir_data"].get("app", None),
                "workfile",
                task_name=self.data["task_name"],
                task_type=self.data["task_name"],
                project_settings=self.data["project_settings"]
            )

            publish_template = anatomy.templates[publish_template_key]
            publish_template_path = os.path.normpath(publish_template["path"])

            publish_data = copy.deepcopy(wf_data)
            publish_data["version"] = publish_version
            publish_data["subset"] = subset
            publish_data["family"] = "workfile"
            publish_data["root"] = anatomy.roots

            publish_file_path = Path(StringTemplate.format_template(
                template=publish_template_path,
                data=publish_data
            )
            )

            if not publish_file_path.exists():
                msg = (
                    f"The Published WorkFile:\n {str(publish_file_path)} \n does not exists on this computer.\n"
                    f"Please check that you downloaded it or if its upload is finished through the sync queue."
                )
                Window(title="title",
                       message=msg,
                       parent=parents.get("LauncherWindow"),
                       level="warning")

                raise ValueError(f"Path {str(publish_file_path)} was not found")

            # Copy and open
            self.launch_context.launch_args.remove(last_workfile)
            shutil.copyfile(str(publish_file_path), str(workfile_path))

            self.data["env"]["AVALON_LAST_WORKFILE"] = str(workfile_path)
            self.data["last_workfile_path"] = str(workfile_path)
            self.launch_context.launch_args.append(str(workfile_path))

        return

    @staticmethod
    def get_work_file(data, template):
        data["ext"] = data["ext"].lstrip(".").lower()
        return StringTemplate.format_template(
            template=template,
            data=data,
        )

    @staticmethod
    def get_version_from_path(path, prefix="v"):
        match = re.search(rf"{prefix}(\d+)", path)
        return int(match.group(1)) if match else None
