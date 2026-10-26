"""
`ModelResponse` -- the return shape of `complete()`.

Exactly one of `text` or `model_call_error` is populated, never both and
never neither (see interface/data/ModelResponse.md). `backend` is always
recorded on the output, even though a caller never supplies it as input
(R-ENDPOINT-002's resolution is entirely internal) -- captured purely for
observability ("which backend is flaky", D32).
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class ModelResponse:
    text: Optional[str]
    model: str
    backend: str
    model_call_error: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)