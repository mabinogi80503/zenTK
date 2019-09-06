class Observable(object):
    def __init__(self):
        self._observers = []

    def subscribe(self, oberser):
        if oberser not in self._observers:
            self._observers.append(oberser)

    def unsubscribe(self, oberser):
        self._observers.remove(oberser)

    def notify(self, event=None):
        for oberser in self._observers:
            oberser(event)
