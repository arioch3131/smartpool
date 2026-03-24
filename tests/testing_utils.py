class WeakReferencableObject(object):
    """A simple object that supports weak references."""

    __slots__ = ("id", "data", "corrupted", "reset_count", "destroyed", "__weakref__")

    def __init__(self, id, data, corrupted=False):
        self.id = id
        self.data = data
        self.corrupted = corrupted
        self.reset_count = 0
        self.destroyed = False
