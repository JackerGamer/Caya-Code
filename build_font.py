from __future__ import annotations

import argparse
import os
import tempfile
import unicodedata
import winreg
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTCollection, TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from font_config import CASCADE_FONT_NAME, DEFAULT_FAMILY, STYLES, Style, safe_filename


def environment_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return Path(value)


WINDOWS_FONTS = environment_path("WINDIR") / "Fonts"
FONT_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
FONT_REGISTRY_LOCATIONS = (
    (winreg.HKEY_CURRENT_USER, environment_path("LOCALAPPDATA") / "Microsoft/Windows/Fonts"),
    (winreg.HKEY_LOCAL_MACHINE, WINDOWS_FONTS),
)


@dataclass(frozen=True)
class FontSource:
    path: Path
    name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Caya Code."
    )
    parser.add_argument("--family", default=DEFAULT_FAMILY, help="Font family name")
    parser.add_argument("--output", type=Path, default=Path("build"))
    parser.add_argument(
        "--version",
        help="Font version; defaults to build time",
    )
    return parser.parse_args()


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name = font["name"]
    name.removeNames(nameID=name_id)
    name.setName(value, name_id, 3, 1, 0x409)
    name.setName(value, name_id, 0, 3, 0)


def registered_font_path(font_name: str) -> Path:
    target = font_name.casefold()
    missing_paths: list[Path] = []

    for hive, relative_base in FONT_REGISTRY_LOCATIONS:
        try:
            key = winreg.OpenKey(hive, FONT_REGISTRY_KEY)
        except FileNotFoundError:
            continue

        with key:
            index = 0
            while True:
                try:
                    value_name, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                index += 1

                display_name = value_name
                if display_name.casefold().endswith(" (truetype)"):
                    display_name = display_name[: -len(" (TrueType)")]
                aliases = {alias.strip().casefold() for alias in display_name.split(" & ")}
                if target not in aliases:
                    continue

                path = Path(os.path.expandvars(str(value)))
                if not path.is_absolute():
                    path = relative_base / path
                if path.is_file():
                    return path.resolve()
                missing_paths.append(path)

    details = ""
    if missing_paths:
        details = "\nRegistered paths not found:\n" + "\n".join(map(str, missing_paths))
    raise FileNotFoundError(f"Installed font not found: {font_name}{details}")


def font_names(font: TTFont, name_ids: tuple[int, ...]) -> set[str]:
    values: set[str] = set()
    for record in font["name"].names:
        if record.nameID in name_ids:
            try:
                values.add(record.toUnicode())
            except UnicodeDecodeError:
                continue
    return values


def rename_font(font: TTFont, family: str, style: Style, version: str) -> None:
    ps_family = safe_filename(family)
    is_legacy_linked_style = style.name in {"Regular", "Bold"}
    legacy_family = family if is_legacy_linked_style else f"{family} {style.name}"
    legacy_style = style.name if is_legacy_linked_style else "Regular"
    full_name = family if style.name == "Regular" else f"{family} {style.name}"
    postscript_name = f"{ps_family}-{style.name}"

    set_name(font, 0, "Cascadia Code © Microsoft; Microsoft YaHei © Microsoft/Founder.")
    set_name(font, 1, legacy_family)
    set_name(font, 2, legacy_style)
    set_name(font, 3, f"{family}; {style.name}; {version}")
    set_name(font, 4, full_name)
    set_name(font, 5, f"Version {version}")
    set_name(font, 6, postscript_name)
    font["name"].removeNames(nameID=13)
    set_name(font, 16, family)
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


def make_cjk_double_width(font: TTFont, latin_codepoints: set[int]) -> tuple[int, int]:
    cmap = font.getBestCmap()
    zero_name = cmap.get(ord("0"))
    if not zero_name:
        raise RuntimeError("Cascadia Code digit zero is missing")
    cell_width = font["hmtx"].metrics[zero_name][0]
    target_width = cell_width * 2

    glyph_codepoints: dict[str, set[int]] = {}
    for codepoint, glyph_name in cmap.items():
        if codepoint not in latin_codepoints:
            glyph_codepoints.setdefault(glyph_name, set()).add(codepoint)

    changed = 0
    for glyph_name, codepoints in glyph_codepoints.items():
        if not any(unicodedata.east_asian_width(chr(cp)) in {"W", "F"} for cp in codepoints):
            continue
        old_width, old_lsb = font["hmtx"].metrics[glyph_name]
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


def normalize_metadata(font: TTFont, family: str, style: Style, version: str) -> None:
    rename_font(font, family, style, version)
    font["OS/2"].usWeightClass = style.weight
    font["OS/2"].xAvgCharWidth = font["hmtx"].metrics[font.getBestCmap()[ord("0")]][0]
    font["OS/2"].panose.bProportion = 9
    font["post"].isFixedPitch = 1

    bold = style.name == "Bold"
    font["head"].macStyle = (font["head"].macStyle | 1) if bold else (font["head"].macStyle & ~1)
    # fsSelection: clear italic/bold/regular, then set the appropriate style bit.
    font["OS/2"].fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6))
    font["OS/2"].fsSelection |= (1 << 5) if bold else (1 << 6)

    for tag in ("DSIG", "STAT"):
        if tag in font:
            del font[tag]


def build_style(
    cascadia_path: Path,
    yahei_source: FontSource,
    output_path: Path,
    family: str,
    style: Style,
    version: str,
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
            yahei_source.path,
            cjk_path,
            "Microsoft YaHei",
        )

        with TTFont(latin_path, lazy=True) as latin:
            latin_codepoints = set(latin.getBestCmap())

        merged = Merger().merge([str(latin_path), str(cjk_path)])
        try:
            cell_width, changed = make_cjk_double_width(merged, latin_codepoints)
            normalize_metadata(merged, family, style, version)
            temporary_output = temp / output_path.name
            merged.save(temporary_output, reorderTables=True)
            glyph_count = len(merged.getGlyphOrder())
        finally:
            merged.close()

        temporary_output.replace(output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Built {output_path.name}: {glyph_count} glyphs, "
        f"{changed} double-width glyphs, cell={cell_width}, {size_mb:.1f} MiB"
    )


def main() -> None:
    args = parse_args()
    version = args.version or datetime.now(timezone.utc).strftime("%Y%m%d.%H%M%SZ")
    cascadia_path = registered_font_path(CASCADE_FONT_NAME)
    minimum_weight, maximum_weight = cascadia_weight_range(cascadia_path)
    yahei_sources: dict[str, FontSource] = {}
    for style in STYLES:
        if not minimum_weight <= style.weight <= maximum_weight:
            print(
                f"Skipping {style.name}: weight {style.weight} is outside "
                f"Cascadia Code's {minimum_weight}-{maximum_weight} range"
            )
            continue
        try:
            path = registered_font_path(style.yahei_name)
        except FileNotFoundError:
            print(f"Skipping {style.name}: {style.yahei_name} is not installed")
            continue
        yahei_sources[style.name] = FontSource(path, style.yahei_name)

    if not yahei_sources:
        raise RuntimeError("No matching Cascadia Code and Microsoft YaHei weights found")

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Using {CASCADE_FONT_NAME}: {cascadia_path}")
    print(f"Build version: {version}")
    for style in STYLES:
        source = yahei_sources.get(style.name)
        if source:
            print(f"Using {source.name}: {source.path}")

    ps_family = safe_filename(args.family)
    for style in STYLES:
        if style.name not in yahei_sources:
            stale_path = output_dir / f"{ps_family}-{style.name}.ttf"
            if stale_path.is_file():
                stale_path.unlink()
                print(f"Removed stale output: {stale_path.name}")

    for style in STYLES:
        if style.name not in yahei_sources:
            continue
        build_style(
            cascadia_path,
            yahei_sources[style.name],
            output_dir / f"{ps_family}-{style.name}.ttf",
            args.family,
            style,
            version,
        )


if __name__ == "__main__":
    main()
