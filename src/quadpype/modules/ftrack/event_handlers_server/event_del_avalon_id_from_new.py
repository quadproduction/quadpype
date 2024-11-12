from quadpype_modules.ftrack.lib import BaseEvent
from quadpype_modules.ftrack.lib.database_sync import CUST_ATTR_ID_KEY
from quadpype_modules.ftrack.event_handlers_server.event_sync_to_database import (
    SyncToQuadPypeEvent
)


class DelQuadPypeIdFromNew(BaseEvent):
    '''
    This event removes QuadPypeId from custom attributes of new entities
    Result:
    - 'Copy->Pasted' entities won't have same QuadPypeID as source entity

    Priority of this event must be less than SyncToQuadPype event
    '''
    priority = SyncToQuadPypeEvent.priority - 1
    ignore_me = True

    def launch(self, session, event):
        created = []
        entities = event['data']['entities']
        for entity in entities:
            try:
                entity_id = entity['entityId']

                if entity.get('action', None) == 'add':
                    id_dict = entity['changes']['id']

                    if id_dict['new'] is not None and id_dict['old'] is None:
                        created.append(id_dict['new'])

                elif (
                    entity.get('action', None) == 'update' and
                    CUST_ATTR_ID_KEY in entity['keys'] and
                    entity_id in created
                ):
                    ftrack_entity = session.get(
                        self._get_entity_type(entity),
                        entity_id
                    )

                    cust_attrs = ftrack_entity["custom_attributes"]
                    if cust_attrs[CUST_ATTR_ID_KEY]:
                        cust_attrs[CUST_ATTR_ID_KEY] = ""
                        session.commit()

            except Exception:
                session.rollback()
                continue


def register(session):
    '''Register plugin. Called when used as an plugin.'''
    DelQuadPypeIdFromNew(session).register()
