import os
import tempfile
import unicodedata
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTCollection, TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from font_config import (
    CASCADIA_FONT_FILE,
    CASCADIA_FONT_NAME,
    FAMILY,
    OUTPUT_DIR,
    POSTSCRIPT_FAMILY,
    STYLES,
    VERSION,
    Style,
)
from verify_font import verify_outputs


def environment_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return Path(value)


WINDOWS_FONTS = environment_path("WINDIR") / "Fonts"
FONT_DIRECTORIES = (
    environment_path("LOCALAPPDATA") / "Microsoft/Windows/Fonts",
    WINDOWS_FONTS,
)


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name = font["name"]
    name.removeNames(nameID=name_id)
    name.setName(value, name_id, 3, 1, 0x409)
    name.setName(value, name_id, 0, 3, 0)


def installed_font_path(filename: str) -> Path:
    candidates = [directory / filename for directory in FONT_DIRECTORIES]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    checked = "\n".join(map(str, candidates))
    raise FileNotFoundError(f"Installed font file not found: {filename}\nChecked:\n{checked}")


def font_names(font: TTFont, name_ids: tuple[int, ...]) -> set[str]:
    values: set[str] = set()
    for record in font["name"].names:
        if record.nameID in name_ids:
            try:
                values.add(record.toUnicode())
            except UnicodeDecodeError:
                continue
    return values


def rename_font(font: TTFont, style: Style) -> None:
    is_legacy_linked_style = style.name in {"Regular", "Bold"}
    legacy_family = FAMILY if is_legacy_linked_style else f"{FAMILY} {style.name}"
    legacy_style = style.name if is_legacy_linked_style else "Regular"
    full_name = FAMILY if style.name == "Regular" else f"{FAMILY} {style.name}"
    postscript_name = f"{POSTSCRIPT_FAMILY}-{style.name}"

    set_name(font, 0, "Cascadia Code © Microsoft; Microsoft YaHei © Microsoft/Founder.")
    set_name(font, 1, legacy_family)
    set_name(font, 2, legacy_style)
    set_name(font, 3, f"{FAMILY}; {style.name}; {VERSION}")
    set_name(font, 4, full_name)
    set_name(font, 5, f"Version {VERSION}")
    set_name(font, 6, postscript_name)
    font["name"].removeNames(nameID=13)
    set_name(font, 16, FAMILY)
    set_name(font, 17, style.name)


def extract_yahei(
    source: Path,
    destination: Path,
    expected_family: str,
) -> None:
    collection = TTCollection(source)
    try:
        if not collection.fonts:
            raise RuntimeError(f"No font faces found in {source}")

        matches = [
            font
            for font in collection.fonts
            if expected_family in font_names(font, (1, 16))
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one {expected_family} face in {source}, found {len(matches)}"
            )

        font = matches[0]
        # The Latin base has no vertical metrics. These optional CJK-only tables
        # cannot be merged with a missing peer by fontTools and are not needed in
        # horizontal source-code editors.
        for tag in ("vhea", "vmtx", "VDMX", "LTSH", "hdmx"):
            if tag in font:
                del font[tag]
        font.save(destination)
    finally:
        collection.close()


def instantiate_cascadia(source: Path, weight: int, destination: Path) -> None:
    with TTFont(source) as font:
        if "fvar" in font:
            axes = {axis.axisTag for axis in font["fvar"].axes}
            if "wght" not in axes:
                raise RuntimeError(f"Variable font has no wght axis: {source}")
            instantiateVariableFont(font, {"wght": weight}, inplace=True, overlap=True)
        elif weight != 400:
            raise RuntimeError(
                f"{source} is not variable; all non-Regular styles require a "
                "Cascadia Code variable TTF"
            )
        font.save(destination)


def cascadia_weight_range(source: Path) -> tuple[int, int]:
    with TTFont(source, lazy=True) as font:
        if CASCADIA_FONT_NAME not in font_names(font, (1, 16)):
            raise RuntimeError(f"Expected {CASCADIA_FONT_NAME} in {source}")
        if "fvar" not in font:
            weight = font["OS/2"].usWeightClass
            return weight, weight
        for axis in font["fvar"].axes:
            if axis.axisTag == "wght":
                return round(axis.minValue), round(axis.maxValue)
        raise RuntimeError(f"Variable font has no wght axis: {source}")


def translate_glyph(font: TTFont, glyph_name: str, dx: int) -> None:
    if not dx:
        return
    glyf = font["glyf"]
    glyph = glyf[glyph_name]
    if glyph.isComposite():
        for component in glyph.components:
            if hasattr(component, "x"):
                component.x += dx
    elif glyph.numberOfContours:
        glyph.coordinates.translate((dx, 0))
    glyph.recalcBounds(glyf)


def normalize_fallback_widths(
    font: TTFont,
    latin_codepoints: set[int],
    latin_glyphs: set[str],
) -> tuple[int, int]:
    cmap = font.getBestCmap()
    zero_name = cmap.get(ord("0"))
    if not zero_name:
        raise RuntimeError("Cascadia Code digit zero is missing")
    cell_width = font["hmtx"].metrics[zero_name][0]

    glyph_codepoints: dict[str, set[int]] = {}
    for codepoint, glyph_name in cmap.items():
        if codepoint not in latin_codepoints:
            glyph_codepoints.setdefault(glyph_name, set()).add(codepoint)

    changed = 0
    for glyph_name, (old_width, old_lsb) in font["hmtx"].metrics.items():
        if glyph_name in latin_glyphs or old_width == 0:
            continue
        codepoints = glyph_codepoints.get(glyph_name, set())
        if codepoints:
            target_width = (
                cell_width * 2
                if any(
                    unicodedata.east_asian_width(chr(codepoint)) in {"W", "F"}
                    for codepoint in codepoints
                )
                else cell_width
            )
        else:
            target_width = min(
                (cell_width, cell_width * 2),
                key=lambda width: abs(width - old_width),
            )
        if old_width == target_width:
            continue
        dx = round((target_width - old_width) / 2)
        translate_glyph(font, glyph_name, dx)
        font["hmtx"].metrics[glyph_name] = (target_width, old_lsb + dx)
        changed += 1

    font["hhea"].advanceWidthMax = max(
        advance for advance, _ in font["hmtx"].metrics.values()
    )
    return cell_width, changed


def normalize_metadata(font: TTFont, style: Style) -> None:
    rename_font(font, style)
    font["head"].fontRevision = float(VERSION)
    font["OS/2"].usWeightClass = style.weight
    font["OS/2"].xAvgCharWidth = font["hmtx"].metrics[font.getBestCmap()[ord("0")]][0]
    font["OS/2"].panose.bProportion = 9
    font["post"].isFixedPitch = 1

    bold = style.name == "Bold"
    regular = style.name == "Regular"
    font["head"].macStyle = (
        (font["head"].macStyle | 1)
        if bold
        else (font["head"].macStyle & ~1)
    )
    # fsSelection: clear italic/bold/regular/WWS, then set the actual style.
    # Every face differs only by weight, so the typographic names form a WWS
    # family even though legacy applications may expose extra weights separately.
    font["OS/2"].fsSelection &= ~(
        (1 << 0) | (1 << 5) | (1 << 6) | (1 << 8)
    )
    if bold:
        font["OS/2"].fsSelection |= 1 << 5
    elif regular:
        font["OS/2"].fsSelection |= 1 << 6
    font["OS/2"].fsSelection |= (1 << 7) | (1 << 8)

    for tag in ("DSIG", "STAT"):
        if tag in font:
            del font[tag]


def build_style(
    cascadia_path: Path,
    yahei_path: Path,
    output_path: Path,
    style: Style,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix=".caya-code-",
        dir=output_path.parent,
    ) as temp_dir:
        temp = Path(temp_dir)
        latin_path = temp / "latin.ttf"
        cjk_path = temp / "cjk.ttf"

        instantiate_cascadia(cascadia_path, style.weight, latin_path)
        extract_yahei(
            yahei_path,
            cjk_path,
            "Microsoft YaHei",
        )

        with TTFont(latin_path, lazy=True) as latin:
            latin_codepoints = set(latin.getBestCmap())
            latin_glyphs = set(latin.getGlyphOrder())

        merged = Merger().merge([str(latin_path), str(cjk_path)])
        try:
            cell_width, changed = normalize_fallback_widths(
                merged,
                latin_codepoints,
                latin_glyphs,
            )
            normalize_metadata(merged, style)
            merged.save(output_path, reorderTables=True)
            glyph_count = len(merged.getGlyphOrder())
        finally:
            merged.close()

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Built {output_path.name}: {glyph_count} glyphs, "
        f"{changed} normalized glyphs, cell={cell_width}, {size_mb:.1f} MiB"
    )


def normalize_family_metrics(outputs: list[tuple[Path, Style]]) -> None:
    regular_path = next(path for path, style in outputs if style.name == "Regular")
    with TTFont(regular_path, lazy=True) as regular:
        hhea = regular["hhea"]
        os2 = regular["OS/2"]
        reference_hhea = (hhea.ascent, hhea.descent, hhea.lineGap)
        reference_typo = (
            os2.sTypoAscender,
            os2.sTypoDescender,
            os2.sTypoLineGap,
        )

    win_metrics: list[tuple[int, int]] = []
    for path, _ in outputs:
        with TTFont(path, lazy=True) as font:
            win_metrics.append((font["OS/2"].usWinAscent, font["OS/2"].usWinDescent))
    win_ascent = max(ascent for ascent, _ in win_metrics)
    win_descent = max(descent for _, descent in win_metrics)

    for path, _ in outputs:
        normalized_path = path.with_suffix(".normalized.ttf")
        with TTFont(path) as font:
            hhea = font["hhea"]
            os2 = font["OS/2"]
            hhea.ascent, hhea.descent, hhea.lineGap = reference_hhea
            (
                os2.sTypoAscender,
                os2.sTypoDescender,
                os2.sTypoLineGap,
            ) = reference_typo
            os2.usWinAscent = win_ascent
            os2.usWinDescent = win_descent
            font.save(normalized_path, reorderTables=True)
        normalized_path.replace(path)


def main() -> None:
    cascadia_path = installed_font_path(CASCADIA_FONT_FILE)
    minimum_weight, maximum_weight = cascadia_weight_range(cascadia_path)
    yahei_sources: dict[str, Path] = {}
    for style in STYLES:
        if not minimum_weight <= style.weight <= maximum_weight:
            print(
                f"Skipping {style.name}: weight {style.weight} is outside "
                f"Cascadia Code's {minimum_weight}-{maximum_weight} range"
            )
            continue
        try:
            path = installed_font_path(style.yahei_file)
        except FileNotFoundError:
            print(
                f"Skipping {style.name}: {style.yahei_name} "
                f"({style.yahei_file}) is not installed"
            )
            continue
        yahei_sources[style.name] = path

    if "Regular" not in yahei_sources:
        raise RuntimeError("Microsoft YaHei Regular is required")

    print(f"Using {CASCADIA_FONT_NAME} ({CASCADIA_FONT_FILE}): {cascadia_path}")
    print(f"Font version: {VERSION}")
    for style in STYLES:
        if style.name in yahei_sources:
            print(
                f"Using {style.yahei_name} ({style.yahei_file}): "
                f"{yahei_sources[style.name]}"
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".caya-code-build-",
        dir=OUTPUT_DIR.parent,
    ) as staging:
        staging_dir = Path(staging)
        staged_outputs: list[tuple[Path, Style]] = []
        for style in STYLES:
            if style.name not in yahei_sources:
                continue
            staged_path = staging_dir / f"{POSTSCRIPT_FAMILY}-{style.name}.ttf"
            build_style(cascadia_path, yahei_sources[style.name], staged_path, style)
            staged_outputs.append((staged_path, style))

        normalize_family_metrics(staged_outputs)
        verify_outputs(staged_outputs)

        for staged_path, _ in staged_outputs:
            staged_path.replace(OUTPUT_DIR / staged_path.name)

    built_names = {path.name for path, _ in staged_outputs}
    for stale_path in OUTPUT_DIR.glob(f"{POSTSCRIPT_FAMILY}-*.ttf"):
        if stale_path.name not in built_names:
            stale_path.unlink()
            print(f"Removed stale output: {stale_path.name}")

    print(f"Published {len(staged_outputs)} fonts to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
