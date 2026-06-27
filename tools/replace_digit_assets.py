#!/usr/bin/env python3
r"""Render score/combo digit PNG assets from TrueType/OpenType fonts.

Examples:
  python tools/replace_digit_assets.py --score-font C:\Windows\Fonts\arialbd.ttf --combo-font C:\Windows\Fonts\impact.ttf
  python tools/replace_digit_assets.py --score-font myfont.otf --combo-font otherfont.otf --stretch-to-original-size
"""

from __future__ import annotations

import argparse
import configparser
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    from tools.replace_ui_assets import is_rainbow_theme, render_ui_asset, themed_color, themed_fill
except ModuleNotFoundError:
    from replace_ui_assets import is_rainbow_theme, render_ui_asset, themed_color, themed_fill


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
SCORE_DIR = ROOT / "assets" / "score" / "digit"
SCORE_UI_DIR = ROOT / "assets" / "score"
COMBO_DIR = ROOT / "assets" / "combo"
JUDGE_V3_DIR = ROOT / "assets" / "judge" / "v3"
RANK_DIR = ROOT / "assets" / "score" / "rank"
LIFE_V3_DIR = ROOT / "assets" / "life" / "v3"
LIFE_V3_DIGIT_DIR = LIFE_V3_DIR / "digit"
WINDOWS_FONT_DIR = Path("C:/Windows/Fonts")
DEFAULT_CONFIG = ROOT / "tools" / "replace_digit_assets.ini"

Color = tuple[int, int, int, int]
Fill = Color | tuple[Color, ...]


@dataclass(frozen=True)
class RenderStyle:
    font_path: Path
    fill: Fill
    stroke_fill: Fill
    stroke_width: int
    x_padding: int
    y_padding: int
    blur_fill: tuple[int, int, int, int] | None = None
    blur_radius: float = 0.0
    blur_spread: int = 0


@dataclass(frozen=True)
class AssetTarget:
    path: Path
    output_path: Path
    text: str
    style: RenderStyle
    sample_chars: str
    shape_source_path: Path | None = None
    shape_source_style: RenderStyle | None = None
    force_original_size: bool = False
    renderer: str = "text"


def parse_color(value: str) -> Color:
    raw = value.strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) == 6:
        raw += "ff"
    if len(raw) != 8:
        raise argparse.ArgumentTypeError("Color must be #RRGGBB or #RRGGBBAA")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in range(0, 8, 2))  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Color must be hexadecimal") from exc


def parse_fill(value: str) -> Fill:
    raw = value.strip()
    if raw.lower().startswith("gradient(") and raw.endswith(")"):
        raw = raw[9:-1]
    parts = [part.strip() for chunk in raw.split(">") for part in chunk.split(",")]
    colors = tuple(parse_color(part) for part in parts if part)
    if not colors:
        raise argparse.ArgumentTypeError("Fill must be a color or color,color gradient")
    if len(colors) == 1:
        return colors[0]
    return colors


def fill_to_text(fill: Fill) -> str:
    if isinstance(fill[0], int):  # type: ignore[index]
        color = fill  # type: ignore[assignment]
        return "#" + "".join(f"{value:02x}" for value in color)
    return ",".join("#" + "".join(f"{value:02x}" for value in color) for color in fill)  # type: ignore[union-attr]


def scale_fill_alpha(fill: Fill, scale: float) -> Fill:
    scale = max(0.0, min(1.0, scale))
    if isinstance(fill[0], int):  # type: ignore[index]
        color = fill  # type: ignore[assignment]
        return color[0], color[1], color[2], round(color[3] * scale)
    return tuple((*color[:3], round(color[3] * scale)) for color in fill)  # type: ignore[union-attr]


def fill_layer(size: tuple[int, int], fill: Fill, mask: Image.Image) -> Image.Image:
    if isinstance(fill[0], int):  # type: ignore[index]
        layer = Image.new("RGBA", size, fill)  # type: ignore[arg-type]
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        return layer

    colors: Sequence[Color] = fill  # type: ignore[assignment]
    height = max(1, size[1])
    gradient = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = gradient.load()
    segments = max(1, len(colors) - 1)
    for y in range(size[1]):
        pos = 0.0 if height == 1 else y / (height - 1)
        scaled = min(segments - 1e-9, pos * segments)
        index = int(scaled)
        local = scaled - index
        c0 = colors[index]
        c1 = colors[min(index + 1, len(colors) - 1)]
        color = tuple(round(c0[i] * (1 - local) + c1[i] * local) for i in range(4))
        for x in range(size[0]):
            pixels[x, y] = color
    gradient.putalpha(ImageChops.multiply(gradient.getchannel("A"), mask))
    return gradient


def default_options() -> dict[str, object]:
    return {
        "score_font": "",
        "combo_font": "",
        "judge_font": "",
        "rank_font": "",
        "life_font": "",
        "score_ui_font": "",
        "life_ui_font": "",
        "auto_ui_font": "",
        "ui_theme_color": "",
        "ui_theme_mode": "simple",
        "score_auto_theme_color": "",
        "life_theme_color": "",
        "combo_theme_color": "",
        "judge_theme_color": "",
        "ui_panel_opacity": 1.0,
        "ui_accent_opacity": 1.0,
        "score_fill": parse_fill("#ffffffff"),
        "score_stroke": parse_color("#00000000"),
        "score_n_fill": parse_fill("#b8b8cfff"),
        "score_s_fill": parse_fill("#050505ff"),
        "score_s_stroke": parse_color("#00000000"),
        "score_s_blur": parse_color("#000000bb"),
        "combo_p_fill": parse_fill("#ffffffff"),
        "combo_p_stroke": parse_color("#d965ffff"),
        "combo_b_fill": parse_fill("#96968cff"),
        "combo_b_stroke": parse_color("#00000000"),
        "combo_b_blur": parse_color("#96968ccc"),
        "combo_n_fill": parse_fill("#ffffffff"),
        "combo_n_stroke": parse_color("#d6d6dcff"),
        "combo_n_blur": parse_color("#00000000"),
        "judge_fill": parse_fill("#ffffffff"),
        "judge_perfect_fill": parse_fill("#69fff0,#f0d7ff,#fff8c9"),
        "judge_great_fill": parse_fill("#ff98ff,#f4b2ff"),
        "judge_good_fill": parse_fill("#7bd7ffff,#50b8ffff"),
        "judge_bad_fill": parse_fill("#65ffc0ff,#55e69fff"),
        "judge_miss_fill": parse_fill("#ffffffff,#d8d8d8ff"),
        "judge_auto_fill": parse_fill("#eaff78ff,#b4ff62ff"),
        "judge_stroke": parse_color("#00000000"),
        "judge_stroke_width": 0,
        "judge_blur": parse_color("#000000aa"),
        "judge_blur_radius": 6.0,
        "judge_blur_spread": 1,
        "rank_a_fill": parse_fill("#d776ffff"),
        "rank_b_fill": parse_fill("#73a8ffff"),
        "rank_c_fill": parse_fill("#48f4efff"),
        "rank_d_fill": parse_fill("#6bf2bdff"),
        "rank_s_fill": parse_fill("#ff82c2ff"),
        "rank_text_stroke": parse_color("#00000000"),
        "rank_chr_stroke": parse_color("#00000000"),
        "rank_chr_stroke_width": 0,
        "rank_text_stroke_width": 0,
        "life_digit_fill": parse_fill("#ffffffff,#cfffffff"),
        "life_digit_n_fill": parse_fill("#b8c2d8ff"),
        "life_digit_s_fill": parse_fill("#101426ff"),
        "life_digit_stroke": parse_color("#3deaff99"),
        "life_digit_s_stroke": parse_color("#05070eff"),
        "life_digit_s_blur": parse_color("#53f7ff99"),
        "life_digit_stroke_width": 2,
        "life_digit_s_stroke_width": 1,
        "life_digit_s_blur_radius": 4.0,
        "life_digit_s_blur_spread": 1,
        "score_ui_glass": parse_fill("#091126e8,#14233cdb,#18203bd6"),
        "score_ui_outline": parse_color("#8bffe2a0"),
        "score_ui_track": parse_color("#030817dc"),
        "score_ui_bar": parse_fill("#baf579ee,#58e5c8ee,#48bde8ee"),
        "score_ui_text": parse_fill("#a9ffe9ff,#70d9d0ff"),
        "life_ui_glass": parse_fill("#091126e8,#102b38db,#171d39d6"),
        "life_ui_outline": parse_color("#8bffe2a0"),
        "life_ui_track": parse_color("#030817dc"),
        "life_ui_normal": parse_fill("#b8f36aee,#55df9aee"),
        "life_ui_overflow": parse_fill("#8efff2ee,#54bde8ee"),
        "life_ui_danger": parse_fill("#ffcc6aee,#ff627fee"),
        "life_ui_text": parse_fill("#baffedff,#73dcd2ff"),
        "auto_ui_glass": parse_fill("#081226e8,#102b38dc,#171d39d8"),
        "auto_ui_outline": parse_color("#76efd5b0"),
        "auto_ui_accent": parse_fill("#b9f572ff,#52dfc4ff"),
        "auto_ui_text": parse_fill("#f7ffffff,#b9f7e8ff"),
        "score_stroke_width": 0,
        "score_s_stroke_width": 0,
        "score_s_blur_radius": 3.0,
        "score_s_blur_spread": 1,
        "combo_stroke_width": 8,
        "combo_b_stroke_width": 0,
        "combo_b_blur_radius": 16.0,
        "combo_b_blur_spread": 2,
        "combo_n_stroke_width": 6,
        "combo_n_blur_radius": 0.0,
        "combo_n_blur_spread": 0,
        "combo_scale": 1.0,
        "x_padding": 3,
        "y_padding": 1,
        "output_dir": Path.cwd(),
        "copy_assets": True,
        "stretch_to_original_size": False,
        "dot_as_shape": True,
        "dot_scale": 0.72,
        "dot_shape": "square",
        "dot_roundness": 0.35,
        "backup_dir": None,
        "dry_run": False,
    }


FILL_KEYS = {
    "score_fill",
    "score_n_fill",
    "score_s_fill",
    "combo_p_fill",
    "combo_b_fill",
    "combo_n_fill",
    "judge_fill",
    "judge_perfect_fill",
    "judge_great_fill",
    "judge_good_fill",
    "judge_bad_fill",
    "judge_miss_fill",
    "judge_auto_fill",
    "rank_a_fill",
    "rank_b_fill",
    "rank_c_fill",
    "rank_d_fill",
    "rank_s_fill",
    "life_digit_fill",
    "life_digit_n_fill",
    "life_digit_s_fill",
    "score_ui_glass",
    "score_ui_bar",
    "score_ui_text",
    "life_ui_glass",
    "life_ui_normal",
    "life_ui_overflow",
    "life_ui_danger",
    "life_ui_text",
    "auto_ui_glass",
    "auto_ui_accent",
    "auto_ui_text",
}
COLOR_KEYS = {
    "score_stroke",
    "score_s_stroke",
    "score_s_blur",
    "combo_p_stroke",
    "combo_b_stroke",
    "combo_b_blur",
    "combo_n_stroke",
    "combo_n_blur",
    "judge_stroke",
    "judge_blur",
    "rank_text_stroke",
    "rank_chr_stroke",
    "life_digit_stroke",
    "life_digit_s_stroke",
    "life_digit_s_blur",
    "score_ui_outline",
    "score_ui_track",
    "life_ui_outline",
    "life_ui_track",
    "auto_ui_outline",
}
INT_KEYS = {
    "score_stroke_width",
    "score_s_stroke_width",
    "score_s_blur_spread",
    "combo_stroke_width",
    "combo_b_stroke_width",
    "combo_b_blur_spread",
    "combo_n_stroke_width",
    "combo_n_blur_spread",
    "judge_stroke_width",
    "judge_blur_spread",
    "rank_chr_stroke_width",
    "rank_text_stroke_width",
    "life_digit_stroke_width",
    "life_digit_s_stroke_width",
    "life_digit_s_blur_spread",
    "x_padding",
    "y_padding",
}
FLOAT_KEYS = {
    "score_s_blur_radius",
    "combo_b_blur_radius",
    "combo_n_blur_radius",
    "judge_blur_radius",
    "life_digit_s_blur_radius",
    "dot_scale",
    "dot_roundness",
    "combo_scale",
    "ui_panel_opacity",
    "ui_accent_opacity",
}
BOOL_KEYS = {"copy_assets", "stretch_to_original_size", "dot_as_shape", "dry_run"}
PATH_KEYS = {"output_dir", "backup_dir"}


def convert_config_value(key: str, value: str) -> object:
    if key in FILL_KEYS:
        return parse_fill(value)
    if key in COLOR_KEYS:
        return parse_color(value)
    if key in INT_KEYS:
        return int(value)
    if key in FLOAT_KEYS:
        return float(value)
    if key in BOOL_KEYS:
        return value.strip().lower() in {"1", "yes", "true", "on"}
    if key in PATH_KEYS:
        return Path(value) if value.strip() else None
    return value


def load_config_defaults(path: Path) -> dict[str, object]:
    values = default_options()
    if not path.exists():
        return values

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    known = set(values)
    for section in parser.sections():
        for raw_key, raw_value in parser.items(section):
            key = raw_key.strip().replace("-", "_")
            if key not in known:
                continue
            values[key] = convert_config_value(key, raw_value)
    return values


def resolve_font(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.exists():
        return candidate.resolve()

    if WINDOWS_FONT_DIR.exists():
        lowered = value.lower()
        for font in WINDOWS_FONT_DIR.iterdir():
            if font.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            if font.name.lower() == lowered or font.stem.lower() == lowered:
                return font.resolve()

    raise FileNotFoundError(
        f"Font not found: {value}. Pass a .ttf/.otf/.ttc path, or a file name in C:/Windows/Fonts."
    )


def copy_asset_tree(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for source in ASSETS_DIR.rglob("*"):
        relative = source.relative_to(ASSETS_DIR)
        destination = output_root / relative
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def text_for_suffix(suffix: str) -> str:
    if suffix == ".":
        return "."
    if suffix == "plus":
        return "+"
    if suffix == "n":
        return "0"
    return suffix


def measure_text(font: ImageFont.FreeTypeFont, text: str, stroke_width: int) -> tuple[int, int]:
    bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox(
        (0, 0), text, font=font, stroke_width=stroke_width
    )
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def is_dot_text(text: str) -> bool:
    return text == "."


def dot_side_for_size(width: int, height: int, scale: float) -> int:
    return max(1, round(min(width, height) * scale))


def font_for_height(
    font_path: Path,
    target_height: int,
    stroke_width: int,
    y_padding: int,
    sample_chars: str,
    blur_radius: float = 0.0,
    blur_spread: int = 0,
) -> ImageFont.FreeTypeFont:
    vertical_effect = stroke_width + int(round(blur_radius)) + blur_spread
    usable_height = max(1, target_height - y_padding * 2 - vertical_effect * 2)
    low = 1
    high = max(usable_height * 4, 16)
    best = low

    while low <= high:
        mid = (low + high) // 2
        font = ImageFont.truetype(str(font_path), mid)
        tallest = max(measure_text(font, ch, stroke_width)[1] for ch in sample_chars)
        if tallest <= usable_height:
            best = mid
            low = mid + 1
        else:
            high = mid - 1

    return ImageFont.truetype(str(font_path), best)


def centered_on_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    source_x = max(0, -x)
    source_y = max(0, -y)
    paste_x = max(0, x)
    paste_y = max(0, y)
    width = min(image.width - source_x, size[0] - paste_x)
    height = min(image.height - source_y, size[1] - paste_y)
    if width > 0 and height > 0:
        output.alpha_composite(
            image.crop((source_x, source_y, source_x + width, source_y + height)),
            (paste_x, paste_y),
        )
    return output


def render_dot_asset(path: Path, style: RenderStyle, args: argparse.Namespace) -> Image.Image:
    with Image.open(path) as original:
        target_width = original.width
        target_height = original.height

    side = dot_side_for_size(target_width, target_height, args.dot_scale)
    if style.blur_fill is not None:
        effect_margin = int(round(style.blur_radius)) + style.blur_spread + style.x_padding
    else:
        effect_margin = style.x_padding
    canvas = Image.new(
        "RGBA",
        (side + effect_margin * 2, side + effect_margin * 2),
        (0, 0, 0, 0),
    )
    fill_mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(fill_mask)
    box = (effect_margin, effect_margin, effect_margin + side - 1, effect_margin + side - 1)
    if args.dot_shape == "square":
        draw.rectangle(box, fill=255)
    else:
        draw.rounded_rectangle(box, radius=max(1, round(side * args.dot_roundness)), fill=255)

    if style.stroke_width > 0:
        stroke_mask = fill_mask.filter(ImageFilter.MaxFilter(style.stroke_width * 2 + 1))
    else:
        stroke_mask = fill_mask

    if style.blur_fill is not None and (style.blur_radius > 0 or style.blur_spread > 0):
        blur_mask = stroke_mask
        if style.blur_spread > 0:
            blur_mask = blur_mask.filter(ImageFilter.MaxFilter(style.blur_spread * 2 + 1))
        if style.blur_radius > 0:
            blur_mask = blur_mask.filter(ImageFilter.GaussianBlur(style.blur_radius))
        blur_layer = Image.new("RGBA", canvas.size, style.blur_fill)
        blur_layer.putalpha(ImageChops.multiply(blur_layer.getchannel("A"), blur_mask))
        canvas.alpha_composite(blur_layer)

    if style.stroke_width > 0:
        canvas.alpha_composite(fill_layer(canvas.size, style.stroke_fill, stroke_mask))

    canvas.alpha_composite(fill_layer(canvas.size, style.fill, fill_mask))

    if args.stretch_to_original_size:
        return centered_on_canvas(canvas, (target_width, target_height))

    output = Image.new(
        "RGBA",
        (canvas.width + style.x_padding * 2, target_height),
        (0, 0, 0, 0),
    )
    output.alpha_composite(canvas, (style.x_padding, (target_height - canvas.height) // 2))
    return output


def render_from_shape(
    shape: Image.Image,
    target_path: Path,
    style: RenderStyle,
    stretch_to_original_size: bool,
) -> Image.Image:
    with Image.open(target_path) as original:
        target_width = original.width
        target_height = original.height

    effect_margin = max(style.stroke_width, int(round(style.blur_radius)) + style.blur_spread) + 4
    mask = shape.getchannel("A")
    canvas_size = (
        mask.width + effect_margin * 2 + style.x_padding * 4,
        mask.height + effect_margin * 2 + style.y_padding * 4,
    )
    base_mask = Image.new("L", canvas_size, 0)
    base_mask.paste(mask, (effect_margin + style.x_padding * 2, effect_margin + style.y_padding * 2))

    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if style.blur_fill is not None and (style.blur_radius > 0 or style.blur_spread > 0):
        blur_mask = base_mask
        if style.blur_spread > 0:
            blur_mask = blur_mask.filter(ImageFilter.MaxFilter(style.blur_spread * 2 + 1))
        if style.blur_radius > 0:
            blur_mask = blur_mask.filter(ImageFilter.GaussianBlur(style.blur_radius))
        blur_layer = Image.new("RGBA", canvas_size, style.blur_fill)
        blur_layer.putalpha(ImageChops.multiply(blur_layer.getchannel("A"), blur_mask))
        canvas.alpha_composite(blur_layer)

    if style.stroke_width > 0:
        stroke_mask = base_mask.filter(ImageFilter.MaxFilter(style.stroke_width * 2 + 1))
        canvas.alpha_composite(fill_layer(canvas_size, style.stroke_fill, stroke_mask))

    canvas.alpha_composite(fill_layer(canvas_size, style.fill, base_mask))

    alpha_bbox = canvas.getbbox()
    if alpha_bbox is None:
        if stretch_to_original_size:
            return Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        return Image.new("RGBA", (1 + style.x_padding * 2, target_height), (0, 0, 0, 0))

    cropped = canvas.crop(alpha_bbox)
    if stretch_to_original_size:
        return centered_on_canvas(cropped, (target_width, target_height))

    output = Image.new(
        "RGBA",
        (cropped.width + style.x_padding * 2, target_height),
        (0, 0, 0, 0),
    )
    output.alpha_composite(cropped, (style.x_padding, (target_height - cropped.height) // 2))
    return output


def render_text_asset(
    path: Path,
    text: str,
    style: RenderStyle,
    sample_chars: str,
    stretch_to_original_size: bool = False,
) -> Image.Image:
    with Image.open(path) as original:
        target_width = original.width
        target_height = original.height

    font = font_for_height(
        style.font_path,
        target_height,
        style.stroke_width,
        style.y_padding,
        sample_chars,
        style.blur_radius,
        style.blur_spread,
    )

    draw_probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    effect_margin = (
        max(style.stroke_width, int(round(style.blur_radius)) + style.blur_spread) + 4
    )
    bbox = draw_probe.textbbox((0, 0), text, font=font, stroke_width=style.stroke_width)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    canvas = Image.new(
        "RGBA",
        (
            max(1, text_width + effect_margin * 2 + style.x_padding * 4),
            max(1, text_height + effect_margin * 2 + style.y_padding * 4),
        ),
        (0, 0, 0, 0),
    )
    origin = (
        effect_margin + style.x_padding * 2 - bbox[0],
        effect_margin + style.y_padding * 2 - bbox[1],
    )

    fill_mask = Image.new("L", canvas.size, 0)
    fill_mask_draw = ImageDraw.Draw(fill_mask)
    fill_mask_draw.text(origin, text, font=font, fill=255)

    stroke_mask = Image.new("L", canvas.size, 0)
    stroke_mask_draw = ImageDraw.Draw(stroke_mask)
    stroke_mask_draw.text(
        origin,
        text,
        font=font,
        fill=255,
        stroke_width=style.stroke_width,
        stroke_fill=255,
    )

    if style.blur_fill is not None and (style.blur_radius > 0 or style.blur_spread > 0):
        blur_mask = stroke_mask
        if style.blur_spread > 0:
            kernel_size = style.blur_spread * 2 + 1
            blur_mask = blur_mask.filter(ImageFilter.MaxFilter(kernel_size))
        if style.blur_radius > 0:
            blur_mask = blur_mask.filter(ImageFilter.GaussianBlur(style.blur_radius))
        blur_layer = Image.new("RGBA", canvas.size, style.blur_fill)
        blur_layer.putalpha(ImageChops.multiply(blur_layer.getchannel("A"), blur_mask))
        canvas.alpha_composite(blur_layer)

    if style.stroke_width > 0:
        canvas.alpha_composite(fill_layer(canvas.size, style.stroke_fill, stroke_mask))

    canvas.alpha_composite(fill_layer(canvas.size, style.fill, fill_mask))

    alpha_bbox = canvas.getbbox()
    if alpha_bbox is None:
        if stretch_to_original_size:
            return Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        return Image.new("RGBA", (1 + style.x_padding * 2, target_height), (0, 0, 0, 0))

    cropped = canvas.crop(alpha_bbox)
    if cropped.height > target_height - style.y_padding * 2:
        ratio = (target_height - style.y_padding * 2) / cropped.height
        cropped = cropped.resize(
            (max(1, round(cropped.width * ratio)), max(1, round(cropped.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    output = Image.new(
        "RGBA",
        (cropped.width + style.x_padding * 2, target_height),
        (0, 0, 0, 0),
    )
    output.alpha_composite(cropped, (style.x_padding, (target_height - cropped.height) // 2))
    if stretch_to_original_size and output.size != (target_width, target_height):
        output = output.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return output


def scale_asset_content(image: Image.Image, scale: float) -> Image.Image:
    if abs(scale - 1.0) < 1e-6:
        return image
    scale = max(0.1, min(2.0, scale))
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    return centered_on_canvas(scaled, image.size)


def finish_render(target: AssetTarget, image: Image.Image, args: argparse.Namespace) -> Image.Image:
    if target.path.parent == COMBO_DIR:
        return scale_asset_content(image, args.combo_scale)
    return image


def render_asset(target: AssetTarget, args: argparse.Namespace) -> Image.Image:
    if target.renderer != "text":
        return render_ui_asset(target.path, target.renderer, args, ROOT)

    stretch_to_original_size = args.stretch_to_original_size or target.force_original_size
    if args.dot_as_shape and is_dot_text(target.text):
        return finish_render(target, render_dot_asset(target.path, target.style, args), args)

    if target.shape_source_path is not None and target.shape_source_style is not None:
        shape = render_text_asset(
            target.shape_source_path,
            target.text,
            target.shape_source_style,
            target.sample_chars,
            stretch_to_original_size,
        )
        image = render_from_shape(shape, target.path, target.style, stretch_to_original_size)
        return finish_render(target, image, args)

    image = render_text_asset(
        target.path,
        target.text,
        target.style,
        target.sample_chars,
        stretch_to_original_size,
    )
    return finish_render(target, image, args)


def existing_targets(
    directory: Path,
    output_directory: Path,
    names: Iterable[str],
    style: RenderStyle,
    sample_chars: str,
    strip_prefix: str = "",
    shape_source_directory: Path | None = None,
    shape_source_prefix: str = "",
    shape_source_style: RenderStyle | None = None,
    force_original_size: bool = False,
) -> list[AssetTarget]:
    targets: list[AssetTarget] = []
    for name in names:
        path = directory / f"{name}.png"
        if path.exists():
            suffix = name.removeprefix(strip_prefix) if strip_prefix else name
            shape_source_path = None
            if shape_source_directory is not None:
                shape_source_path = shape_source_directory / f"{shape_source_prefix}{suffix}.png"
                if not shape_source_path.exists():
                    shape_source_path = None
            targets.append(
                AssetTarget(
                    path,
                    output_directory / path.name,
                    text_for_suffix(suffix),
                    style,
                    sample_chars,
                    shape_source_path,
                    shape_source_style if shape_source_path is not None else None,
                    force_original_size,
                )
            )
    return targets


def build_targets(args: argparse.Namespace) -> list[AssetTarget]:
    score_font = resolve_font(args.score_font)
    combo_font = resolve_font(args.combo_font)
    judge_font = resolve_font(args.judge_font or args.combo_font)
    rank_font = resolve_font(args.rank_font or args.combo_font)
    life_font = resolve_font(args.life_font or args.score_font)
    output_root = args.output_dir
    if not output_root.is_absolute():
        output_root = Path.cwd() / output_root
    score_ui_output_dir = output_root / "score"
    score_output_dir = output_root / "score" / "digit"
    combo_output_dir = output_root / "combo"
    judge_v3_output_dir = output_root / "judge" / "v3"
    rank_output_dir = output_root / "score" / "rank"
    life_v3_output_dir = output_root / "life" / "v3"
    life_digit_output_dir = life_v3_output_dir / "digit"

    score_style = RenderStyle(
        score_font,
        args.score_fill,
        args.score_stroke,
        args.score_stroke_width,
        args.x_padding,
        args.y_padding,
    )
    score_n_style = RenderStyle(
        score_font,
        args.score_n_fill,
        args.score_stroke,
        args.score_stroke_width,
        args.x_padding,
        args.y_padding,
    )
    score_small_style = RenderStyle(
        score_font,
        args.score_s_fill,
        args.score_s_stroke,
        args.score_s_stroke_width,
        args.x_padding,
        args.y_padding,
        args.score_s_blur,
        args.score_s_blur_radius,
        args.score_s_blur_spread,
    )
    combo_p_fill = themed_fill(args.combo_p_fill, args, "accent", "combo")
    combo_p_stroke = themed_fill(args.combo_p_stroke, args, "stroke", "combo")
    combo_b_fill = themed_fill(args.combo_b_fill, args, "panel", "combo")
    combo_b_stroke = themed_color(args.combo_b_stroke, args, "panel", "combo")
    combo_b_blur = themed_color(args.combo_b_blur, args, "panel", "combo")
    combo_n_fill = themed_fill(args.combo_n_fill, args, "text", "combo")
    combo_n_stroke = themed_fill(args.combo_n_stroke, args, "stroke", "combo")
    combo_n_blur = themed_color(args.combo_n_blur, args, "panel", "combo")
    combo_is_rainbow = is_rainbow_theme(args, "combo")
    if combo_is_rainbow:
        combo_b_fill = scale_fill_alpha(combo_b_fill, 0.3)
        combo_b_stroke = scale_fill_alpha(combo_b_stroke, 0.3)  # type: ignore[assignment]
        combo_b_blur = scale_fill_alpha(combo_b_blur, 0.3)  # type: ignore[assignment]

    combo_front_stroke_width = args.combo_stroke_width
    if combo_is_rainbow:
        combo_front_stroke_width = max(2, round(combo_front_stroke_width * 0.5))

    combo_p_style = RenderStyle(
        combo_font,
        combo_p_fill,
        combo_p_stroke,
        combo_front_stroke_width,
        args.x_padding,
        args.y_padding,
    )
    combo_b_style = RenderStyle(
        combo_font,
        combo_b_fill,
        combo_b_stroke,
        args.combo_b_stroke_width,
        args.x_padding,
        args.y_padding,
        combo_b_blur,
        args.combo_b_blur_radius,
        args.combo_b_blur_spread,
    )
    combo_n_style = RenderStyle(
        combo_font,
        combo_n_fill,
        combo_n_stroke,
        args.combo_n_stroke_width,
        args.x_padding,
        args.y_padding,
        combo_n_blur if combo_n_blur[3] > 0 else None,
        args.combo_n_blur_radius,
        args.combo_n_blur_spread,
    )
    # Judgment fill/stroke colors carry gameplay meaning. Keep their configured
    # colors and apply the shared theme only to the surrounding glow.
    judge_stroke = args.judge_stroke
    judge_blur = themed_color(args.judge_blur, args, "accent", "judge")

    def make_judge_style(fill: Fill) -> RenderStyle:
        return RenderStyle(
            judge_font,
            fill,
            judge_stroke,
            args.judge_stroke_width,
            args.x_padding,
            args.y_padding,
            judge_blur,
            args.judge_blur_radius,
            args.judge_blur_spread,
        )

    judge_base_style = make_judge_style(args.judge_fill)
    life_digit_style = RenderStyle(
        life_font,
        args.life_digit_fill,
        args.life_digit_stroke,
        args.life_digit_stroke_width,
        args.x_padding,
        args.y_padding,
    )
    life_digit_n_style = RenderStyle(
        life_font,
        args.life_digit_n_fill,
        args.life_digit_stroke,
        args.life_digit_stroke_width,
        args.x_padding,
        args.y_padding,
    )
    life_digit_small_style = RenderStyle(
        life_font,
        args.life_digit_s_fill,
        args.life_digit_s_stroke,
        args.life_digit_s_stroke_width,
        args.x_padding,
        args.y_padding,
        args.life_digit_s_blur,
        args.life_digit_s_blur_radius,
        args.life_digit_s_blur_spread,
    )

    score_ui_targets: list[AssetTarget] = []
    for file_name in ("bg.png", "bar.png", "bars.png", "fg.png"):
        path = SCORE_UI_DIR / file_name
        if path.exists():
            score_ui_targets.append(
                AssetTarget(
                    path,
                    score_ui_output_dir / file_name,
                    file_name.removesuffix(".png"),
                    score_style,
                    "SCORE",
                    force_original_size=True,
                    renderer="score_ui",
                )
            )

    digit_suffixes = [str(i) for i in range(10)] + ["%", ".", "-", "+", "plus"]
    score_targets = existing_targets(
        SCORE_DIR, score_output_dir, digit_suffixes, score_style, "0123456789%.-+"
    )
    score_targets += existing_targets(
        SCORE_DIR, score_output_dir, ["n"], score_n_style, "0123456789%.-+"
    )
    score_targets += existing_targets(
        SCORE_DIR,
        score_output_dir,
        [f"s{i}" for i in range(10)] + ["s%", "s.", "s-", "s+", "splus", "sn"],
        score_small_style,
        "0123456789%.-+",
        strip_prefix="s",
        shape_source_directory=SCORE_DIR,
        shape_source_style=score_style,
    )

    combo_targets: list[AssetTarget] = []
    for prefix, style in (("p", combo_p_style), ("b", combo_b_style)):
        names = [f"{prefix}{i}" for i in range(10)] + [f"{prefix}%", f"{prefix}.", f"{prefix}-"]
        combo_targets += existing_targets(
            COMBO_DIR,
            combo_output_dir,
            names,
            style,
            "0123456789%.-",
            strip_prefix=prefix,
            shape_source_directory=COMBO_DIR if prefix == "b" else None,
            shape_source_prefix="p" if prefix == "b" else "",
            shape_source_style=combo_p_style if prefix == "b" else None,
        )

    n_names = [f"n{i}" for i in range(10)] + ["n%", "n.", "n-"]
    combo_targets += existing_targets(
        COMBO_DIR,
        combo_output_dir,
        n_names,
        combo_n_style,
        "0123456789%.-COMBO",
        strip_prefix="n",
        force_original_size=True,
    )
    n_shadow_names = [f"n_{i}" for i in range(10)] + ["n_%", "n_.", "n_-"]
    combo_targets += existing_targets(
        COMBO_DIR,
        combo_output_dir,
        n_shadow_names,
        combo_b_style,
        "0123456789%.-COMBO",
        strip_prefix="n_",
        shape_source_directory=COMBO_DIR,
        shape_source_prefix="n",
        shape_source_style=combo_n_style,
        force_original_size=True,
    )
    nt_path = COMBO_DIR / "nt.png"
    if nt_path.exists():
        combo_targets.append(
            AssetTarget(
                nt_path,
                combo_output_dir / "nt.png",
                "COMBO",
                combo_n_style,
                "COMBO0123456789%.-",
                force_original_size=True,
            )
        )
    n_c_path = COMBO_DIR / "n_c.png"
    if n_c_path.exists():
        combo_targets.append(
            AssetTarget(
                n_c_path,
                combo_output_dir / "n_c.png",
                "COMBO",
                combo_b_style,
                "COMBO0123456789%.-",
                nt_path if nt_path.exists() else None,
                combo_n_style if nt_path.exists() else None,
                force_original_size=True,
            )
        )

    combo_text_targets: list[AssetTarget] = []
    pt_path = COMBO_DIR / "pt.png"
    if pt_path.exists():
        combo_text_targets.append(
            AssetTarget(
                pt_path,
                combo_output_dir / "pt.png",
                "COMBO",
                combo_p_style,
                "COMBO0123456789%.-",
                force_original_size=True,
            )
        )
    pe_path = COMBO_DIR / "pe.png"
    if pe_path.exists():
        combo_text_targets.append(
            AssetTarget(
                pe_path,
                combo_output_dir / "pe.png",
                "COMBO",
                combo_b_style,
                "COMBO0123456789%.-",
                pt_path if pt_path.exists() else None,
                combo_p_style if pt_path.exists() else None,
                force_original_size=True,
            )
        )

    judge_styles = {
        "PERFECT": make_judge_style(args.judge_perfect_fill),
        "GREAT": make_judge_style(args.judge_great_fill),
        "GOOD": make_judge_style(args.judge_good_fill),
        "BAD": make_judge_style(args.judge_bad_fill),
        "MISS": make_judge_style(args.judge_miss_fill),
        "AUTO": make_judge_style(args.judge_auto_fill),
    }
    judge_names = {
        "1.png": "PERFECT",
        "2.png": "GREAT",
        "3.png": "GOOD",
        "4.png": "BAD",
        "5.png": "MISS",
        "6.png": "AUTO",
    }
    judge_targets: list[AssetTarget] = []
    for file_name, text in judge_names.items():
        path = JUDGE_V3_DIR / file_name
        if path.exists():
            judge_targets.append(
                AssetTarget(
                    path,
                    judge_v3_output_dir / file_name,
                    text,
                    judge_styles.get(text, judge_base_style),
                    "PERFECTGREATGOODBADMISSAUTO",
                    force_original_size=True,
                )
            )

    rank_fills = {
        "a": args.rank_a_fill,
        "b": args.rank_b_fill,
        "c": args.rank_c_fill,
        "d": args.rank_d_fill,
        "s": args.rank_s_fill,
    }
    rank_targets: list[AssetTarget] = []
    for rank, fill in rank_fills.items():
        chr_path = RANK_DIR / "chr" / f"{rank}.png"
        if chr_path.exists():
            rank_targets.append(
                AssetTarget(
                    chr_path,
                    rank_output_dir / "chr" / f"{rank}.png",
                    rank.upper(),
                    RenderStyle(
                        rank_font,
                        fill,
                        args.rank_chr_stroke,
                        args.rank_chr_stroke_width,
                        args.x_padding,
                        args.y_padding,
                    ),
                    "ABCDS",
                    force_original_size=True,
                )
            )
        for lang in ("en", "jp"):
            txt_path = RANK_DIR / "txt" / lang / f"{rank}.png"
            if txt_path.exists():
                rank_targets.append(
                    AssetTarget(
                        txt_path,
                        rank_output_dir / "txt" / lang / f"{rank}.png",
                        "SCORE RANK" if lang == "en" else "SCORERANK",
                        RenderStyle(
                            rank_font,
                            fill,
                            args.rank_text_stroke,
                            args.rank_text_stroke_width,
                            args.x_padding,
                            args.y_padding,
                        ),
                        "SCORERANK",
                        force_original_size=True,
                    )
                )

    life_ui_targets: list[AssetTarget] = []
    for file_name in ("bg.png", "normal.png", "overflow.png", "danger.png", "mask.png"):
        path = LIFE_V3_DIR / file_name
        if path.exists():
            life_ui_targets.append(
                AssetTarget(
                    path,
                    life_v3_output_dir / file_name,
                    file_name.removesuffix(".png"),
                    life_digit_style,
                    "LIFEDANGER+",
                    force_original_size=True,
                    renderer="life_ui",
                )
            )

    life_digit_targets = existing_targets(
        LIFE_V3_DIGIT_DIR,
        life_digit_output_dir,
        [str(i) for i in range(10)],
        life_digit_style,
        "0123456789",
        force_original_size=True,
    )
    life_digit_targets += existing_targets(
        LIFE_V3_DIGIT_DIR,
        life_digit_output_dir,
        ["n"],
        life_digit_n_style,
        "0123456789",
        force_original_size=True,
    )
    life_digit_targets += existing_targets(
        LIFE_V3_DIGIT_DIR,
        life_digit_output_dir,
        [f"s{i}" for i in range(10)] + ["sn"],
        life_digit_small_style,
        "0123456789",
        strip_prefix="s",
        shape_source_directory=LIFE_V3_DIGIT_DIR,
        shape_source_style=life_digit_style,
        force_original_size=True,
    )

    auto_ui_targets: list[AssetTarget] = []
    for file_name in ("autolive.png", "autolive-en.png"):
        path = ASSETS_DIR / file_name
        if path.exists():
            auto_ui_targets.append(
                AssetTarget(
                    path,
                    output_root / file_name,
                    "AUTO LIVE" if file_name == "autolive.png" else "AUTO-PLAY",
                    combo_p_style,
                    "AUTOLIVE-PLAY",
                    force_original_size=True,
                    renderer="auto_ui",
                )
            )

    return (
        score_ui_targets
        + score_targets
        + combo_targets
        + combo_text_targets
        + judge_targets
        + rank_targets
        + life_ui_targets
        + life_digit_targets
        + auto_ui_targets
    )


def main(argv: list[str] | None = None) -> int:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    pre_args, _ = pre_parser.parse_known_args(argv)
    defaults = load_config_defaults(pre_args.config)

    parser = argparse.ArgumentParser(
        description="Replace score/combo digit PNG assets with glyphs rendered from fonts."
    )
    parser.add_argument("--config", type=Path, default=pre_args.config, help="INI config file")
    parser.add_argument("--score-font", default=defaults["score_font"], help="Font path/name for assets/score/digit")
    parser.add_argument("--combo-font", default=defaults["combo_font"], help="Font path/name for assets/combo p*/b*")
    parser.add_argument("--judge-font", default=defaults["judge_font"], help="Font path/name for assets/judge/v3")
    parser.add_argument("--rank-font", default=defaults["rank_font"], help="Font path/name for assets/score/rank")
    parser.add_argument("--life-font", default=defaults["life_font"], help="Font path/name for assets/life/v3/digit")
    parser.add_argument("--score-ui-font", default=defaults["score_ui_font"], help="Font for SCORE and score rank markers")
    parser.add_argument("--life-ui-font", default=defaults["life_ui_font"], help="Font for the LIFE label")
    parser.add_argument("--auto-ui-font", default=defaults["auto_ui_font"], help="Font for AUTO LIVE/AUTO-PLAY")
    parser.add_argument(
        "--ui-theme-color",
        default=defaults["ui_theme_color"],
        help="Shared UI theme color: green, blue, purple, cyan, pink, rainbow, or #RRGGBB",
    )
    parser.add_argument("--ui-theme-mode", choices=("simple", "detailed"), default=defaults["ui_theme_mode"])
    parser.add_argument("--score-auto-theme-color", default=defaults["score_auto_theme_color"])
    parser.add_argument("--life-theme-color", default=defaults["life_theme_color"])
    parser.add_argument("--combo-theme-color", default=defaults["combo_theme_color"])
    parser.add_argument("--judge-theme-color", default=defaults["judge_theme_color"])
    parser.add_argument("--ui-panel-opacity", type=float, default=defaults["ui_panel_opacity"])
    parser.add_argument("--ui-accent-opacity", type=float, default=defaults["ui_accent_opacity"])
    parser.add_argument("--score-fill", type=parse_fill, default=defaults["score_fill"])
    parser.add_argument("--score-stroke", type=parse_color, default=defaults["score_stroke"])
    parser.add_argument("--score-n-fill", type=parse_fill, default=defaults["score_n_fill"])
    parser.add_argument("--score-s-fill", type=parse_fill, default=defaults["score_s_fill"])
    parser.add_argument("--score-s-stroke", type=parse_color, default=defaults["score_s_stroke"])
    parser.add_argument("--score-s-blur", type=parse_color, default=defaults["score_s_blur"])
    parser.add_argument("--combo-p-fill", type=parse_fill, default=defaults["combo_p_fill"])
    parser.add_argument("--combo-p-stroke", type=parse_color, default=defaults["combo_p_stroke"])
    parser.add_argument("--combo-b-fill", type=parse_fill, default=defaults["combo_b_fill"])
    parser.add_argument("--combo-b-stroke", type=parse_color, default=defaults["combo_b_stroke"])
    parser.add_argument("--combo-b-blur", type=parse_color, default=defaults["combo_b_blur"])
    parser.add_argument("--combo-n-fill", type=parse_fill, default=defaults["combo_n_fill"])
    parser.add_argument("--combo-n-stroke", type=parse_color, default=defaults["combo_n_stroke"])
    parser.add_argument("--combo-n-blur", type=parse_color, default=defaults["combo_n_blur"])
    parser.add_argument("--judge-fill", type=parse_fill, default=defaults["judge_fill"])
    parser.add_argument("--judge-perfect-fill", type=parse_fill, default=defaults["judge_perfect_fill"])
    parser.add_argument("--judge-great-fill", type=parse_fill, default=defaults["judge_great_fill"])
    parser.add_argument("--judge-good-fill", type=parse_fill, default=defaults["judge_good_fill"])
    parser.add_argument("--judge-bad-fill", type=parse_fill, default=defaults["judge_bad_fill"])
    parser.add_argument("--judge-miss-fill", type=parse_fill, default=defaults["judge_miss_fill"])
    parser.add_argument("--judge-auto-fill", type=parse_fill, default=defaults["judge_auto_fill"])
    parser.add_argument("--judge-stroke", type=parse_color, default=defaults["judge_stroke"])
    parser.add_argument("--judge-blur", type=parse_color, default=defaults["judge_blur"])
    parser.add_argument("--rank-a-fill", type=parse_fill, default=defaults["rank_a_fill"])
    parser.add_argument("--rank-b-fill", type=parse_fill, default=defaults["rank_b_fill"])
    parser.add_argument("--rank-c-fill", type=parse_fill, default=defaults["rank_c_fill"])
    parser.add_argument("--rank-d-fill", type=parse_fill, default=defaults["rank_d_fill"])
    parser.add_argument("--rank-s-fill", type=parse_fill, default=defaults["rank_s_fill"])
    parser.add_argument("--rank-text-stroke", type=parse_color, default=defaults["rank_text_stroke"])
    parser.add_argument("--rank-chr-stroke", type=parse_color, default=defaults["rank_chr_stroke"])
    parser.add_argument("--life-digit-fill", type=parse_fill, default=defaults["life_digit_fill"])
    parser.add_argument("--life-digit-n-fill", type=parse_fill, default=defaults["life_digit_n_fill"])
    parser.add_argument("--life-digit-s-fill", type=parse_fill, default=defaults["life_digit_s_fill"])
    parser.add_argument("--life-digit-stroke", type=parse_color, default=defaults["life_digit_stroke"])
    parser.add_argument("--life-digit-s-stroke", type=parse_color, default=defaults["life_digit_s_stroke"])
    parser.add_argument("--life-digit-s-blur", type=parse_color, default=defaults["life_digit_s_blur"])
    parser.add_argument("--score-ui-glass", type=parse_fill, default=defaults["score_ui_glass"])
    parser.add_argument("--score-ui-outline", type=parse_color, default=defaults["score_ui_outline"])
    parser.add_argument("--score-ui-track", type=parse_color, default=defaults["score_ui_track"])
    parser.add_argument("--score-ui-bar", type=parse_fill, default=defaults["score_ui_bar"])
    parser.add_argument("--score-ui-text", type=parse_fill, default=defaults["score_ui_text"])
    parser.add_argument("--life-ui-glass", type=parse_fill, default=defaults["life_ui_glass"])
    parser.add_argument("--life-ui-outline", type=parse_color, default=defaults["life_ui_outline"])
    parser.add_argument("--life-ui-track", type=parse_color, default=defaults["life_ui_track"])
    parser.add_argument("--life-ui-normal", type=parse_fill, default=defaults["life_ui_normal"])
    parser.add_argument("--life-ui-overflow", type=parse_fill, default=defaults["life_ui_overflow"])
    parser.add_argument("--life-ui-danger", type=parse_fill, default=defaults["life_ui_danger"])
    parser.add_argument("--life-ui-text", type=parse_fill, default=defaults["life_ui_text"])
    parser.add_argument("--auto-ui-glass", type=parse_fill, default=defaults["auto_ui_glass"])
    parser.add_argument("--auto-ui-outline", type=parse_color, default=defaults["auto_ui_outline"])
    parser.add_argument("--auto-ui-accent", type=parse_fill, default=defaults["auto_ui_accent"])
    parser.add_argument("--auto-ui-text", type=parse_fill, default=defaults["auto_ui_text"])
    parser.add_argument("--score-stroke-width", type=int, default=defaults["score_stroke_width"])
    parser.add_argument("--score-s-stroke-width", type=int, default=defaults["score_s_stroke_width"])
    parser.add_argument("--score-s-blur-radius", type=float, default=defaults["score_s_blur_radius"])
    parser.add_argument("--score-s-blur-spread", type=int, default=defaults["score_s_blur_spread"])
    parser.add_argument("--combo-stroke-width", type=int, default=defaults["combo_stroke_width"])
    parser.add_argument("--combo-b-stroke-width", type=int, default=defaults["combo_b_stroke_width"])
    parser.add_argument("--combo-b-blur-radius", type=float, default=defaults["combo_b_blur_radius"])
    parser.add_argument("--combo-b-blur-spread", type=int, default=defaults["combo_b_blur_spread"])
    parser.add_argument("--combo-n-stroke-width", type=int, default=defaults["combo_n_stroke_width"])
    parser.add_argument("--combo-n-blur-radius", type=float, default=defaults["combo_n_blur_radius"])
    parser.add_argument("--combo-n-blur-spread", type=int, default=defaults["combo_n_blur_spread"])
    parser.add_argument("--combo-scale", type=float, default=defaults["combo_scale"])
    parser.add_argument("--judge-stroke-width", type=int, default=defaults["judge_stroke_width"])
    parser.add_argument("--judge-blur-radius", type=float, default=defaults["judge_blur_radius"])
    parser.add_argument("--judge-blur-spread", type=int, default=defaults["judge_blur_spread"])
    parser.add_argument("--rank-chr-stroke-width", type=int, default=defaults["rank_chr_stroke_width"])
    parser.add_argument("--rank-text-stroke-width", type=int, default=defaults["rank_text_stroke_width"])
    parser.add_argument("--life-digit-stroke-width", type=int, default=defaults["life_digit_stroke_width"])
    parser.add_argument("--life-digit-s-stroke-width", type=int, default=defaults["life_digit_s_stroke_width"])
    parser.add_argument("--life-digit-s-blur-radius", type=float, default=defaults["life_digit_s_blur_radius"])
    parser.add_argument("--life-digit-s-blur-spread", type=int, default=defaults["life_digit_s_blur_spread"])
    parser.add_argument("--x-padding", type=int, default=defaults["x_padding"], help="Transparent pixels kept at left/right")
    parser.add_argument("--y-padding", type=int, default=defaults["y_padding"], help="Pixels reserved at top/bottom when sizing")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=defaults["output_dir"],
        help="Root output directory. Generated PNGs are written to output-dir/score and output-dir/combo",
    )
    parser.add_argument(
        "--copy-assets",
        action=argparse.BooleanOptionalAction,
        default=defaults["copy_assets"],
        help="Copy every file from assets into output-dir before writing generated assets",
    )
    parser.add_argument(
        "--stretch-to-original-size",
        action=argparse.BooleanOptionalAction,
        default=defaults["stretch_to_original_size"],
        help="Resize each generated PNG to the same width and height as its source PNG",
    )
    parser.add_argument(
        "--dot-as-shape",
        action=argparse.BooleanOptionalAction,
        default=defaults["dot_as_shape"],
        help="Render '.' assets as a square-ish shape instead of using the font period",
    )
    parser.add_argument(
        "--dot-scale",
        type=float,
        default=defaults["dot_scale"],
        help="Dot side length as a fraction of min(source width, source height)",
    )
    parser.add_argument(
        "--dot-shape",
        choices=("round", "square"),
        default=defaults["dot_shape"],
        help="Shape used for generated '.' assets",
    )
    parser.add_argument(
        "--dot-roundness",
        type=float,
        default=defaults["dot_roundness"],
        help="Corner radius fraction for --dot-shape round",
    )
    parser.add_argument("--backup-dir", type=Path, default=defaults["backup_dir"], help="Copy source PNGs here before generating")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=defaults["dry_run"], help="Print targets without writing PNGs")
    args = parser.parse_args(argv)

    if not args.score_font or not args.combo_font:
        parser.error("score_font and combo_font must be set in the INI file or CLI arguments")

    targets = build_targets(args)
    if not targets:
        print("No target PNGs found.")
        return 1

    if args.backup_dir and not args.dry_run:
        backup_dir = args.backup_dir
        if not backup_dir.is_absolute():
            backup_dir = ROOT / backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        for target in targets:
            relative = target.path.relative_to(ROOT)
            backup_path = backup_dir / relative
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target.path, backup_path)

    if args.copy_assets and not args.dry_run:
        output_root = args.output_dir
        if not output_root.is_absolute():
            output_root = Path.cwd() / output_root
        copy_asset_tree(output_root)

    for target in targets:
        image = render_asset(target, args)
        source_relative = target.path.relative_to(ROOT)
        try:
            output_relative = target.output_path.relative_to(Path.cwd())
        except ValueError:
            output_relative = target.output_path
        if args.dry_run:
            print(
                f"{source_relative} -> {output_relative}: "
                f"'{target.text}' -> {image.width}x{image.height}"
            )
            continue
        target.output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(target.output_path, format="PNG")
        print(f"wrote {output_relative}: '{target.text}' -> {image.width}x{image.height}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
