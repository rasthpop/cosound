from collections import defaultdict


class SequentialIdGenerator:
    """Deterministic ids such as `ses_000001`, counted per prefix."""

    def __init__(self) -> None:
        self._counters: defaultdict[str, int] = defaultdict(int)

    def new(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}_{self._counters[prefix]:06d}"
