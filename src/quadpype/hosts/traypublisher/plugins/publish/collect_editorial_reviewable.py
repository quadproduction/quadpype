import pyblish.api


class CollectEditorialReviewable(pyblish.api.InstancePlugin):
    """ Collect review input from user.

    Adds the input to instance data.
    """

    label = "Collect Editorial Reviewable"
    order = pyblish.api.CollectorOrder

    families = ["plate", "review", "audio", "shot"]
    hosts = ["traypublisher"]

    def process(self, instance):
        creator_identifier = instance.data["creator_identifier"]
        if creator_identifier not in [
            "editorial_plate",
            "editorial_audio",
            "editorial_review",
            "editorial_shot"
        ]:
            return

        creator_attributes = instance.data["creator_attributes"]

        if creator_attributes["add_review_family"]:
            creator_attributes["mark_for_review"] = True
            instance.data["families"].append("review")

        self.log.debug("instance.data {}".format(instance.data))
