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

from quadpype.pipeline import (
    legacy_io,
    Anatomy
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
    NumberDef,
    EnumDef,
    filter_profiles,
    StringTemplate
)
from quadpype.pipeline.publish.lib import get_template_name_profiles
from quadpype.settings import get_project_settings

from quadpype_modules.deadline import (
    get_deadline_limits_plugin
)


class NukeSubmitDeadline(pyblish.api.InstancePlugin,
                         QuadPypePyblishPluginMixin,
                         DeadlineDefaultJobAttrs):
    """Submit write to Deadline

    Renders are submitted to a Deadline Web Service as
    supplied via settings key "DEADLINE_REST_URL".

    """

    label = "Submit Nuke to Deadline"
    order = pyblish.api.IntegratorOrder + 0.1
    hosts = ["nuke"]
    families = ["render", "prerender"]
    optional = True
    targets = ["local"]

    # presets
    chunk_size = 1
    concurrent_tasks = 1
    group = ""
    department = ""
    use_gpu = False
    env_allowed_keys = []
    env_search_replace_values = {}
    workfile_dependency = True
    use_published_workfile = True

    @classmethod
    def apply_settings(cls, project_settings):
        profile = get_deadline_job_profile(project_settings, cls.hosts[0])
        cls.set_job_attrs(profile)

    @classmethod
    def get_attribute_defs(cls):
        defs = super(NukeSubmitDeadline, cls).get_attribute_defs()
        manager = _get_modules_manager()
        deadline_module = manager.modules_by_name["deadline"]
        deadline_url = deadline_module.deadline_urls["default"]
        pools = deadline_module.get_deadline_pools(deadline_url, cls.log)
        limits_plugin = get_deadline_limits_plugin(deadline_module.enabled, deadline_url, cls.log)

        defs.extend([
            EnumDef("pool",
                    label="Primary Pool",
                    items=pools,
                    default=cls.get_job_attr("pool")),
            EnumDef("pool_secondary",
                    label="Secondary Pool",
                    items=pools,
                    default=cls.get_job_attr("pool_secondary")),
            NumberDef(
                "priority",
                label="Priority",
                default=cls.get_job_attr("priority"),
                decimals=0
            ),
            NumberDef(
                "limit_machine",
                label="Machine Limit",
                default=cls.get_job_attr("limit_machine"),
                minimum=0,
                decimals=0
            ),
            EnumDef(
                "limits_plugin",
                label="Plugin Limits",
                items=limits_plugin,
                default=cls.get_job_attr("limits_plugin"),
                multiselection=True
            ),
            NumberDef(
                "chunkSize",
                label="Frames Per Task",
                default=cls.chunk_size,
                decimals=0,
                minimum=1,
                maximum=1000
            ),
            NumberDef(
                "concurrency",
                label="Concurrency",
                default=cls.concurrent_tasks,
                decimals=0,
                minimum=1,
                maximum=10
            ),
            BoolDef(
                "use_gpu",
                default=cls.use_gpu,
                label="Use GPU"
            ),
            BoolDef(
                "suspend_publish",
                default=False,
                label="Suspend publish"
            ),
            BoolDef(
                "workfile_dependency",
                default=cls.workfile_dependency,
                label="Workfile Dependency"
            ),
            BoolDef(
                "use_published_workfile",
                default=cls.use_published_workfile,
                label="Use Published Workfile"
            )
        ])
        return defs

    def process(self, instance):
        if not instance.data.get("farm"):
            self.log.debug("Skipping local instance.")
            return
        instance.data["attributeValues"] = self.get_attr_values_from_data(
            instance.data)

        # add suspend_publish attributeValue to instance data
        instance.data["suspend_publish"] = instance.data["attributeValues"][
            "suspend_publish"]

        families = instance.data["families"]

        node = instance.data["transientData"]["node"]
        context = instance.context

        # get default deadline webservice url from deadline module
        deadline_url = instance.context.data["defaultDeadline"]
        # if custom one is set in instance, use that
        if instance.data.get("deadlineUrl"):
            deadline_url = instance.data.get("deadlineUrl")
        assert deadline_url, "Requires Deadline Webservice URL"

        self.deadline_url = "{}/api/jobs".format(deadline_url)
        self._comment = context.data.get("comment", "")
        self._ver = re.search(r"\d+\.\d+", context.data.get("hostVersion"))
        self._deadline_user = context.data.get(
            "deadlineUser", getpass.getuser())
        submit_frame_start = int(instance.data["frameStartHandle"])
        submit_frame_end = int(instance.data["frameEndHandle"])

        # get output path
        render_path = instance.data['path']
        script_path = context.data["currentFile"]

        use_published_workfile = instance.data["attributeValues"].get(
            "use_published_workfile", self.use_published_workfile
        )
        if use_published_workfile:
            script_path = self._get_published_workfile_path(context)

        # only add main rendering job if target is not frames_farm
        r_job_response_json = None
        if instance.data["render_target"] != "frames_farm":
            r_job_response = self.payload_submit(
                instance,
                script_path,
                render_path,
                node.name(),
                submit_frame_start,
                submit_frame_end
            )
            r_job_response_json = r_job_response.json()
            instance.data["deadlineSubmissionJob"] = r_job_response_json

            # Store output dir for unified publisher (filesequence)
            instance.data["outputDir"] = os.path.dirname(
                render_path).replace("\\", "/")
            instance.data["publishJobState"] = "Suspended"

        if instance.data.get("bakingNukeScripts"):
            for baking_script in instance.data["bakingNukeScripts"]:
                render_path = baking_script["bakeRenderPath"]
                script_path = baking_script["bakeScriptPath"]
                exe_node_name = baking_script["bakeWriteNodeName"]

                b_job_response = self.payload_submit(
                    instance,
                    script_path,
                    render_path,
                    exe_node_name,
                    submit_frame_start,
                    submit_frame_end,
                    r_job_response_json,
                    baking_submission=True
                )

                # Store output dir for unified publisher (filesequence)
                instance.data["deadlineSubmissionJob"] = b_job_response.json()

                instance.data["publishJobState"] = "Suspended"

                # add to list of job Id
                if not instance.data.get("bakingSubmissionJobs"):
                    instance.data["bakingSubmissionJobs"] = []

                instance.data["bakingSubmissionJobs"].append(
                    b_job_response.json()["_id"])

        # redefinition of families
        if "render" in instance.data["family"]:
            instance.data['family'] = 'write'
            families.insert(0, "render2d")
        elif "prerender" in instance.data["family"]:
            instance.data['family'] = 'write'
            families.insert(0, "prerender")
        instance.data["families"] = families

    def _get_published_workfile_path(self, context):
        """This method is temporary while the class is not inherited from
        AbstractSubmitDeadline"""
        for instance in context:
            if (
                instance.data["family"] != "workfile"
                # Disabled instances won't be integrated
                or instance.data("publish") is False
            ):
                continue

            # Expect workfile instance has only one representation
            representation = instance.data["representations"][0]
            # Get workfile extension
            repre_file = representation["files"]
            self.log.info(repre_file)
            ext = os.path.splitext(repre_file)[1].lstrip(".").lower()

            anatomy_data = instance.data['anatomyData']
            family = instance.data["family"]

            project_name = anatomy_data.get('project', {}).get('name', None)
            if not project_name:
                raise RuntimeError("Can not retrieve project name from template_data. Can not get path from template.")

            profiles = get_template_name_profiles(
                project_name, get_project_settings(project_name), self.log
            )

            task = anatomy_data.get('task')
            if not task:
                raise RuntimeError("Can not retrieve task from template_data. Can not get path from template.")

            filter_criteria = {
                "hosts": anatomy_data["app"],
                "families": family,
                "task_names": task.get('name', None),
                "task_types": task.get('type', None),
            }
            profile = filter_profiles(profiles, filter_criteria, logger=self.log)

            anatomy = Anatomy()
            template = anatomy.templates.get(profile['template_name'])
            if not template:
                raise NotImplemented(
                    f"'{profile['template_name']}' template need to be setted in your project settings")

            template_data = copy(anatomy_data)
            template_data.update(
                {
                    'root': anatomy.roots,
                    'family': family,
                    'subset': instance.data["subset"],
                    'ext': ext
                }
            )
            template_filled = StringTemplate.format_template(
                template=template['path'],
                data=template_data,
            )

            script_path = os.path.normpath(template_filled)
            self.log.info(
                "Using published scene for render {}".format(
                    script_path
                )
            )
            return script_path

        return None

    def payload_submit(
        self,
        instance,
        script_path,
        render_path,
        exe_node_name,
        start_frame,
        end_frame,
        response_data=None,
        baking_submission=False,
    ):
        """Submit payload to Deadline

        Args:
            instance (pyblish.api.Instance): pyblish instance
            script_path (str): path to nuke script
            render_path (str): path to rendered images
            exe_node_name (str): name of the node to render
            start_frame (int): start frame
            end_frame (int): end frame
            response_data Optional[dict]: response data from
                                          previous submission
            baking_submission Optional[bool]: if it's baking submission

        Returns:
            requests.Response
        """
        render_dir = os.path.normpath(os.path.dirname(render_path))

        # batch name
        src_filepath = instance.context.data["currentFile"]
        filename = os.path.basename(src_filepath)

        job_name = set_custom_deadline_name(
            instance,
            filename,
            "deadline_job_name"
        )
        batch_name = set_custom_deadline_name(
            instance,
            filename,
            "deadline_batch_name"
        )

        if is_in_tests():
            batch_name += datetime.now(timezone.utc).strftime("%d%m%Y%H%M%S")

        output_filename_0 = self.preview_fname(render_path)

        if not response_data:
            response_data = {}

        try:
            # Ensure render folder exists
            os.makedirs(render_dir)
        except OSError:
            pass

        # resolve any limit groups
        limits_plugin = self.get_attr_value(self, instance, "limits_plugin")
        if limits_plugin:
            limits_plugin = ",".join(limits_plugin)

        payload = {
            "JobInfo": {
                # Top-level group name
                "BatchName": "Group: " + batch_name,

                # Job name, as seen in Monitor
                "Name": job_name,

                # Arbitrary username, for visualization in Monitor
                "UserName": self._deadline_user,

                "Priority": self.get_attr_value(self, instance, "priority"),
                "ChunkSize": self.get_attr_value(self, instance, "chunkSize", self.chunk_size),
                "ConcurrentTasks": self.get_attr_value(self, instance, "concurrency", self.concurrent_tasks),

                "Department": self.department,

                "Pool": self.get_attr_value(self, instance, "pool"),
                "SecondaryPool": self.get_attr_value(self, instance, "pool_secondary"),
                "MachineLimit": self.get_attr_value(self, instance, "limit_machine"),
                "Group": self.group,

                "MachineName": self.get_attr_value(self, instance, "machine",
                                                   fallback=instance.context.data.get("machine", platform.node())),

                "Plugin": "Nuke",
                "Frames": "{start}-{end}".format(
                    start=start_frame,
                    end=end_frame
                ),
                "Comment": self._comment,

                # Optional, enable double-click to preview rendered
                # frames from Deadline Monitor
                "OutputFilename0": output_filename_0.replace("\\", "/"),

                # limiting groups
                "LimitGroups": limits_plugin

            },
            "PluginInfo": {
                # Input
                "SceneFile": script_path,

                # Output directory and filename
                "OutputFilePath": render_dir.replace("\\", "/"),
                # "OutputFilePrefix": render_variables["filename_prefix"],

                # Mandatory for Deadline
                "Version": self._ver.group(),

                # Resolve relative references
                "ProjectPath": script_path,
                "AWSAssetFile0": render_path,

                # using GPU by default
                "UseGpu": self.get_attr_value(self, instance, "use_gpu", self.use_gpu),

                # Only the specific write node is rendered.
                "WriteNode": exe_node_name
            },

            # Mandatory for Deadline, may be empty
            "AuxFiles": []
        }

        # Add workfile dependency.
        workfile_dependency = instance.data["attributeValues"].get(
            "workfile_dependency", self.workfile_dependency
        )
        if workfile_dependency:
            payload["JobInfo"].update({"AssetDependency0": script_path})

        # TODO: rewrite for baking with sequences
        if baking_submission:
            payload["JobInfo"].update({
                "JobType": "Normal",
                "ChunkSize": 99999999
            })

        if response_data.get("_id"):
            payload["JobInfo"].update({
                "BatchName": response_data["Props"]["Batch"],
                "JobDependency0": response_data["_id"],
            })

        # Include critical environment variables with submission
        keys = [
            "PYTHONPATH",
            "PATH",
            "AVALON_DB",
            "AVALON_PROJECT",
            "AVALON_ASSET",
            "AVALON_TASK",
            "AVALON_APP_NAME",
            "FTRACK_API_KEY",
            "FTRACK_API_USER",
            "FTRACK_SERVER",
            "PYBLISHPLUGINPATH",
            "NUKE_PATH",
            "TOOL_ENV",
            "foundry_LICENSE",
            "QUADPYPE_SG_USER",
        ]

        # Add QuadPype version if we are running from build.
        if is_running_from_build():
            keys.append("QUADPYPE_VERSION")

        # Add mongo url if it's enabled
        if instance.context.data.get("deadlinePassMongoUrl"):
            keys.append("QUADPYPE_MONGO")

        # add allowed keys from preset if any
        if self.env_allowed_keys:
            keys += self.env_allowed_keys

        # QUICK FIX : add all gizmos and plugin paths to the NUKE_PATH for the render farm
        # CORRECT WAY : the proper way is to declare tools in settings to add them to the soft
        # import nuke
        # nuke_path = os.getenv("NUKE_PATH", "")
        # nuke_paths = [path for path in nuke_path.split(os.pathsep) if path]
        # for nuke_plugin_path in nuke.pluginPath():
        #     if nuke_plugin_path not in nuke_paths:
        #         nuke_paths.append(nuke_plugin_path)
        # os.environ["NUKE_PATH"] = os.pathsep.join(nuke_paths)

        environment = dict({key: os.environ[key] for key in keys
                            if key in os.environ}, **legacy_io.Session)

        environment['NUKE_PATH'] = self._convert_paths_for_all_os(environment['NUKE_PATH'])

        for _path in os.environ:
            if _path.lower().startswith('quadpype_'):
                environment[_path] = os.environ[_path]

        # to recognize render jobs
        render_job_label = "QUADPYPE_RENDER_JOB"

        environment[render_job_label] = "1"

        # finally search replace in values of any key
        if self.env_search_replace_values:
            for key, value in environment.items():
                for _k, _v in self.env_search_replace_values.items():
                    environment[key] = value.replace(_k, _v)

        payload["JobInfo"].update({
            "EnvironmentKeyValue%d" % index: "{key}={value}".format(
                key=key,
                value=environment[key]
            ) for index, key in enumerate(environment)
        })

        plugin = payload["JobInfo"]["Plugin"]
        self.log.debug("using render plugin : {}".format(plugin))

        self.log.debug("Submitting..")
        self.log.debug(json.dumps(payload, indent=4, sort_keys=True))

        # adding expected files to instance.data
        self.expected_files(
            instance,
            render_path,
            start_frame,
            end_frame
        )

        self.log.debug("__ expectedFiles: `{}`".format(
            self.get_attr_value(self, instance, "expectedFiles")))
        response = requests.post(self.deadline_url, json=payload, timeout=10)

        if not response.ok:
            raise Exception(response.text)

        return response

    def _convert_paths_for_all_os(self, nuke_paths):
        """Take all paths from the given environment string and add
        a converted path for each operating system as specified
        in the root's anatomy settings. This ensures that at least
        one path format will work for each primary entry.
        """
        all_paths = nuke_paths.split(';')
        root_paths = Anatomy().get('roots', None)

        converted_paths = list()

        base_pattern = r'^({windows})|({linux})|({darwin})'
        for single_path in all_paths:
            single_path = Path(single_path).as_posix()
            converted_paths.append(single_path)

            for _, os_paths_parts in root_paths.items():
                pattern = base_pattern.format(
                    windows=Path(os_paths_parts.get('windows')).as_posix(),
                    linux=Path(os_paths_parts.get('linux')).as_posix(),
                    darwin=Path(os_paths_parts.get('darwin')).as_posix()
                )

                for _, specific_part in os_paths_parts.items():
                    replace_path = re.sub(
                        pattern=pattern,
                        repl=Path(specific_part).as_posix(),
                        string=single_path
                    )

                    if replace_path in converted_paths:
                        continue

                    converted_paths.append(replace_path)

        return ';'.join(converted_paths)

    def preflight_check(self, instance):
        """Ensure the startFrame, endFrame and byFrameStep are integers"""

        for key in ("frameStart", "frameEnd"):
            value = instance.data[key]

            if int(value) == value:
                continue

            self.log.warning(
                "%f=%d was rounded off to nearest integer"
                % (value, int(value))
            )

    def preview_fname(self, path):
        """Return output file path with #### for padding.

        Deadline requires the path to be formatted with # in place of numbers.
        For example `/path/to/render.####.png`

        Args:
            path (str): path to rendered images

        Returns:
            str

        """
        self.log.debug("_ path: `{}`".format(path))
        if "%" in path:
            search_results = re.search(r"(%0)(\d+)(d)", path)
            if not search_results:
                self.log.debug("No match found for '(%0)(\d+)(d)' in: `{}`".format(path))
                return path
            self.log.debug("_ search_results: `{}`".format(search_results))
            prefix, padding, _ = search_results.groups()
            hashes = "#" * int(padding)
            new_path = path.replace(f"{prefix}{padding}d", hashes)
            self.log.debug("_ path: `{}`".format(new_path))
            return new_path

        if "#" in path:
            self.log.debug("_ path: `{}`".format(path))
        return path

    def expected_files(
        self,
        instance,
        filepath,
        start_frame,
        end_frame
    ):
        """ Create expected files in instance data
        """
        if not instance.data.get("expectedFiles"):
            instance.data["expectedFiles"] = []

        dirname = os.path.dirname(filepath)
        file = os.path.basename(filepath)

        # since some files might be already tagged as publish_on_farm
        # we need to avoid adding them to expected files since those would be
        # duplicated into metadata.json file
        representations = instance.data.get("representations", [])
        # check if file is not in representations with publish_on_farm tag
        for repre in representations:
            # Skip if 'publish_on_farm' not available
            if "publish_on_farm" not in repre.get("tags", []):
                continue

            # in case where single file (video, image) is already in
            # representation file. Will be added to expected files via
            # submit_publish_job.py
            if file in repre.get("files", []):
                self.log.debug(
                    "Skipping expected file: {}".format(filepath))
                return

        # in case path is hashed sequence expression
        # (e.g. /path/to/file.####.png)
        if "#" in file:
            pparts = file.split("#")
            padding = "%0{}d".format(len(pparts) - 1)
            file = pparts[0] + padding + pparts[-1]

        # in case input path was single file (video or image)
        if "%" not in file:
            instance.data["expectedFiles"].append(filepath)
            return

        # shift start frame by 1 if slate is present
        if instance.data.get("slate"):
            start_frame -= 1

        # add sequence files to expected files
        for i in range(start_frame, (end_frame + 1)):
            instance.data["expectedFiles"].append(
                os.path.join(dirname, (file % i)).replace("\\", "/"))
