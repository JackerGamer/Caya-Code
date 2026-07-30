from __future__ import annotations

from dataclasses import dataclass


DEFAULT_FAMILY = "Caya Code"
CASCADE_FONT_NAME = "Cascadia Code Regular"


@dataclass(frozen=True)
class Style:
    name: str
    weight: int
    yahei_name: str


STYLES = (
    Style("Light", 300, "Microsoft YaHei Light"),
    Style("SemiLight", 350, "Microsoft YaHei Semilight"),
    Style("Regular", 400, "Microsoft YaHei"),
    Style("SemiBold", 600, "Microsoft YaHei Semibold"),
    Style("Bold", 700, "Microsoft YaHei Bold"),
    Style("Heavy", 900, "Microsoft YaHei Heavy"),
)


def safe_filename(value: str) -> str:
    return "".join(ch for ch in value if ch.isascii() and ch.isalnum()) or "CayaCode"
