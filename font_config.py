from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "build"
FAMILY = "Caya Code"
POSTSCRIPT_FAMILY = "CayaCode"
VERSION = "1.002"
CASCADIA_FONT_NAME = "Cascadia Code"
CASCADIA_FONT_FILE = "CascadiaCode.ttf"


@dataclass(frozen=True)
class Style:
    name: str
    weight: int
    yahei_name: str
    yahei_file: str


STYLES = (
    Style("Light", 300, "Microsoft YaHei Light", "msyhl.ttc"),
    Style("SemiLight", 350, "Microsoft YaHei Semilight", "msyhsl.ttc"),
    Style("Regular", 400, "Microsoft YaHei", "msyh.ttc"),
    Style("SemiBold", 600, "Microsoft YaHei Semibold", "msyhsb.ttc"),
    Style("Bold", 700, "Microsoft YaHei Bold", "msyhbd.ttc"),
)
