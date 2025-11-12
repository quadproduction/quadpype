import os
import re
from pathlib import Path
import shutil
from datetime import datetime, timezone
import copy
from qtpy import QtWidgets

from quadpype.client.mongo.entities import get_version_by_id

from quadpype.pipeline.publish.lib import get_last_publish_workfile_representation

from quadpype.lib.applications import PreLaunchHook, LaunchTypes
from quadpype.tools.utils.workfile_cache import WorkFileCache

from quadpype.modules.sync_server.sync_server import download_last_published_workfile
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

        sync_server = self.modules_manager.get("sync_server")
        if not sync_server or not sync_server.enabled:
            self.log.debug("Sync server module is not enabled or available")
            return

        # Get data
        project_name = self.data["project_name"]
        asset_name = self.data["asset_name"]
        task_name = self.data["task_name"]
        task_type = self.data["task_type"]
        host_name = self.application.host_name
        anatomy = self.data.get("anatomy")

        # Get last WorkFile
        last_workfile_path = Path(last_workfile)
        creation_time = last_workfile_path.stat().st_ctime
        workfile_creation = datetime.fromtimestamp(creation_time, tz=timezone.utc)

        # Get last Published WorkFile Representation
        self.log.info("Trying to fetch last published workfile from MongoDB...")

        context_filters = {
            "asset": asset_name,
            "family": "workfile",
            "task": {"name": task_name, "type": task_type}
        }

        # Add version filter
        workfile_version = self.launch_context.data.get("workfile_version", -1)

        if workfile_version > 0 and workfile_version not in {None, "last"}:
            context_filters["version"] = self.launch_context.data[
                "workfile_version"
            ]

            # Only one version will be matched
            version_index = 0
        else:
            version_index = workfile_version

        published_workfile_representation = get_last_publish_workfile_representation(project_name,
                                                                                     context_filters,
                                                                                     version_index)

        if not published_workfile_representation:
            return

        # Get the Version representation associated for time comparison
        published_workfile_version_repre = get_version_by_id(project_name,
                                                             published_workfile_representation["parent"],
                                                             ["data"])

        creation_time = published_workfile_version_repre["data"]["time"]

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
        version_template = self.data.get("anatomy").templates.get("version")
        parts = re.split(r"\{.*?\}", version_template)
        version_prefix = "".join(parts)

        last_version = self.get_version_from_path(last_workfile, prefix=version_prefix)
        version = last_version + 1

        wf_template_key = get_workfile_template_key(
            task_name,
            host_name=self.data["workdir_data"].get("app", None),
            project_name=project_name
        )

        template = anatomy.templates[wf_template_key]["file"]
        wf_data = copy.deepcopy(self.data.get("workdir_data"))
        wf_data["version"] = version
        wf_data["ext"] = last_workfile_path.suffix
        work_filename = self.get_work_file(wf_data, template)

        workdir = get_workdir_from_session(
            {
                "AVALON_PROJECT": project_name,
                "AVALON_TASK": task_name,
                "AVALON_ASSET": self.data["asset_name"]
            }
            , wf_template_key
        )

        workfile_file_path = os.path.join(os.path.normpath(workdir), work_filename)
        workfile_path = Path(str(workfile_file_path))

        # Compute Published WorkFile Path
        max_retries = int((sync_server.sync_project_settings[project_name]
        ["config"]
        ["retry_cnt"]))

        # Copy file and substitute path
        last_published_workfile_path = download_last_published_workfile(
            host_name,
            project_name,
            task_name,
            published_workfile_representation,
            max_retries,
            anatomy=anatomy
        )
        if not last_published_workfile_path:
            self.log.debug(
                "Couldn't download {}".format(last_published_workfile_path)
            )
            return

        self.log.info(f"{last_published_workfile_path} correctly downloaded !")

        # Copy and open
        self.launch_context.launch_args.remove(last_workfile)
        shutil.copyfile(last_published_workfile_path, str(workfile_path))

        _, ext = os.path.splitext(str(workfile_path))
        WorkFileCache().add_task_extension(project_name, task_name, asset_name, ext)

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
