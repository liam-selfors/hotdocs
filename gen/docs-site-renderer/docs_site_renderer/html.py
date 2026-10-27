"""Tiny HTML-escaping helper shared by the renderer's templating code."""

from __future__ import annotations

import html as _html
from typing import Any


def esc(value: Any) -> str:
    """HTML-escapes `value`'s string form. `None` renders as an empty
    string rather than the literal text "None"."""
    return _html.escape("" if value is None else str(value), quote=True)