# -*- coding: utf-8 -*-
"""Submitting render job to Deadline."""

import os
import re
import json
import getpass
import platform
from copy import copy
from pathlib import Path

from datetime import datetime, timezone

import requests
import pyblish.api

import pyblish.api
from dataclasses import dataclass, field, asdict

from quadpype.pipeline import (
    legacy_io,
)
from quadpype.pipeline.publish import (
    QuadPypePyblishPluginMixin
)

from quadpype.pipeline.context_tools import _get_modules_manager
from quadpype.modules.deadline.utils import (
    set_custom_deadline_name,
    get_deadline_job_profile,
    DeadlineDefaultJobAttrs
)

from quadpype.tests.lib import is_in_tests
from quadpype.lib import (
    is_running_from_build,
    BoolDef,
    EnumDef,
)

from quadpype.settings import PROJECT_SETTINGS_KEY

from quadpype.pipeline import legacy_io, OptionalPyblishPluginMixin

from quadpype.pipeline.farm.tools import iter_expected_files
from quadpype.pipeline.publish.lib import get_template_name_profiles

from quadpype_modules.deadline import abstract_submit_deadline, get_deadline_limits_plugin
from quadpype_modules.deadline.utils import get_deadline_job_profile, DeadlineDefaultJobAttrs
from quadpype_modules.deadline.blender.publish import common_job

@dataclass
class BlenderPluginInfo:
    SceneFile: str = field(default=None)  # Input
    Version: str = field(default=None)  # Mandatory for Deadline
    ScriptName: str = field(default=None)
    SaveFile: bool = field(default=True)


class BlenderSubmitDeadline(abstract_submit_deadline.AbstractSubmitDeadline,
                            pyblish.api.InstancePlugin,
                            OptionalPyblishPluginMixin,
                            QuadPypePyblishPluginMixin,
                            DeadlineDefaultJobAttrs):
    label = "Submit Blender Render to Deadline"
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
    use_gpu = False

    @classmethod
    def get_job_attr(cls, attr_name):
        if attr_name not in cls.deadline_attrs_names:
            # Attribute not found
            raise AttributeError("Unknown attribute {}".format(attr_name))

        if hasattr(cls, "_" + attr_name):
            # Attribute has been set, use it
            return getattr(cls, "_" + attr_name)

        try:
            # Value from project setting default values
            return get_current_project_settings()["deadline"]["JobAttrsValues"]["DefaultValues"][attr_name]
        except Exception: # noqa
            pass

        # Value from global setting default values
        return cls.global_default_attrs_values[attr_name]

    @classmethod
    def apply_settings(cls, project_settings):
        profile = get_deadline_job_profile(project_settings, cls.hosts[0])
        cls.set_job_attrs(profile)

    @classmethod
    def get_attribute_defs(cls):

        cls.log.info("=== DÉBUT get_attribute_defs Blender ===")

        defs = super(BlenderSubmitDeadline, cls).get_attribute_defs()
        manager = _get_modules_manager()
        deadline_module = manager.modules_by_name["deadline"]
        deadline_url = deadline_module.deadline_urls["default"]
        pools = deadline_module.get_deadline_pools(deadline_url, cls.log)

        defs.extend([
            EnumDef("pool",
                    label="Primary Pool",
                    items=pools,
                    default=cls.get_job_attr("pool")),
            EnumDef("pool_secondary",
                    label="Secondary Pool",
                    items=pools,
                    default=cls.get_job_attr("pool_secondary")),

            BoolDef("use_published",
                    default=cls.use_published,
                    label="Use Published Scene"),
        ])

        return defs

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
                plugin_name="Blender",
                src_filepath=src_filepath,
                job_suffix="Render"
            )

            deadline_publish_attributes = instance.data.get("publish_attributes", {}).get("BlenderSubmitDeadline", None)
            job.Pool = deadline_publish_attributes.get("pool", "")
            job.SecondaryPool = deadline_publish_attributes.get("pool_secondary", "")

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
        render_device = self._instance.data.get('creator_attributes', {}).get('device', '')
        plugin_info = BlenderPluginInfo(
            SceneFile=self.scene_path,
            Version=f"{major}.{minor}",
            ScriptName=common_job.ScriptsNames.ForceGPU.value if render_device == "GPU" else '',
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
