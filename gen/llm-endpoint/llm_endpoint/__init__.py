"""
llm-endpoint: the single, vendor-agnostic transport for every model call
this pipeline makes (D30).

Public surface is exactly `complete()` and `ModelResponse` --
everything else in this package is internal (resolution, backends, the
call log) and MUST NOT be imported by callers.
"""

from .endpoint import complete, UnknownModelBackendError
from .model_response import ModelResponse

__all__ = ["complete", "ModelResponse", "UnknownModelBackendError"]