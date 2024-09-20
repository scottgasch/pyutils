from typing import Dict, List, Union

from typing_extensions import TypeAlias

RawJSONStr: TypeAlias = str
ParsedJSON: TypeAlias = Union[
    Dict[str, "ParsedJSON"], List["ParsedJSON"], str, int, float, bool, None
]
