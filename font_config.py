from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "build"
FAMILY = "Caya Code"
POSTSCRIPT_FAMILY = "CayaCode"
VERSION = "1.001"
CASCADIA_FONT_NAME = "Cascadia Code Regular"


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
)
