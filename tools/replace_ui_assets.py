#!/usr/bin/env python3
"""Render non-text score, life, and auto-live UI assets."""

from __future__ import annotations

import argparse
import colorsys
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


Color = tuple[int, int, int, int]
Fill = Color | tuple[Color, ...]

NAMED_THEME_COLORS = {
    "green": (85, 223, 154),
    "blue": (76, 142, 255),
    "purple": (166, 105, 255),
    "cyan": (72, 211, 232),
    "pink": (242, 105, 190),
}
BASE_THEME_RGB = NAMED_THEME_COLORS["green"]
RAINBOW_REFERENCE_RGB = (126, 132, 255)
RAINBOW_COLORS: tuple[tuple[int, int, int], ...] = (
    (255, 216, 245),
    (255, 237, 251),
    (249, 247, 255),
    (218, 231, 255),
    (178, 251, 243),
)


THEME_CATEGORY_KEYS = {
    "score_auto": "score_auto_theme_color",
    "life": "life_theme_color",
    "combo": "combo_theme_color",
    "judge": "judge_theme_color",
}


def _theme_rgb(
    args: argparse.Namespace,
    category: str | None = None,
) -> tuple[int, int, int] | str | None:
    value = getattr(args, "ui_theme_color", "")
    if str(getattr(args, "ui_theme_mode", "simple")).strip().lower() == "detailed" and category:
        category_key = THEME_CATEGORY_KEYS.get(category)
        if category_key:
            value = getattr(args, category_key, "") or value
    value = str(value or "").strip().lower()
    if not value:
        return None
    if value == "rainbow":
        return value
    if value in NAMED_THEME_COLORS:
        return NAMED_THEME_COLORS[value]
    raw = value.removeprefix("#")
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        raise ValueError(f"Invalid ui_theme_color: {value}")
    try:
        return tuple(int(raw[index : index + 2], 16) for index in range(0, 6, 2))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"Invalid ui_theme_color: {value}") from exc


def _themed_color(
    color: Color,
    args: argparse.Namespace,
    role: str,
    category: str | None = None,
) -> Color:
    theme = _theme_rgb(args, category)
    opacity_key = "ui_panel_opacity" if role in {"panel", "track"} else "ui_accent_opacity"
    opacity = max(0.0, min(1.0, float(getattr(args, opacity_key, 1.0))))
    alpha = round(color[3] * opacity)
    if theme is None or role == "danger":
        return color[0], color[1], color[2], alpha
    if theme == "rainbow":
        theme = RAINBOW_REFERENCE_RGB

    red, green, blue = (channel / 255 for channel in color[:3])
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    target_hue, target_saturation, _ = colorsys.rgb_to_hsv(*(channel / 255 for channel in theme))
    if role in {"panel", "track"}:
        hue = target_hue
        saturation = max(saturation, target_saturation * (0.58 if role == "panel" else 0.35))
    elif role == "text":
        hue = target_hue
        saturation = min(0.42, max(0.2, target_saturation * 0.42))
    else:
        base_hue = colorsys.rgb_to_hsv(*(channel / 255 for channel in BASE_THEME_RGB))[0]
        relative_hue = (hue - base_hue + 0.5) % 1.0 - 0.5
        hue = (target_hue + relative_hue * 0.25) % 1.0
    themed = colorsys.hsv_to_rgb(hue, min(1.0, saturation), value)
    themed_rgb = tuple(round(channel * 255) for channel in themed)
    return themed_rgb[0], themed_rgb[1], themed_rgb[2], alpha


def _themed_fill(
    fill: Fill,
    args: argparse.Namespace,
    role: str,
    category: str | None = None,
) -> Fill:
    theme = _theme_rgb(args, category)
    if theme == "rainbow" and role in {"accent", "text", "stroke"}:
        colors = (fill,) if isinstance(fill[0], int) else fill  # type: ignore[index,assignment]
        source_alpha = max(color[3] for color in colors)  # type: ignore[union-attr]
        opacity = max(0.0, min(1.0, float(getattr(args, "ui_accent_opacity", 1.0))))
        alpha = round(source_alpha * opacity)
        if role == "stroke":
            dark_colors = []
            for red, green, blue in RAINBOW_COLORS:
                hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
                dark_rgb = colorsys.hsv_to_rgb(hue, max(0.72, saturation), value * 0.72)
                dark_colors.append(tuple(round(channel * 255) for channel in dark_rgb))
            return tuple((*color, alpha) for color in dark_colors)
        return tuple((*color, alpha) for color in RAINBOW_COLORS)
    if isinstance(fill[0], int):  # type: ignore[index]
        return _themed_color(fill, args, role, category)  # type: ignore[arg-type]
    return tuple(_themed_color(color, args, role, category) for color in fill)  # type: ignore[arg-type]


def themed_color(
    color: Color,
    args: argparse.Namespace,
    role: str = "accent",
    category: str | None = None,
) -> Color:
    """Apply the shared UI theme to a color used by another asset renderer."""
    return _themed_color(color, args, role, category)


def themed_fill(
    fill: Fill,
    args: argparse.Namespace,
    role: str = "accent",
    category: str | None = None,
) -> Fill:
    """Apply the shared UI theme to a solid color or gradient."""
    return _themed_fill(fill, args, role, category)


def is_rainbow_theme(args: argparse.Namespace, category: str | None = None) -> bool:
    return _theme_rgb(args, category) == "rainbow"


def _fill_layer(size: tuple[int, int], fill: Fill, mask: Image.Image) -> Image.Image:
    if isinstance(fill[0], int):  # type: ignore[index]
        layer = Image.new("RGBA", size, fill)  # type: ignore[arg-type]
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        return layer

    colors: Sequence[Color] = fill  # type: ignore[assignment]
    gradient = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = gradient.load()
    segments = max(1, len(colors) - 1)
    for y in range(size[1]):
        position = 0.0 if size[1] == 1 else y / (size[1] - 1)
        scaled = min(segments - 1e-9, position * segments)
        index = int(scaled)
        local = scaled - index
        start = colors[index]
        end = colors[min(index + 1, len(colors) - 1)]
        color = tuple(round(start[i] * (1 - local) + end[i] * local) for i in range(4))
        for x in range(size[0]):
            pixels[x, y] = color
    gradient.putalpha(ImageChops.multiply(gradient.getchannel("A"), mask))
    return gradient


def _rect_mask(size: tuple[int, int], box: tuple[int, int, int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def _composite_fill(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: Fill,
) -> Image.Image:
    mask = _rect_mask(canvas.size, box, radius)
    canvas.alpha_composite(_fill_layer(canvas.size, fill, mask))
    return mask


def _draw_outline(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    color: Color,
    width: int,
) -> None:
    if width <= 0 or color[3] <= 0:
        return
    draw = ImageDraw.Draw(canvas)
    for offset in range(width):
        inset = (box[0] + offset, box[1] + offset, box[2] - offset, box[3] - offset)
        draw.rounded_rectangle(inset, radius=max(1, radius - offset), outline=color)


def _font_for_box(
    font_path: Path,
    text: str,
    max_width: int,
    max_height: int,
    stroke_width: int = 0,
) -> ImageFont.FreeTypeFont:
    low, high, best = 1, max(max_width, max_height, 16) * 2, 1
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    while low <= high:
        size = (low + high) // 2
        font = ImageFont.truetype(str(font_path), size)
        bbox = probe.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
            best = size
            low = size + 1
        else:
            high = size - 1
    return ImageFont.truetype(str(font_path), best)


def _resolve_font(value: str | Path, root: Path) -> Path:
    candidate = Path(value)
    for path in (candidate, root / candidate, Path("C:/Windows/Fonts") / candidate.name):
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"Font not found: {value}")


def _draw_gradient_text(
    canvas: Image.Image,
    text: str,
    font_path: Path,
    box: tuple[int, int, int, int],
    fill: Fill,
    stroke_fill: Color,
    stroke_width: int,
) -> None:
    font = _font_for_box(font_path, text, box[2] - box[0], box[3] - box[1], stroke_width)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    origin = (
        box[0] + (box[2] - box[0] - (bbox[2] - bbox[0])) // 2 - bbox[0],
        box[1] + (box[3] - box[1] - (bbox[3] - bbox[1])) // 2 - bbox[1],
    )
    if stroke_width > 0 and stroke_fill[3] > 0:
        stroke_mask = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(stroke_mask).text(
            origin, text, font=font, fill=255, stroke_width=stroke_width, stroke_fill=255
        )
        stroke_layer = Image.new("RGBA", canvas.size, stroke_fill)
        stroke_layer.putalpha(stroke_mask)
        canvas.alpha_composite(stroke_layer)
    fill_mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(fill_mask).text(origin, text, font=font, fill=255)
    canvas.alpha_composite(_fill_layer(canvas.size, fill, fill_mask))


def _add_panel_shadow(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    blur: int,
) -> None:
    shadow_box = (box[0] + blur // 3, box[1] + blur // 2, box[2] + blur // 3, box[3] + blur // 2)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 105))
    shadow.putalpha(_rect_mask(canvas.size, shadow_box, radius).filter(ImageFilter.GaussianBlur(blur)))
    canvas.alpha_composite(shadow)


def render_score_ui_asset(path: Path, args: argparse.Namespace, root: Path) -> Image.Image:
    with Image.open(path) as original:
        width, height = original.size
        source_alpha = original.convert("RGBA").getchannel("A")
    name = path.name.lower()
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glass = _themed_fill(args.score_ui_glass, args, "panel", "score_auto")
    outline = _themed_color(args.score_ui_outline, args, "accent", "score_auto")
    track = _themed_color(args.score_ui_track, args, "track", "score_auto")
    bar = _themed_fill(args.score_ui_bar, args, "accent", "score_auto")
    text_fill = _themed_fill(args.score_ui_text, args, "text", "score_auto")

    if name == "bar.png":
        box = (2, 5, width - 3, height - 6)
        radius = max(1, (box[3] - box[1]) // 2)
        _composite_fill(canvas, box, radius, bar)
        _composite_fill(
            canvas,
            (box[0] + 12, box[1] + 4, box[2] - 12, box[1] + max(7, height // 5)),
            max(2, height // 10),
            ((255, 255, 255, 125), (255, 255, 255, 0)),
        )
        _draw_outline(canvas, box, radius, outline, 2)
        return canvas

    if name == "bars.png":
        font_path = _resolve_font(args.score_ui_font or args.score_font, root)
        label_boxes = {
            "C": (384, 10, 410, 40),
            "B": (476, 10, 502, 40),
            "A": (563, 10, 592, 40),
            "S": (655, 10, 679, 40),
        }
        marker_boxes = {
            "C": (390, 46, 405, 59),
            "B": (478, 46, 494, 80),
            "A": (569, 46, 585, 80),
            "S": (659, 46, 675, 80),
        }
        for rank, label_box in label_boxes.items():
            _draw_gradient_text(
                canvas,
                rank,
                font_path,
                label_box,
                text_fill,
                (3, 9, 24, 230),
                1,
            )
            marker_box = marker_boxes[rank]
            _composite_fill(canvas, marker_box, 2, track)
            cap_height = max(3, (marker_box[3] - marker_box[1]) // 3)
            _composite_fill(
                canvas,
                (marker_box[0], marker_box[1], marker_box[2], marker_box[1] + cap_height),
                2,
                bar,
            )
            _draw_outline(canvas, marker_box, 2, outline, 1)
        return canvas

    if name == "fg.png":
        # Keep the original threshold silhouette aligned with the v3 score UI,
        # while replacing its letters with the configured UI font.
        panel_mask = source_alpha.copy()
        label_boxes = {
            "C": (1072, 30, 1148, 112),
            "B": (1320, 30, 1395, 112),
            "A": (1564, 30, 1644, 112),
            "S": (1813, 30, 1888, 112),
        }
        mask_draw = ImageDraw.Draw(panel_mask)
        for box in label_boxes.values():
            mask_draw.rectangle(box, fill=0)
        canvas.alpha_composite(_fill_layer(canvas.size, glass, panel_mask))
        font_path = _resolve_font(args.score_ui_font or args.score_font, root)
        for rank, box in label_boxes.items():
            _draw_gradient_text(
                canvas,
                rank,
                font_path,
                box,
                text_fill,
                (3, 9, 24, 230),
                2,
            )
        return canvas

    # Keep the original UI silhouette and coordinates. The runtime offsets bar.png
    # by (34, -3), which maps its 1650x76 canvas to this track rectangle.
    panel_mask = source_alpha.copy()
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 105))
    shadow.putalpha(panel_mask.filter(ImageFilter.GaussianBlur(max(4, height // 40))))
    canvas.alpha_composite(shadow, (5, 7))
    canvas.alpha_composite(_fill_layer(canvas.size, glass, panel_mask))

    track_box = (369, 171, 2017, 247)
    track_radius = (track_box[3] - track_box[1]) // 2
    _composite_fill(canvas, track_box, track_radius, track)
    _draw_outline(canvas, track_box, track_radius, _themed_color((139, 255, 226, 70), args, "accent", "score_auto"), 1)
    _draw_gradient_text(
        canvas,
        "SCORE",
        _resolve_font(args.score_ui_font or args.score_font, root),
        (397, 72, 706, 157),
        text_fill,
        (3, 9, 24, 220),
        1,
    )
    return canvas


def render_life_ui_asset(path: Path, args: argparse.Namespace, root: Path) -> Image.Image:
    with Image.open(path) as original:
        width, height = original.size
        source_alpha_bbox = original.convert("RGBA").getchannel("A").getbbox()
    name = path.name.lower()
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glass = _themed_fill(args.life_ui_glass, args, "panel", "life")
    outline = _themed_color(args.life_ui_outline, args, "accent", "life")
    track = _themed_color(args.life_ui_track, args, "track", "life")
    normal = _themed_fill(args.life_ui_normal, args, "accent", "life")
    overflow = _themed_fill(args.life_ui_overflow, args, "accent", "life")
    danger = _themed_fill(args.life_ui_danger, args, "danger", "life")
    text_fill = _themed_fill(args.life_ui_text, args, "text", "life")

    if name == "bg.png":
        mask_path = path.parent / "mask.png"
        with Image.open(mask_path) as mask_source:
            bar_box = mask_source.convert("RGBA").getchannel("A").getbbox()
    else:
        bar_box = source_alpha_bbox
    bar_box = bar_box or (round(width * 0.147), round(height * 0.462), round(width * 0.747), round(height * 0.612))
    bar_draw_box = (bar_box[0], bar_box[1], bar_box[2] - 1, bar_box[3] - 1)
    bar_radius = max(8, (bar_box[3] - bar_box[1]) // 2)

    if name == "mask.png":
        _composite_fill(canvas, bar_draw_box, bar_radius, (255, 255, 255, 255))
        return canvas

    fills = {
        "normal.png": normal,
        "overflow.png": overflow,
        "danger.png": danger,
    }
    if name in fills:
        _composite_fill(canvas, bar_draw_box, bar_radius, fills[name])
        highlight = (
            bar_box[0] + 18,
            bar_box[1] + 7,
            bar_box[2] - 18,
            bar_box[1] + max(10, round((bar_box[3] - bar_box[1]) * 0.3)),
        )
        _composite_fill(canvas, highlight, max(4, (highlight[3] - highlight[1]) // 2), ((255, 255, 255, 115), (255, 255, 255, 0)))
        _draw_outline(canvas, bar_draw_box, bar_radius, (255, 255, 255, 80), 1)
        return canvas

    bg_bbox = source_alpha_bbox or (round(width * 0.035), round(height * 0.08), round(width * 0.99), round(height * 0.99))
    outer = (bg_bbox[0], max(0, bg_bbox[1] + round(height * 0.02)), bg_bbox[2], min(height - 1, bg_bbox[3] - round(height * 0.03)))
    outer_radius = max(16, round(height * 0.16))
    _add_panel_shadow(canvas, outer, outer_radius, max(5, height // 48))
    _composite_fill(canvas, outer, outer_radius, glass)
    _draw_outline(canvas, outer, outer_radius, outline, max(2, height // 180))
    _composite_fill(canvas, bar_draw_box, bar_radius, track)
    _draw_outline(canvas, bar_draw_box, bar_radius, _themed_color((139, 255, 226, 62), args, "accent", "life"), 1)

    heart_box = (
        outer[0] + round(width * 0.055),
        bar_box[1] - round(height * 0.045),
        outer[0] + round(width * 0.13),
        bar_box[3] + round(height * 0.08),
    )
    heart = Image.new("L", canvas.size, 0)
    heart_draw = ImageDraw.Draw(heart)
    heart_width = heart_box[2] - heart_box[0]
    heart_height = heart_box[3] - heart_box[1]
    lobe = heart_width // 2
    heart_draw.ellipse((heart_box[0], heart_box[1], heart_box[0] + lobe, heart_box[1] + lobe), fill=255)
    heart_draw.ellipse((heart_box[2] - lobe, heart_box[1], heart_box[2], heart_box[1] + lobe), fill=255)
    heart_draw.polygon(
        [(heart_box[0], heart_box[1] + lobe // 2), (heart_box[2], heart_box[1] + lobe // 2), (heart_box[0] + heart_width // 2, heart_box[1] + heart_height)],
        fill=255,
    )
    canvas.alpha_composite(_fill_layer(canvas.size, normal, heart))
    _draw_gradient_text(
        canvas,
        "LIFE",
        _resolve_font(args.life_ui_font or args.life_font or args.combo_font, root),
        (outer[0] + round(width * 0.15), outer[1] + round(height * 0.05), outer[0] + round(width * 0.32), bar_box[1] - round(height * 0.06)),
        text_fill,
        (3, 9, 24, 225),
        1,
    )
    return canvas


def render_auto_ui_asset(path: Path, args: argparse.Namespace, root: Path) -> Image.Image:
    with Image.open(path) as original:
        width, height = original.size
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glass = _themed_fill(args.auto_ui_glass, args, "panel", "score_auto")
    outline = _themed_color(args.auto_ui_outline, args, "accent", "score_auto")
    accent = _themed_fill(args.auto_ui_accent, args, "accent", "score_auto")
    text_fill = _themed_fill(args.auto_ui_text, args, "text", "score_auto")
    outer = (5, 5, width - 6, height - 7)
    radius = (outer[3] - outer[1]) // 2
    _add_panel_shadow(canvas, outer, radius, 5)
    _composite_fill(canvas, outer, radius, glass)
    _draw_outline(canvas, outer, radius, outline, 2)

    # Compact music-note mark, drawn as geometry so it remains crisp at 74 px.
    draw = ImageDraw.Draw(canvas)
    icon = accent[-1] if not isinstance(accent[0], int) else accent
    ix, iy = 35, 23
    draw.rounded_rectangle((ix + 10, iy, ix + 14, iy + 24), radius=2, fill=icon)
    draw.polygon([(ix + 12, iy), (ix + 29, iy - 4), (ix + 29, iy + 2), (ix + 12, iy + 6)], fill=icon)
    draw.ellipse((ix, iy + 17, ix + 14, iy + 30), fill=icon)

    text = "AUTO LIVE" if path.name.lower() == "autolive.png" else "AUTO-PLAY"
    _draw_gradient_text(
        canvas,
        text,
        _resolve_font(args.auto_ui_font or args.combo_font, root),
        (72, 15, width - 20, height - 15),
        text_fill,
        (3, 9, 24, 235),
        1,
    )
    return canvas


def render_ui_asset(path: Path, renderer: str, args: argparse.Namespace, root: Path) -> Image.Image:
    if renderer == "score_ui":
        return render_score_ui_asset(path, args, root)
    if renderer == "life_ui":
        return render_life_ui_asset(path, args, root)
    if renderer == "auto_ui":
        return render_auto_ui_asset(path, args, root)
    raise ValueError(f"Unknown UI renderer: {renderer}")
