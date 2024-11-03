from typing import Dict, Protocol

"""Type hint for dataclasses."""


class Dataclass(Protocol):
    """Dataclass isn't really a first class type and therefore there is no offical
    type hint for Dataclasses in Python (yet).  If you need one, here's a suitable
    stand in.  Example usage::

        def f(d: Dataclass) -> Any:
            pass

        def g(d: Dict[str, Any]) -> Dataclass:
            pass
    """

    __dataclass_fields__: Dict
