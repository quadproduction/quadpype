import re

from quadpype.pipeline import (
    get_current_project_name,
    get_current_asset_name
)
from quadpype.client import get_asset_by_name
from quadpype.settings import get_project_settings
from quadpype.pipeline.anatomy import Anatomy


RES_SEPARATOR = '*'
RES_REGEX = r'(\d+).{1}(\d+)'
RES_RECONSTRUCTION = fr'\1{RES_SEPARATOR}\2'


def get_available_resolutions(project_name, project_settings=None, log=None):
    if not project_settings:
        project_settings = get_project_settings(project_name)

    resolutions = list()

    project_attributes = Anatomy().get('attributes', None)
    assert project_attributes, "Can't find root paths to update render paths."

    project_width = project_attributes.get('resolutionWidth', None)
    project_height = project_attributes.get('resolutionHeight', None)
    if project_width and project_height:
        resolutions.append(RES_SEPARATOR.join([str(project_width), str(project_height)]))

    asset_entity = get_asset_by_name(project_name, get_current_asset_name())

    asset_width = asset_entity['data'].get('resolutionWidth', None)
    asset_height = asset_entity['data'].get('resolutionHeight', None)

    if asset_width and asset_height and _resolution_is_different(
            project_width, project_height, asset_width, asset_height,
    ):
        resolutions.append(RES_SEPARATOR.join([str(asset_width), str(asset_height)]))

    custom_resolutions = project_settings.get('global', {}).get('project_resolutions', {}).get('resolutions')
    if not custom_resolutions:
        if log:
            log.warning(
                "Can not retrieve project resolution overrides from settings or settings are empty. "
                "Can not add resolution to resolutions list to render subset creator."
            )
        return resolutions

    resolutions.extend(
        [
            re.sub(RES_REGEX, RES_RECONSTRUCTION, resolution)
            for resolution in custom_resolutions
        ]
    )
    return resolutions


def _resolution_is_different(first_width, first_height, second_width, second_height):
    return first_width != second_width or first_height != second_height


def extract_width_and_height(resolution):
    return resolution.split(RES_SEPARATOR) if resolution else [None, None]
