import os
import logging
from quadpype.settings import get_project_settings
from quadpype.hosts.blender.api.pipeline import set_custom_frame_offset


project_name = os.environ.get('AVALON_PROJECT', None)
if not project_name:
    logging.error("Can not retrieve project name from environment variable 'AVALON_PROJECT'.")
    quit()

project_settings = get_project_settings(project_name)

frame_offset_settings = project_settings.get('blender', {}).get('CustomFrameStart', None)
if not frame_offset_settings:
    logging.error("Can not retrieve settings for plugin 'CustomFrameStart'.")
    quit()

if not frame_offset_settings.get('enabled', False):
    logging.warning("Custom frame start has not been enabled and will not be set for current scene.")
    quit()

custom_frame_offset = frame_offset_settings.get('frame_start', 1)-1
set_custom_frame_offset(custom_frame_offset)
logging.info(f"Custom frame offset with a value of {custom_frame_offset} have been applied to scenes properties.")
