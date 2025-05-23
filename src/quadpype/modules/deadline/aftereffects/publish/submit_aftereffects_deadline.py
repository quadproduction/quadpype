import os
import getpass
import pyblish.api
from dataclasses import dataclass, field, asdict

from datetime import datetime, timezone

from quadpype.lib import (
    env_value_to_bool,
    collect_frames,
)
from quadpype.pipeline import legacy_io
from quadpype_modules.deadline import abstract_submit_deadline
from quadpype_modules.deadline.abstract_submit_deadline import DeadlineJobInfo
from quadpype.modules.deadline.utils import set_custom_deadline_name, DeadlineDefaultJobAttrs
from quadpype.tests.lib import is_in_tests
from quadpype.lib import is_running_from_build


@dataclass
class DeadlinePluginInfo():
    Comp: str = field(default=None)
    SceneFile: str = field(default=None)
    OutputFilePath: str = field(default=None)
    Output: str = field(default=None)
    StartupDirectory: str = field(default=None)
    Arguments: str = field(default=None)
    ProjectPath: str = field(default=None)
    AWSAssetFile0: str = field(default=None)
    Version: str = field(default=None)
    MultiProcess: str = field(default=None)


class AfterEffectsSubmitDeadline(
    abstract_submit_deadline.AbstractSubmitDeadline,
    DeadlineDefaultJobAttrs):
    label = "Submit AE to Deadline"
    order = pyblish.api.IntegratorOrder + 0.1
    hosts = ["aftereffects"]
    families = ["render.farm"]  # cannot be "render' as that is integrated
    use_published = True
    targets = ["local"]

    chunk_size = 1000000
    group = None
    department = None
    multiprocess = True

    def get_job_info(self):
        dln_job_info = DeadlineJobInfo(Plugin="AfterEffects")

        context = self._instance.context

        filename = os.path.basename(self._instance.data["source"])

        job_name = set_custom_deadline_name(
            self._instance,
            filename,
            "deadline_job_name"
        )
        batch_name = set_custom_deadline_name(
            self._instance,
            filename,
            "deadline_batch_name"
        )

        if is_in_tests():
            batch_name += datetime.now(timezone.utc).strftime("%d%m%Y%H%M%S")
        dln_job_info.Name = job_name
        dln_job_info.BatchName = "Group: " + batch_name
        dln_job_info.Plugin = "AfterEffects"
        dln_job_info.UserName = context.data.get(
            "deadlineUser", getpass.getuser())
        if self._instance.data["frameEnd"] > self._instance.data["frameStart"]:
            # Deadline requires integers in frame range
            frame_range = "{}-{}".format(
                int(round(self._instance.data["frameStart"])),
                int(round(self._instance.data["frameEnd"])))
            dln_job_info.Frames = frame_range

        dln_job_info.Priority = self.get_job_attr("priority")
        dln_job_info.Pool = self._instance.data.get("pool", self.get_job_attr("pool"))
        dln_job_info.SecondaryPool = self._instance.data.get("pool_secondary", self.get_job_attr("pool_secondary"))
        dln_job_info.Group = self.group
        dln_job_info.Department = self.department
        dln_job_info.ChunkSize = self.chunk_size
        dln_job_info.OutputFilename += \
            os.path.basename(self._instance.data["expectedFiles"][0])
        dln_job_info.OutputDirectory += \
            os.path.dirname(self._instance.data["expectedFiles"][0])
        dln_job_info.JobDelay = "00:00:00"

        keys = [
            "FTRACK_API_KEY",
            "FTRACK_API_USER",
            "FTRACK_SERVER",
            "AVALON_DB",
            "AVALON_PROJECT",
            "AVALON_ASSET",
            "AVALON_TASK",
            "AVALON_APP_NAME",
            "QUADPYPE_DEV",
            "QUADPYPE_LOG_NO_COLORS",
            "IS_TEST"
        ]

        # Add QuadPype version if we are running from build.
        if is_running_from_build():
            keys.append("QUADPYPE_VERSION")

        # Add mongo url if it's enabled
        if self._instance.context.data.get("deadlinePassMongoUrl"):
            keys.append("QUADPYPE_MONGO")

        environment = dict({key: os.environ[key] for key in keys
                            if key in os.environ}, **legacy_io.Session)
        for key in keys:
            value = environment.get(key)
            if value:
                dln_job_info.EnvironmentKeyValue[key] = value

        # to recognize render jobs
        dln_job_info.add_render_job_env_var()

        return dln_job_info

    def get_plugin_info(self):
        deadline_plugin_info = DeadlinePluginInfo()

        render_path = self._instance.data["expectedFiles"][0]

        file_name, frame = list(collect_frames([render_path]).items())[0]
        if frame:
            # replace frame ('000001') with Deadline's required '[#######]'
            # expects filename in format project_asset_subset_version.FRAME.ext
            render_dir = os.path.dirname(render_path)
            file_name = os.path.basename(render_path)
            hashed = '[{}]'.format(len(frame) * "#")
            file_name = file_name.replace(frame, hashed)
            render_path = os.path.join(render_dir, file_name)

        deadline_plugin_info.Comp = self._instance.data["comp_name"]
        deadline_plugin_info.Version = self._instance.data["app_version"]
        # must be here because of DL AE plugin
        # added override of multiprocess by env var, if shouldn't be used for
        # some app variant use MULTIPROCESS:false in Settings, default is True
        env_multi = env_value_to_bool("MULTIPROCESS", default=True)
        deadline_plugin_info.MultiProcess = env_multi and self.multiprocess
        deadline_plugin_info.SceneFile = self.scene_path
        deadline_plugin_info.Output = render_path.replace("\\", "/")

        return asdict(deadline_plugin_info)

    def from_published_scene(self, replace_in_path=True):
        """ Do not overwrite expected files.

            Use published is set to True, so rendering will be triggered
            from published scene (in 'publish' folder). Default implementation
            of abstract class renames expected (eg. rendered) files accordingly
            which is not needed here.
        """
        return super().from_published_scene(replace_in_path)
