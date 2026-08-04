# -*- coding: utf-8 -*-
import os
import re

import pyblish.api

from quadpype.pipeline import get_current_project_name
from quadpype.settings import get_project_settings

class CollectKitsuUsername(pyblish.api.ContextPlugin):
    """Collect Kitsu username from the kitsu login"""

    order = pyblish.api.CollectorOrder + 0.499
    label = "Kitsu username"

    def process(self, context):
        import gazu

        kitsu_login = os.getenv("KITSU_LOGIN")

        if not kitsu_login:
            return

        kitsu_host = os.getenv("KITSU_SERVER")
        if kitsu_host:
            gazu.set_host(kitsu_host)

        user_login = os.getenv("KITSU_LOGIN")
        user_password = os.getenv("KITSU_PWD")

        settings = get_project_settings(get_current_project_name())
        bot_token = settings["kitsu"].get("admin_token", None)

        from gazu.person import get_person_by_email

        if bot_token:
            gazu.client.set_tokens({"access_token": bot_token})
            self.log.info("Logged in to Kitsu with bot token")
            try:
                user = get_person_by_email(kitsu_login)
                self.log.info("Found user: {}".format(user["full_name"]))
                self.log.info(user)

            finally:
                gazu.client.set_tokens({})
                if user_login and user_password:
                    gazu.log_in(user_login, user_password)
        else:
            user = get_person_by_email(kitsu_login)

        for instance in context:
            # Don't override customData if it already exists
            custom_data = instance.data.setdefault("customData", {})
            custom_data["kitsuUsername"] = user["full_name"]
