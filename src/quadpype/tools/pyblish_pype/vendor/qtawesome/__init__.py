"""
qtawesome - use font-awesome in PyQt / PySide applications

This is a port to Python of the C++ QtAwesome library by Rick Blommers
"""
from .iconic_font import IconicFont, set_global_defaults
from .animation import Pulse, Spin
from ._version import version_info, __version__

_resource = {'iconic': None, }


def _instance():
    if _resource['iconic'] is None:
        _resource['iconic'] = IconicFont(('fa', 'fontawesome-webfont.ttf', 'fontawesome-webfont-charmap.json'),
                                         ('ei', 'elusiveicons-webfont.ttf', 'elusiveicons-webfont-charmap.json'))
    return _resource['iconic']


def icon(*args, **kwargs):
    return _instance().icon(*args, **kwargs)


def load_font(*args, **kwargs):
    return _instance().load_font(*args, **kwargs)


def charmap(prefixed_name):
    prefix, name = prefixed_name.split('.')
    return _instance().charmap[prefix][name]


def font(*args, **kwargs):
    return _instance().font(*args, **kwargs)


def set_defaults(**kwargs):
    return set_global_defaults(**kwargs)
