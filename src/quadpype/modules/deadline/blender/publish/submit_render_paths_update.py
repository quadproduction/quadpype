# -*- coding: utf-8 -*-
"""Submitting render job to Deadline."""

import os
import getpass
import attr
import pyblish.api
from quadpype.pipeline import Anatomy

from datetime import datetime, timezone

from quadpype.lib import (
    is_running_from_build,
    BoolDef,
    NumberDef,
    TextDef,
)
from quadpype.settings import PROJECT_SETTINGS_KEY
from quadpype.pipeline.context_tools import get_current_project_name

from quadpype.pipeline import legacy_io, OptionalPyblishPluginMixin
from quadpype.pipeline.publish import QuadPypePyblishPluginMixin
from quadpype.pipeline.farm.tools import iter_expected_files
from quadpype.tests.lib import is_in_tests

from quadpype_modules.deadline import abstract_submit_deadline
from quadpype_modules.deadline.utils import get_deadline_job_profile, DeadlineDefaultJobAttrs
from quadpype_modules.deadline.abstract_submit_deadline import DeadlineJobInfo


UPDATE_BLENDER_PATHS_SCRIPT_NAME = 'update_blender_paths'


@attr.s
class BlenderScriptPluginInfo():
    SceneFile = attr.ib(default=None)   # Input
    Version = attr.ib(default=None)  # Mandatory for Deadline
    SaveFile = attr.ib(default=True)
    ScriptName = attr.ib(default=None)
    ScriptArguments = attr.ib(default=None)


class BlenderRenderPathsUpdateDeadline(abstract_submit_deadline.AbstractSubmitDeadline,
                            OptionalPyblishPluginMixin,
                            QuadPypePyblishPluginMixin,
                            DeadlineDefaultJobAttrs):
    label = "Submit render paths update script to Deadline"
    hosts = ["blender"]
    families = ["render"]
    order = pyblish.api.IntegratorOrder + 0.11

    # optional = True
    # use_published = True
    priority = 50
    # chunk_size = 1
    jobInfo = {}
    pluginInfo = {}
    group = None
    job_delay = "00:00:00:00"
    dependency = True

    def get_job_info(self):
        job_info = DeadlineJobInfo(Plugin="BlenderScript")

        job_info.update(self.jobInfo)

        instance = self._instance
        context = instance.context

        profile = get_deadline_job_profile(context.data[PROJECT_SETTINGS_KEY],  self.hosts[0])
        self.set_job_attrs(profile)

        job_info.Priority = self.get_job_attr("priority")
        job_info.Pool = self.get_job_attr("pool")
        job_info.SecondaryPool = self.get_job_attr("pool_secondary")
        job_info.MachineLimit = self.get_job_attr("limit_machine")

        # Always use the original work file name for the Job name even when
        # rendering is done from the published Work File. The original work
        # file name is clearer because it can also have subversion strings,
        # etc. which are stripped for the published file.
        src_filepath = context.data["currentFile"]
        src_filename = os.path.basename(src_filepath)

        if is_in_tests():
            src_filename += datetime.now(timezone.utc).strftime("%d%m%Y%H%M%S")

        job_info.Name = f"{src_filename} - update_render_paths"
        job_info.BatchName = src_filename
        job_info.UserName = context.data.get("deadlineUser", getpass.getuser())

        job_info.Comment = instance.data.get("comment")

        if self.group != "none" and self.group:
            job_info.Group = self.group

        attr_values = self.get_attr_values_from_data(instance.data)
        job_info.Priority = attr_values.get("priority", self.priority)
        job_info.ScheduledType = "Once"
        job_info.JobDelay = attr_values.get("job_delay", self.job_delay)

        return job_info

    def get_plugin_info(self):
        # Not all hosts can import this module.
        import bpy

        root_paths = Anatomy().get('roots', []).get('work', None)
        assert root_paths, "Can't find root paths to update render paths."

        windows_path = root_paths.get('windows', '')
        mac_path = root_paths.get('darwin', '')
        linux_path = root_paths.get('linux', '')

        plugin_info = BlenderScriptPluginInfo(
            SceneFile=self.scene_path,
            Version=bpy.app.version_string,
            SaveFile=True,
            ScriptName=UPDATE_BLENDER_PATHS_SCRIPT_NAME,
            ScriptArguments=f'-wp "{windows_path}" -mp "{mac_path}" -lp "{linux_path}"'
        )

        plugin_payload = attr.asdict(plugin_info)

        # Patching with pluginInfo from settings
        for key, value in self.pluginInfo.items():
            plugin_payload[key] = value

        return plugin_payload
