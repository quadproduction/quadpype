import os
from quadpype.lib.version_utils import is_running_staging, is_running_locally

RESOURCES_DIR = os.path.dirname(os.path.abspath(__file__))


def get_resource(*args):
    """ Serves to simple resources access

    :param *args: should contain *subfolder* names and *filename* of
                  resource from the resource folder
    :type *args: list
    """
    return os.path.normpath(os.path.join(RESOURCES_DIR, *args))


def get_image_path(*args):
    """Helper function to get images.

    Args:
        *<str>: Filepath part items.
    """
    return get_resource("images", *args)


def get_liberation_font_path(bold=False, italic=False):
    font_name = "LiberationSans"
    suffix = ""
    if bold:
        suffix += "Bold"
    if italic:
        suffix += "Italic"

    if not suffix:
        suffix = "Regular"

    filename = "{}-{}.ttf".format(font_name, suffix)
    font_path = get_resource("fonts", font_name, filename)
    return font_path


def _get_app_image_variation_name():
    if is_running_locally():
        return "dev"
    elif is_running_staging():
        return "staging"

    return "default"

def get_app_icon_filepath(variation_name=None):
    if not variation_name:
        variation_name = _get_app_image_variation_name()
    return get_resource("icons", "quadpype_icon_{}.png".format(variation_name))


def get_app_splash_filepath(variation_name=None):
    if not variation_name:
        variation_name = _get_app_image_variation_name()
    return get_resource("icons", "quadpype_splash_{}.png".format(variation_name))
