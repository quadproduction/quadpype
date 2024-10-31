import pyblish.api
from pprint import pformat

from quadpype.pipeline import get_current_asset_name

from quadpype.hosts.resolve import api as rapi
from quadpype.hosts.resolve.otio import davinci_export


class PrecollectWorkfile(pyblish.api.ContextPlugin):
    """Precollect the current working file into context"""

    label = "Precollect Workfile"
    order = pyblish.api.CollectorOrder - 0.5

    def process(self, context):
        current_asset_name = asset_name = get_current_asset_name()

        subset = "workfileMain"
        project = rapi.get_current_project()
        fps = project.GetSetting("timelineFrameRate")
        video_tracks = rapi.get_video_track_names()

        # adding otio timeline to context
        otio_timeline = davinci_export.create_otio_timeline(project)

        instance_data = {
            "name": "{}_{}".format(asset_name, subset),
            "label": "{} {}".format(current_asset_name, subset),
            "asset": current_asset_name,
            "subset": subset,
            "item": project,
            "family": "workfile",
            "families": []
        }

        # create instance with workfile
        instance = context.create_instance(**instance_data)

        # update context with main project attributes
        context_data = {
            "activeProject": project,
            "otioTimeline": otio_timeline,
            "videoTracks": video_tracks,
            "currentFile": project.GetName(),
            "fps": fps,
        }
        context.data.update(context_data)

        self.log.info("Creating instance: {}".format(instance))
        self.log.debug("__ instance.data: {}".format(pformat(instance.data)))
        self.log.debug("__ context_data: {}".format(pformat(context_data)))
