import pyblish.api
from quadpype.lib import get_quadpype_username


class CollectCurrentUserPype(pyblish.api.ContextPlugin):
    """Inject the currently logged on user into the Context"""

    # Order must be after default pyblish-base CollectCurrentUser
    order = pyblish.api.CollectorOrder + 0.001
    label = ("Collect QuadPype User")

    def process(self, context):
        user = get_quadpype_username()
        context.data["user"] = user
        self.log.debug("Collected user \"{}\"".format(user))
