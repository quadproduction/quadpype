import nuke

class Node:

    id: str
    name: str

    def __init__(self, nuke_entity: nuke.Node):
        self.nuke_entity = nuke_entity

    @property
    def name(self):
        return self.nuke_entity.name()

    @property
    def x(self):
        return self.nuke_entity.xpos()

    @property
    def y(self):
        return self.nuke_entity.ypos()

    @property
    def width(self):
        return self.nuke_entity.screenWidth()

    @property
    def height(self):
        return self.nuke_entity.screenHeight()

    @property
    def nuke_class(self):
        return self.nuke_entity.Class()

    @property
    def position(self):
        return self.x, self.y

    @property
    def size(self):
        return self.width, self.height

    @property
    def exists(self):
        return nuke.toNode(self.name)
