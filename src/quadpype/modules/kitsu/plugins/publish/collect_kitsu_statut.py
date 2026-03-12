# -*- coding: utf-8 -*-
import os

import pyblish.api
import gazu

from quadpype.pipeline.publish import QuadPypePyblishPluginMixin
from quadpype.lib.attribute_definitions import (
    EnumDef,
    UISeparatorDef
)

from quadpype.pipeline import get_current_project_name
from quadpype.settings import get_project_settings

class CollectKitsuStatus(
    pyblish.api.InstancePlugin,
    QuadPypePyblishPluginMixin
):
    """Collect Kitsu status to apply to the review"""

    order = pyblish.api.CollectorOrder + 0.4991
    label = "Kitsu Status"
    families = ["render", "image", "online", "plate", "kitsu", "review", "shot"]

    def process(self, instance):
        attribute_values = self.get_attr_values_from_data(instance.data)
        kitsu_status = attribute_values.get("kitsu_status")

        instance.data["kitsu_status_shortname"] = kitsu_status

    @staticmethod
    def _get_project_status():
        try:
            project = gazu.project.get_project_by_name(get_current_project_name())
        except:
            gazu.set_host(os.environ["KITSU_SERVER"])
            gazu.log_in(os.environ["KITSU_LOGIN"], os.environ["KITSU_PWD"])
            project = gazu.project.get_project_by_name(get_current_project_name())

        statuses = gazu.task.all_task_statuses_for_project(project)
        gazu.log_out()
        return [stat["short_name"] for stat in statuses]


    @classmethod
    def get_attribute_defs(cls):
        project_status = cls._get_project_status()
        settings = get_project_settings(get_current_project_name())
        default_status = settings["kitsu"]["publish"]["IntegrateKitsuNote"]["note_status_shortname"]

        attributes = [
            EnumDef("kitsu_status", label="Review Kitsu Status",
                    items=[status for status in project_status],
                    default=default_status
                    ),
            UISeparatorDef()
        ]

        return attributes
