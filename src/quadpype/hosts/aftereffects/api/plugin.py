from abc import ABC

from quadpype.pipeline import LoaderPlugin
from .launch_logic import get_stub


class AfterEffectsLoader(LoaderPlugin, ABC):
    @staticmethod
    def get_stub():
        return get_stub()
