"""The one stylesheet every page hotdocs writes inlines."""

from pathlib import Path


def stylesheet() -> str:
    return (Path(__file__).parent / "static" / "style.css").read_text(encoding="utf-8")


def style_element() -> str:
    return "<style>\n" + stylesheet() + "</style>"
