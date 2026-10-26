"""
Backend implementations behind R-ENDPOINT-002's resolve/dispatch split.

v1 implements exactly one (`AnthropicBackend`, R-ENDPOINT-003). A future
backend is an additive module here, not a registry/plugin mechanism
(deliberately out of scope, D18/D20).
"""

from .anthropic import AnthropicBackend

__all__ = ["AnthropicBackend"]