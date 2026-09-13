import time
from dataclasses import dataclass


@dataclass
class ProxyState:
    url: str
    success_count: int = 0
    failure_count: int = 0
    cooldown_until: float = 0.0

    @property
    def healthy(self) -> bool:
        return time.monotonic() >= self.cooldown_until


class ProxyManager:
    def __init__(self, urls: list[str]) -> None:
        self._states = [ProxyState(url) for url in urls]
        self._index = 0

    def next(self) -> str | None:
        healthy = [state for state in self._states if state.healthy]
        if not healthy:
            return None
        state = healthy[self._index % len(healthy)]
        self._index += 1
        return state.url

    def report(self, url: str | None, success: bool) -> None:
        if not url:
            return
        state = next((item for item in self._states if item.url == url), None)
        if not state:
            return
        if success:
            state.success_count += 1
            state.failure_count = 0
        else:
            state.failure_count += 1
            if state.failure_count >= 3:
                state.cooldown_until = time.monotonic() + min(
                    900, 60 * 2 ** (state.failure_count - 3)
                )
