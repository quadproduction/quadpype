import nuke
from . import Node

class Backdrop(Node):

    name: str

    @property
    def x(self):
        return self.nuke_entity['xpos'].value()

    @property
    def y(self):
        return self.nuke_entity['ypos'].value()

    @property
    def width(self):
        return self.nuke_entity['bdwidth'].value()

    @property
    def height(self):
        return self.nuke_entity['bdheight'].value()

    @property
    def z_order(self):
        return self.nuke_entity['z_order'].value()

    def get_nodes(self):
        return self.nuke_entity.getNodes()
