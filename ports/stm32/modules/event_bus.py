# event_bus.py
class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, handler):
        """Subscribe a handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type, handler):
        """Unsubscribe a handler from a specific event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    async def publish(self, event_type, data=None):
        """Publish an event to all subscribers."""
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                await handler(data)
        else:
            print(f"No subscribers for event: {event_type}")
