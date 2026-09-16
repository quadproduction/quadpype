# -*- coding: utf-8 -*-
import os
import pyotp

import pyblish.api


class CollectKitsuLogin(pyblish.api.ContextPlugin):
    """Collect Kitsu session using user credentials"""

    order = pyblish.api.CollectorOrder
    label = "Kitsu user session"
    # families = ["kitsu"]

    def process(self, context):
        import gazu

        gazu.set_host(os.environ["KITSU_SERVER"])
        totp_secret = os.getenv("KITSU_TOTP_SECRET", None)
        gazu.log_in(
            os.environ["KITSU_LOGIN"],
            os.environ["KITSU_PWD"],
            totp=pyotp.TOTP(totp_secret).now() if totp_secret else None
        )
