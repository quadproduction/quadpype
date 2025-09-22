import pyblish.api
import clique
import cv2
import os

from quadpype.pipeline import OptionalPyblishPluginMixin

VIDEO_EXTS = ["mov", "mp4", "avi"]

class CollectSequenceFrameData(
    pyblish.api.InstancePlugin,
    OptionalPyblishPluginMixin
):
    """Collect Original Sequence Frame Data

    If the representation includes files with frame numbers,
    then set `frameStart` and `frameEnd` for the instance to the
    start and end frame respectively
    """

    order = pyblish.api.CollectorOrder + 0.4905
    label = "Collect Frame Range From Media"
    families = ["plate", "pointcache",
                "vdbcache", "online",
                "render"]
    hosts = ["traypublisher"]
    optional = True

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        # editorial would fail since they might not be in database yet
        new_asset_publishing = instance.data.get("newAssetPublishing")
        if new_asset_publishing:
            self.log.debug("Instance is creating new asset. Skipping.")
            return

        frame_data = self.get_frame_data_from_repre_sequence(instance)

        if not frame_data:
            # if no dict data skip collecting the frame range data
            return

        for key, value in frame_data.items():
            instance.data[key] = value
            self.log.debug(f"Collected Frame range data '{key}':{value} ")


    def get_frame_data_from_repre_sequence(self, instance):
        repres = instance.data.get("representations")
        asset_data = instance.data["assetEntity"]["data"]

        if repres:
            first_repre = repres[0]
            if "ext" not in first_repre:
                self.log.warning("Cannot find file extension"
                                 " in representation data")
                return

            if first_repre["ext"] in VIDEO_EXTS:
                full_path = os.path.join(first_repre["stagingDir"], first_repre["files"])
                fps, frame_count = self.get_video_frame_count(full_path)
                frame_start = 1
                frame_end = frame_count

            else:
                files = first_repre["files"]
                collections, _ = clique.assemble(files)
                if not collections:
                    # No sequences detected and we can't retrieve
                    # frame range
                    self.log.debug(
                        "No sequences detected in the representation data."
                        " Skipping collecting frame range data.")
                    return
                collection = collections[0]
                repres_frames = list(collection.indexes)
                frame_start = repres_frames[0]
                frame_end = repres_frames[-1]
                fps = asset_data["fps"]

            return {
                "frameStart": frame_start,
                "frameEnd": frame_end,
                "handleStart": 0,
                "handleEnd": 0,
                "fps": fps
            }

    @staticmethod
    def get_video_frame_count(path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise IOError("Can't open video")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        cap.release()
        return fps, frame_count
