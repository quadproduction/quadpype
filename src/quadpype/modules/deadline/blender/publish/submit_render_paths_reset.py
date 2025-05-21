# -*- coding: utf-8 -*-
"""Submitting render job to Deadline."""

import attr
import json
import sys
import pyblish.api
from pathlib import Path

from quadpype.pipeline import Anatomy

from quadpype.settings import PROJECT_SETTINGS_KEY

from quadpype.pipeline import legacy_io, OptionalPyblishPluginMixin
from quadpype.pipeline.publish import QuadPypePyblishPluginMixin

from quadpype_modules.deadline import abstract_submit_deadline
from quadpype_modules.deadline.utils import get_deadline_job_profile, DeadlineDefaultJobAttrs
from quadpype_modules.deadline.blender.publish import common_job


@attr.s
class BlenderScriptPluginInfo():
    SceneFile = attr.ib(default=None)   # Input
    Version = attr.ib(default=None)  # Mandatory for Deadline
    SaveFile = attr.ib(default=True)
    ScriptName = attr.ib(default=None)
    ScriptArguments = attr.ib(default=None)


class BlenderRenderPathsResetDeadline(abstract_submit_deadline.AbstractSubmitDeadline,
                            OptionalPyblishPluginMixin,
                            QuadPypePyblishPluginMixin,
                            DeadlineDefaultJobAttrs):
    label = "Submit render paths reset script to Deadline"
    hosts = ["blender"]
    families = ["render"]
    order = pyblish.api.IntegratorOrder + 0.21

    # optional = True
    # use_published = True
    priority = 50
    # chunk_size = 1
    jobInfo = {}
    pluginInfo = {}
    group = None
    job_delay = "00:00:00:00"

    def get_job_info(self):
        instance = self._instance
        context = instance.context

        profile = get_deadline_job_profile(context.data[PROJECT_SETTINGS_KEY],  self.hosts[0])
        self.set_job_attrs(profile)

        jobs = list()

        for src_filepath in [context.data["currentFile"]]:
            job = common_job.generate(
                job_instance=self,
                instance=instance,
                plugin_name="BlenderScript",
                src_filepath=src_filepath,
                job_suffix="Reset render paths"
            )
            jobs.append(job)

        return jobs


    def get_plugin_info(self):
        # Not all hosts can import this module.
        import bpy

        root_paths = Anatomy().get('roots', None)
        assert root_paths, "Can't find root paths to update render paths."

        root_paths_args = _escape_and_remove_chars(json.dumps(root_paths))
        plugin_info = BlenderScriptPluginInfo(
            SceneFile=self.scene_path,
            Version=bpy.app.version_string,
            SaveFile=True,
            ScriptName=common_job.ScriptsNames.UpdateBlenderPaths.value,
            ScriptArguments=f"-r  \"{root_paths_args}\" -c \"{sys.platform}\""
        )

        plugin_payload = attr.asdict(plugin_info)

        # Patching with pluginInfo from settings
        for key, value in self.pluginInfo.items():
            plugin_payload[key] = value

        return plugin_payload


def _escape_and_remove_chars(data_string):
    return str(Path(data_string).as_posix()).replace('"', '\\"')
