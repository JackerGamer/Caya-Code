from pathlib import Path

from fontTools.ttLib import TTFont

from font_config import (
    FAMILY,
    OUTPUT_DIR,
    POSTSCRIPT_FAMILY,
    STYLES,
    VERSION,
    Style,
)


SAMPLES = "A0=>!=ǐ中文，。￥あ"


def english_name(font: TTFont, name_id: int) -> str:
    for record in font["name"].names:
        if record.nameID == name_id and record.platformID == 3 and record.langID == 0x409:
            return record.toUnicode()
    raise RuntimeError(f"Missing English name ID {name_id}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def vertical_metrics(font: TTFont) -> tuple[int, ...]:
    hhea = font["hhea"]
    os2 = font["OS/2"]
    return (
        hhea.ascent,
        hhea.descent,
        hhea.lineGap,
        os2.sTypoAscender,
        os2.sTypoDescender,
        os2.sTypoLineGap,
        os2.usWinAscent,
        os2.usWinDescent,
    )


def verify(path: Path, style: Style) -> None:
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        missing = [char for char in SAMPLES if ord(char) not in cmap]
        require(not missing, f"{path.name}: missing sample characters {missing!r}")

        cell = font["hmtx"].metrics[cmap[ord("0")]][0]
        valid_widths = {0, cell, cell * 2}
        invalid_widths = [
            (f"U+{codepoint:04X}", font["hmtx"].metrics[glyph_name][0])
            for codepoint, glyph_name in cmap.items()
            if font["hmtx"].metrics[glyph_name][0] not in valid_widths
        ]
        require(
            not invalid_widths,
            f"{path.name}: characters outside the 0/1/2-cell grid: "
            f"{invalid_widths[:10]!r}",
        )
        invalid_glyph_widths = [
            (glyph_name, advance)
            for glyph_name, (advance, _) in font["hmtx"].metrics.items()
            if advance % cell
        ]
        require(
            not invalid_glyph_widths,
            f"{path.name}: glyphs outside the cell grid: "
            f"{invalid_glyph_widths[:10]!r}",
        )

        for char in "A0=>!=ǐ":
            advance = font["hmtx"].metrics[cmap[ord(char)]][0]
            require(
                advance == cell,
                f"{path.name}: {char!r} width {advance}, expected {cell}",
            )
        for char in "中文，。￥あ":
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

        legacy_linked = style.name in {"Regular", "Bold"}
        expected_legacy_family = FAMILY if legacy_linked else f"{FAMILY} {style.name}"
        expected_legacy_style = style.name if legacy_linked else "Regular"
        expected_full_name = (
            FAMILY if style.name == "Regular" else f"{FAMILY} {style.name}"
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
            english_name(font, 3) == f"{FAMILY}; {style.name}; {VERSION}",
            f"{path.name}: wrong unique ID",
        )
        require(
            english_name(font, 4) == expected_full_name,
            f"{path.name}: wrong full name",
        )
        require(
            english_name(font, 5) == f"Version {VERSION}",
            f"{path.name}: wrong version",
        )
        require(
            english_name(font, 6) == f"{POSTSCRIPT_FAMILY}-{style.name}",
            f"{path.name}: wrong PostScript name",
        )
        require(
            english_name(font, 16) == FAMILY,
            f"{path.name}: wrong typographic family",
        )
        require(
            english_name(font, 17) == style.name,
            f"{path.name}: wrong typographic style",
        )
        require(
            not any(record.nameID == 13 for record in font["name"].names),
            f"{path.name}: unexpected description metadata",
        )
        require(
            abs(font["head"].fontRevision - float(VERSION)) < 1 / 65_536,
            f"{path.name}: wrong head fontRevision",
        )
        require(
            font["OS/2"].usWeightClass == style.weight,
            f"{path.name}: wrong weight class",
        )

        bold = style.name == "Bold"
        regular = style.name == "Regular"
        require(
            bool(font["head"].macStyle & 1) == bold,
            f"{path.name}: wrong macStyle",
        )
        require(
            bool(font["OS/2"].fsSelection & (1 << 5)) == bold,
            f"{path.name}: wrong fsSelection bold bit",
        )
        require(
            bool(font["OS/2"].fsSelection & (1 << 6)) == regular,
            f"{path.name}: wrong fsSelection regular bit",
        )
        require(
            bool(font["OS/2"].fsSelection & (1 << 7)),
            f"{path.name}: USE_TYPO_METRICS is not set",
        )
        require(
            bool(font["OS/2"].fsSelection & (1 << 8)),
            f"{path.name}: WWS is not set",
        )
        require(
            not bool(font["OS/2"].fsSelection & (1 << 0)),
            f"{path.name}: unexpectedly marked italic",
        )

        print(
            f"OK {path.name}: style={style.name}, glyphs={len(font.getGlyphOrder())}, "
            f"cell={cell}, Version {VERSION}"
        )


def verify_outputs(outputs: list[tuple[Path, Style]]) -> None:
    require(bool(outputs), "No output fonts found")
    require(
        any(style.name == "Regular" for _, style in outputs),
        "Regular output is required",
    )

    reference_metrics: tuple[int, ...] | None = None
    reference_cmap: set[int] | None = None
    for path, style in outputs:
        require(path.is_file(), f"Missing output font: {path}")
        verify(path, style)
        with TTFont(path, lazy=True) as font:
            metrics = vertical_metrics(font)
            cmap = set(font.getBestCmap())
        if reference_metrics is None:
            reference_metrics = metrics
            reference_cmap = cmap
            continue
        require(metrics == reference_metrics, f"{path.name}: inconsistent vertical metrics")
        require(cmap == reference_cmap, f"{path.name}: inconsistent character coverage")


def main() -> None:
    configured_names = {f"{POSTSCRIPT_FAMILY}-{style.name}.ttf" for style in STYLES}
    unexpected = [
        path.name
        for path in OUTPUT_DIR.glob(f"{POSTSCRIPT_FAMILY}-*.ttf")
        if path.name not in configured_names
    ]
    require(not unexpected, f"Unexpected output fonts: {unexpected!r}")
    outputs = [
        (OUTPUT_DIR / f"{POSTSCRIPT_FAMILY}-{style.name}.ttf", style)
        for style in STYLES
        if (OUTPUT_DIR / f"{POSTSCRIPT_FAMILY}-{style.name}.ttf").is_file()
    ]
    verify_outputs(outputs)


if __name__ == "__main__":
    main()
