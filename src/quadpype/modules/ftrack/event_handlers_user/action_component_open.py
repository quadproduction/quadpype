import os
from quadpype_modules.ftrack.lib import BaseAction, statics_icon
from quadpype.lib import open_in_explorer


class ComponentOpen(BaseAction):
    """Custom action."""

    # Action identifier
    identifier = 'component.open'
    # Action label
    label = 'Open File'
    # Action icon
    icon = statics_icon("ftrack", "action_icons", "ComponentOpen.svg")

    def discover(self, session, entities, event):
        """ Validation """
        if len(entities) != 1 or entities[0].entity_type != 'FileComponent':
            return False

        return True

    def launch(self, session, entities, event):

        entity = entities[0]

        # Return error if component is on ftrack server
        location_name = entity['component_locations'][0]['location']['name']
        if location_name == 'ftrack.server':
            return {
                'success': False,
                'message': "This component is stored on ftrack server!"
            }

        # Get component filepath
        # TODO with locations it will be different???
        fpath = entity['component_locations'][0]['resource_identifier']
        fpath = os.path.normpath(os.path.dirname(fpath))

        if os.path.isdir(fpath):
            open_in_explorer(fpath)
        else:
            return {
                'success': False,
                'message': "Didn't find file: " + fpath
            }

        return {
            'success': True,
            'message': 'Component folder Opened'
        }


def register(session):
    """Register action. Called when used as an event plugin."""

    ComponentOpen(session).register()
