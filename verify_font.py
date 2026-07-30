from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont

from font_config import DEFAULT_FAMILY, STYLES, safe_filename


SAMPLES = "A0=>!=中文，。￥あ"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    parser.add_argument("--output", type=Path, default=Path("build"))
    parser.add_argument("--version")
    return parser.parse_args()


def english_name(font: TTFont, name_id: int) -> str:
    for record in font["name"].names:
        if record.nameID == name_id and record.platformID == 3 and record.langID == 0x409:
            return record.toUnicode()
    raise RuntimeError(f"Missing English name ID {name_id}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(
    path: Path,
    expected_family: str,
    expected_style: str,
    expected_weight: int,
    expected_version: str | None = None,
) -> None:
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        missing = [char for char in SAMPLES if ord(char) not in cmap]
        require(not missing, f"{path.name}: missing sample characters {missing!r}")

        cell = font["hmtx"].metrics[cmap[ord("0")]][0]
        for char in "A0=>!=":
            advance = font["hmtx"].metrics[cmap[ord(char)]][0]
            require(
                advance == cell,
                f"{path.name}: {char!r} width {advance}, expected {cell}",
            )
        for char in "中文，。あ":
            advance = font["hmtx"].metrics[cmap[ord(char)]][0]
            require(
                advance == cell * 2,
                f"{path.name}: {char!r} width {advance}, expected {cell * 2}",
            )

        require(font["post"].isFixedPitch == 1, f"{path.name}: not marked fixed-pitch")
        require("fvar" not in font, f"{path.name}: output is still variable")
        require("GSUB" in font, f"{path.name}: missing GSUB programming ligatures")
        features = {
            record.FeatureTag for record in font["GSUB"].table.FeatureList.FeatureRecord
        }
        require(
            "calt" in features,
            f"{path.name}: missing calt programming-ligature feature",
        )

        legacy_linked = expected_style in {"Regular", "Bold"}
        expected_legacy_family = (
            expected_family if legacy_linked else f"{expected_family} {expected_style}"
        )
        expected_legacy_style = expected_style if legacy_linked else "Regular"
        expected_full_name = (
            expected_family
            if expected_style == "Regular"
            else f"{expected_family} {expected_style}"
        )
        require(
            english_name(font, 1) == expected_legacy_family,
            f"{path.name}: wrong family",
        )
        require(
            english_name(font, 2) == expected_legacy_style,
            f"{path.name}: wrong subfamily",
        )
        require(
            english_name(font, 4) == expected_full_name,
            f"{path.name}: wrong full name",
        )
        require(
            english_name(font, 6) == f"{safe_filename(expected_family)}-{expected_style}",
            f"{path.name}: wrong PostScript name",
        )
        require(
            english_name(font, 16) == expected_family,
            f"{path.name}: wrong typographic family",
        )
        require(
            english_name(font, 17) == expected_style,
            f"{path.name}: wrong typographic style",
        )
        if expected_version:
            require(
                english_name(font, 5) == f"Version {expected_version}",
                f"{path.name}: wrong version",
            )
        require(
            font["OS/2"].usWeightClass == expected_weight,
            f"{path.name}: wrong weight class",
        )

        bold = expected_style == "Bold"
        require(
            bool(font["head"].macStyle & 1) == bold,
            f"{path.name}: wrong macStyle",
        )
        require(
            bool(font["OS/2"].fsSelection & (1 << 5)) == bold,
            f"{path.name}: wrong fsSelection bold bit",
        )
        require(
            not bool(font["OS/2"].fsSelection & (1 << 0)),
            f"{path.name}: unexpectedly marked italic",
        )

        print(
            f"OK {path.name}: family={english_name(font, 16)!r}, "
            f"style={english_name(font, 17)}, glyphs={len(font.getGlyphOrder())}, "
            f"cell={cell}, {english_name(font, 5)}"
        )


def main() -> None:
    args = parse_args()
    prefix = safe_filename(args.family)
    outputs = [
        (args.output / f"{prefix}-{style.name}.ttf", style.name, style.weight)
        for style in STYLES
        if (args.output / f"{prefix}-{style.name}.ttf").is_file()
    ]
    require(bool(outputs), f"No output fonts found in {args.output}")
    for path, style, weight in outputs:
        verify(path, args.family, style, weight, args.version)


if __name__ == "__main__":
    main()
