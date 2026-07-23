from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont


SAMPLES = "A0=>!=中文，。￥あ"
STYLES = {
    "Light": 300,
    "SemiLight": 350,
    "Regular": 400,
    "SemiBold": 600,
    "Bold": 700,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="Caya Code")
    parser.add_argument("--output", type=Path, default=Path("build/fonts"))
    args, _ = parser.parse_known_args()
    return args


def safe_filename(value: str) -> str:
    return "".join(ch for ch in value if ch.isascii() and ch.isalnum()) or "CayaCode"


def english_name(font: TTFont, name_id: int) -> str:
    for record in font["name"].names:
        if record.nameID == name_id and record.platformID == 3 and record.langID == 0x409:
            return record.toUnicode()
    raise AssertionError(f"Missing English name ID {name_id}")


def verify(path: Path, expected_family: str, expected_style: str, expected_weight: int) -> None:
    font = TTFont(path)
    cmap = font.getBestCmap()
    missing = [char for char in SAMPLES if ord(char) not in cmap]
    assert not missing, f"{path.name}: missing sample characters {missing!r}"

    cell = font["hmtx"].metrics[cmap[ord("0")]][0]
    for char in "中文，。あ":
        advance = font["hmtx"].metrics[cmap[ord(char)]][0]
        assert advance == cell * 2, (
            f"{path.name}: {char!r} width {advance}, expected {cell * 2}"
        )

    assert font["post"].isFixedPitch == 1
    assert "GSUB" in font, f"{path.name}: missing GSUB programming ligatures"
    features = {
        record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord
    }
    assert "calt" in features, f"{path.name}: missing calt programming-ligature feature"
    assert english_name(font, 16) == expected_family
    assert english_name(font, 17) == expected_style
    assert font["OS/2"].usWeightClass == expected_weight
    print(
        f"OK {path.name}: family={english_name(font, 16)!r}, "
        f"style={english_name(font, 17)}, glyphs={len(font.getGlyphOrder())}, cell={cell}"
    )
    font.close()


def main() -> None:
    args = parse_args()
    prefix = safe_filename(args.family)
    paths = [args.output / f"{prefix}-{style}.ttf" for style in STYLES]
    missing = [path for path in paths if not path.is_file()]
    assert not missing, f"Missing output fonts: {missing}"
    for path, (style, weight) in zip(paths, STYLES.items()):
        verify(path, args.family, style, weight)


if __name__ == "__main__":
    main()
