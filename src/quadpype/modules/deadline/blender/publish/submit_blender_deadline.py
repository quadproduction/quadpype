# -*- coding: utf-8 -*-
"""Submitting render job to Deadline."""

import os

import pyblish.api
from dataclasses import dataclass, field, asdict

from quadpype.lib import (
    is_running_from_build,
    BoolDef,
    NumberDef,
    TextDef,
)
from quadpype.settings import PROJECT_SETTINGS_KEY

from quadpype.pipeline import legacy_io, OptionalPyblishPluginMixin
from quadpype.pipeline.publish import QuadPypePyblishPluginMixin
from quadpype.pipeline.farm.tools import iter_expected_files

from quadpype_modules.deadline import abstract_submit_deadline
from quadpype_modules.deadline.utils import get_deadline_job_profile, DeadlineDefaultJobAttrs
from quadpype_modules.deadline.blender.publish import common_job


@dataclass
class BlenderPluginInfo:
    SceneFile: str = field(default=None)  # Input
    Version: str = field(default=None)  # Mandatory for Deadline
    SaveFile: bool = field(default=True)


class BlenderSubmitDeadline(abstract_submit_deadline.AbstractSubmitDeadline,
                            OptionalPyblishPluginMixin,
                            QuadPypePyblishPluginMixin,
                            DeadlineDefaultJobAttrs):
    label = "Submit Render to Deadline"
    hosts = ["blender"]
    families = ["render", "renderlayer"]
    order = pyblish.api.IntegratorOrder + 0.12

    optional = True
    use_published = True
    priority = 50
    chunk_size = 1
    jobInfo = {}
    pluginInfo = {}
    group = None
    job_delay = "00:00:00:00"
    dependency = True

    def get_job_info(self):

        instance = self._instance
        context = instance.context

        profile = get_deadline_job_profile(context.data[PROJECT_SETTINGS_KEY],  self.hosts[0])
        self.set_job_attrs(profile)

        jobs = list()
        for src_filepath in [context.data["currentFile"]]:
            instance.data.get("blenderRenderPlugin", "Blender")

            job = common_job.generate(
                job_instance=self,
                instance=instance,
                plugin_name="Blender",
                src_filepath=src_filepath,
                job_suffix="Render"
            )

            frames = "{start}-{end}x{step}".format(
                start=int(instance.data["frameStartHandle"]),
                end=int(instance.data["frameEndHandle"]),
                step=int(instance.data["byFrameStep"]),
            )
            job.Frames = frames

            attr_values = self.get_attr_values_from_data(instance.data)
            render_globals = instance.data.setdefault("renderGlobals", {})
            machine_list = attr_values.get("machineList", "")
            if machine_list:
                if attr_values.get("whitelist", True):
                    machine_list_key = "Whitelist"
                else:
                    machine_list_key = "Blacklist"
                render_globals[machine_list_key] = machine_list

            job.ChunkSize = attr_values.get("chunkSize", self.chunk_size)

            # Add options from RenderGlobals
            render_globals = instance.data.get("renderGlobals", {})
            job.update(render_globals)

            keys = [
                "FTRACK_API_KEY",
                "FTRACK_API_USER",
                "FTRACK_SERVER",
                "QUADPYPE_SG_USER",
                "AVALON_DB",
                "AVALON_PROJECT",
                "AVALON_ASSET",
                "AVALON_TASK",
                "AVALON_APP_NAME",
                "QUADPYPE_DEV"
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
                if not value:
                    continue
                job.EnvironmentKeyValue[key] = value

            # to recognize job from PYPE for turning Event On/Off
            job.add_render_job_env_var()
            job.EnvironmentKeyValue["QUADPYPE_LOG_NO_COLORS"] = "1"
            # Adding file dependencies.
            if self.asset_dependencies:
                dependencies = instance.context.data["fileDependencies"]
                for dependency in dependencies:
                    job.AssetDependency += dependency

            # Add list of expected files to job
            # ---------------------------------
            exp = instance.data.get("expectedFiles")
            for filepath in iter_expected_files(exp):
                job.OutputDirectory += os.path.dirname(filepath)
                job.OutputFilename += os.path.basename(filepath)

            jobs.append(job)

        return jobs

    def get_plugin_info(self):
        # Not all hosts can import this module.
        import bpy

        major, minor, _ = bpy.app.version
        plugin_info = BlenderPluginInfo(
            SceneFile=self.scene_path,
            Version=f"{major}.{minor}",
            SaveFile=True,
        )

        plugin_payload = asdict(plugin_info)

        # Patching with pluginInfo from settings
        for key, value in self.pluginInfo.items():
            plugin_payload[key] = value

        return plugin_payload

    def process_submission(self, job_info=None, plugin_info=None, aux_files=None):
        instance = self._instance

        expected_files = instance.data["expectedFiles"]
        if not expected_files:
            raise RuntimeError("No Render Elements found!")

        first_file = next(iter_expected_files(expected_files))
        output_dir = os.path.dirname(first_file)
        instance.data["outputDir"] = output_dir
        instance.data["toBeRenderedOn"] = "deadline"

        # If render layer, it means that there is already a master render which
        # has submitted a render job and we avoid triggering another one
        if 'renderlayer' in instance.data['families']:
            return False

        payload = self.assemble_payload(job_info, plugin_info, aux_files)
        return self.submit(payload)

    def from_published_scene(self, replace_in_path=True):
        """
        This is needed to set the correct path for the json metadata. Because
        the rendering path is set in the blend file during the collection,
        and the path is adjusted to use the published scene, this ensures that
        the metadata and the rendered files are in the same location.
        """
        return super().from_published_scene(replace_in_path)

    @classmethod
    def get_attribute_defs(cls):
        defs = super(BlenderSubmitDeadline, cls).get_attribute_defs()
        defs.extend([
            BoolDef("use_published",
                    default=cls.use_published,
                    label="Use Published Scene"),

            NumberDef("priority",
                      minimum=1,
                      maximum=250,
                      decimals=0,
                      default=cls.priority,
                      label="Priority"),

            NumberDef("chunkSize",
                      minimum=1,
                      maximum=50,
                      decimals=0,
                      default=cls.chunk_size,
                      label="Frame Per Task"),

            TextDef("group",
                    default=cls.group,
                    label="Group Name"),

            TextDef("job_delay",
                    default=cls.job_delay,
                    label="Job Delay",
                    placeholder="dd:hh:mm:ss",
                    tooltip="Delay the job by the specified amount of time. "
                            "Timecode: dd:hh:mm:ss."),
        ])

        return defs
