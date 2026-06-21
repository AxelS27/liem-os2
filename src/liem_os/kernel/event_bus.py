import asyncio
from typing import Dict, Any, Callable, List, Awaitable

class EventBus:
    """
    Asynchronous Pub/Sub Event Bus.
    Eliminates database polling by notifying listeners when events are published.
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        if channel not in self._listeners:
            self._listeners[channel] = []
        self._listeners[channel].append(callback)

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        if channel in self._listeners:
            # Dispatch all callbacks concurrently
            tasks = [callback(event) for callback in self._listeners[channel]]
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        import traceback
                        traceback.print_exception(type(r), r, r.__traceback__)
                        raise r
