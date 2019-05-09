from typing import Callable


class DependencyManager:
    def __init__(self):
        self.functions = []

    def index_of(self, name):
        for index, (locname, b) in enumerate(self.functions):
            if locname == name:
                return index

        raise Exception("Cannot find dependency {}".format(name))

    def register(self, f: Callable, name: str = None, before: str = None, after: str = None):
        if name is None:
            name = f.__name__

        insertion_index = -1

        if before is not None:
            insertion_index = self.index_of(before)

        if after is not None:
            index = self.index_of(after)
            if insertion_index != -1:
                if index <= insertion_index:
                    raise Exception("Conflict in planning: before {} but after {}".format(index, index))
            else:
                insertion_index = index + 1

        if insertion_index == -1:
            insertion_index = len(self.functions)

        self.functions.insert(insertion_index, (name, f))

    def register_all(self, *args: Callable):
        for x in args:
            self.register(x)

    def call(self):
        for x in self.functions:
            print("Running {}".format(x[0]))
            x[1]()
