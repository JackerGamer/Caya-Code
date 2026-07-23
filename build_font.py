from __future__ import annotations

import argparse
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTCollection, TTFont
from fontTools.varLib.instancer import instantiateVariableFont


DEFAULT_FAMILY = "Caya Code"
WINDOWS_FONTS = Path(r"C:\Windows\Fonts")


@dataclass(frozen=True)
class Style:
    name: str
    weight: int
    yahei_file: str


STYLES = (
    Style("Light", 300, "msyhl.ttc"),
    Style("SemiLight", 350, "msyhsl.ttc"),
    Style("Regular", 400, "msyh.ttc"),
    Style("SemiBold", 600, "msyhsb.ttc"),
    Style("Bold", 700, "msyhbd.ttc"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a personal-use programming font from Cascadia Code and Microsoft YaHei."
    )
    parser.add_argument("--family", default=DEFAULT_FAMILY, help="Output font family name")
    parser.add_argument(
        "--cascadia",
        type=Path,
        default=WINDOWS_FONTS / "CascadiaCode.ttf",
        help="Cascadia Code variable TTF",
    )
    parser.add_argument(
        "--font-dir",
        type=Path,
        default=WINDOWS_FONTS,
        help="Directory containing msyh.ttc, msyhl.ttc, and msyhbd.ttc",
    )
    parser.add_argument("--output", type=Path, default=Path("build/fonts"))
    return parser.parse_args()


def safe_filename(value: str) -> str:
    return "".join(ch for ch in value if ch.isascii() and ch.isalnum()) or "CayaCode"


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name = font["name"]
    name.removeNames(nameID=name_id)
    name.setName(value, name_id, 3, 1, 0x409)
    name.setName(value, name_id, 0, 3, 0)


def rename_font(font: TTFont, family: str, style: Style) -> None:
    ps_family = safe_filename(family)
    is_legacy_linked_style = style.name in {"Regular", "Bold"}
    legacy_family = family if is_legacy_linked_style else f"{family} {style.name}"
    legacy_style = style.name if is_legacy_linked_style else "Regular"
    full_name = family if style.name == "Regular" else f"{family} {style.name}"
    postscript_name = f"{ps_family}-{style.name}"

    set_name(font, 0, "Cascadia Code © Microsoft; Microsoft YaHei © Microsoft/Founder.")
    set_name(font, 1, legacy_family)
    set_name(font, 2, legacy_style)
    set_name(font, 3, f"{family}; {style.name}; personal build")
    set_name(font, 4, full_name)
    set_name(font, 5, "Version 1.000")
    set_name(font, 6, postscript_name)
    set_name(font, 13, "Personal-use local build. Do not redistribute without the required font licenses.")
    set_name(font, 16, family)
    set_name(font, 17, style.name)


def extract_yahei(source: Path, destination: Path) -> None:
    collection = TTCollection(source)
    if not collection.fonts:
        raise RuntimeError(f"No font faces found in {source}")

    # Face 0 is Microsoft YaHei; face 1 is Microsoft YaHei UI.
    font = collection.fonts[0]
    # The Latin base has no vertical metrics. These optional CJK-only tables
    # cannot be merged with a missing peer by fontTools and are not needed in
    # horizontal source-code editors.
    for tag in ("vhea", "vmtx", "VDMX", "LTSH", "hdmx"):
        if tag in font:
            del font[tag]
    font.save(destination)
    font.close()
    collection.close()


def instantiate_cascadia(source: Path, weight: int, destination: Path) -> None:
    font = TTFont(source)
    if "fvar" in font:
        axes = {axis.axisTag for axis in font["fvar"].axes}
        if "wght" not in axes:
            raise RuntimeError(f"Variable font has no wght axis: {source}")
        instantiateVariableFont(font, {"wght": weight}, inplace=True, overlap=True)
    elif weight != 400:
        raise RuntimeError(
            f"{source} is not variable; all non-Regular styles require a Cascadia Code variable TTF"
        )
    font.save(destination)
    font.close()


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


def normalize_metadata(font: TTFont, family: str, style: Style) -> None:
    rename_font(font, family, style)
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
    yahei_path: Path,
    output_path: Path,
    family: str,
    style: Style,
) -> None:
    with tempfile.TemporaryDirectory(prefix="caya-code-") as temp_dir:
        temp = Path(temp_dir)
        latin_path = temp / "latin.ttf"
        cjk_path = temp / "cjk.ttf"

        instantiate_cascadia(cascadia_path, style.weight, latin_path)
        extract_yahei(yahei_path, cjk_path)

        latin = TTFont(latin_path, lazy=True)
        latin_codepoints = set(latin.getBestCmap())
        latin.close()

        merged = Merger().merge([str(latin_path), str(cjk_path)])
        cell_width, changed = make_cjk_double_width(merged, latin_codepoints)
        normalize_metadata(merged, family, style)
        merged.save(output_path, reorderTables=True)
        glyph_count = len(merged.getGlyphOrder())
        merged.close()

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Built {output_path.name}: {glyph_count} glyphs, "
        f"{changed} double-width glyphs, cell={cell_width}, {size_mb:.1f} MiB"
    )


def main() -> None:
    args = parse_args()
    cascadia_path = args.cascadia.resolve()
    font_dir = args.font_dir.resolve()
    output_dir = args.output.resolve()

    required = [cascadia_path, *(font_dir / style.yahei_file for style in STYLES)]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required fonts:\n" + "\n".join(map(str, missing)))

    output_dir.mkdir(parents=True, exist_ok=True)

    ps_family = safe_filename(args.family)
    for style in STYLES:
        build_style(
            cascadia_path,
            font_dir / style.yahei_file,
            output_dir / f"{ps_family}-{style.name}.ttf",
            args.family,
            style,
        )


if __name__ == "__main__":
    main()
