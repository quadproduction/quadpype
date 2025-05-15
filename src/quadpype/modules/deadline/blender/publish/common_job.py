import os
import getpass
from enum import Enum
from datetime import datetime, timezone

from quadpype.tests.lib import is_in_tests
from quadpype_modules.deadline.abstract_submit_deadline import DeadlineJobInfo


class ScriptsNames(Enum):
    UpdateBlenderPaths = "update_blender_paths"


def generate(job_instance, instance, plugin_name, src_filepath, job_suffix):
    job_info = DeadlineJobInfo(Plugin=plugin_name)

    # Todo : is this necessary now ?
    job_info.update(job_instance.jobInfo)

    job_info.Priority = job_instance.get_job_attr("priority")
    job_info.Pool = job_instance.get_job_attr("pool")
    job_info.SecondaryPool = job_instance.get_job_attr("pool_secondary")
    job_info.MachineLimit = job_instance.get_job_attr("limit_machine")

    # Always use the original work file name for the Job name even when
    # rendering is done from the published Work File. The original work
    # file name is clearer because it can also have subversion strings,
    # etc. which are stripped for the published file.
    src_filename = os.path.basename(src_filepath)

    if is_in_tests():
        src_filename += datetime.now(timezone.utc).strftime("%d%m%Y%H%M%S")

    job_info.Name = f"{src_filename} - {job_suffix}"
    job_info.BatchName = f"{src_filename}"
    job_info.UserName = instance.context.data.get("deadlineUser", getpass.getuser())
    job_info.Comment = instance.data.get("comment")

    if job_instance.group != "none" and job_instance.group:
        job_info.Group = job_instance.group

    attr_values = job_instance.get_attr_values_from_data(instance.data)
    job_info.Priority = attr_values.get("priority", job_instance.priority)
    job_info.ScheduledType = "Once"
    job_info.JobDelay = attr_values.get("job_delay", job_instance.job_delay)

    return job_info
