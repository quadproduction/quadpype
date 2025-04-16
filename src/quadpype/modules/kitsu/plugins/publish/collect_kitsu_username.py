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

        from gazu.person import get_person_by_email

        user = get_person_by_email(kitsu_login)

        for instance in context:
            # Don't override customData if it already exists
            custom_data = instance.data.setdefault("customData", {})
            custom_data["kitsuUsername"] = user["full_name"]
