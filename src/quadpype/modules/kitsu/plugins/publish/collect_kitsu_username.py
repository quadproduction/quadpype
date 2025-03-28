# -*- coding: utf-8 -*-
import os
import re

import pyblish.api


class CollectKitsuUsername(pyblish.api.ContextPlugin):
    """Collect Kitsu username from the kitsu login"""

    order = pyblish.api.CollectorOrder + 0.499
    label = "Kitsu username"

    def process(self, context):
        kitsu_login = os.getenv("KITSU_LOGIN")

        if not kitsu_login:
            return

        kitsu_username = kitsu_login.split("@")[0].replace(".", " ")
        new_username = re.sub("[^a-zA-Z]", " ", kitsu_username).title()

        for instance in context:
            # Don't override customData if it already exists
            custom_data = instance.data.setdefault("customData", {})
            custom_data["kitsuUsername"] = new_username
