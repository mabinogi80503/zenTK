class Subscriber(object):
    def __init__(self, name, handler):
        self.name = name
        self.handler = handler


class Publisher(object):
    def __init__(self):
        self._events = {}

    def create_event(self, name):
        if name in self._events.keys():
            return None
        self._events[name] = {}
        return self._events[name]

    def boardcast(self, event, data):
        subscribers = self._events.get(event, None)
        for s in subscribers.values():
            s.handler(data)

    def registe(self, event, subscriber):
        subscribers = self._events.get(event, None)
        if subscribers is None:
            subscribers = self.create_event(event)
        subscribers.update({subscriber.name: subscriber})

    def unregiste(self, event, subscriber):
        subscribers = self._events.get(event, None)
        if subscribers is None:
            return None
        del subscribers[subscriber.name]
