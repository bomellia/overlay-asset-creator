from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance


RGB = tuple[float, float, float]


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {Path(sys.argv[0]).name} <cover.png> [-v 1|-v 3]", file=sys.stderr)
        return 2

    cover_path = Path(sys.argv[1]).resolve()
    version = "3"
    if len(sys.argv) >= 4 and sys.argv[2] == "-v":
        version = sys.argv[3]

    base_path = find_base_image(version)
    cover = Image.open(cover_path).convert("RGBA")
    base = Image.open(base_path).convert("RGBA")
    base = fit_base_to_output_size(base, version)

    output = generate_background(base, cover, version)
    output_path = cover_path.with_name("cover.output.png")
    output.save(output_path)
    print(f"generated {output_path} using {base_path}")
    return 0


def fit_base_to_output_size(base: Image.Image, version: str) -> Image.Image:
    if version == "1":
        return base

    target_size = (2048, 1168)
    if base.size == target_size:
        return base

    return cover_fill(base, target_size)


def find_base_image(version: str) -> Path:
    name = "background-v1_full.png" if version == "1" else "background_full.png"
    candidates: list[Path] = []

    env_assets = os.environ.get("PJSEKAI_BG_ASSETS_DIR")
    if env_assets:
        candidates.append(Path(env_assets) / name)

    exe_dir = executable_dir()
    candidates.extend(
        [
            exe_dir / ".." / "assets" / name,
            exe_dir / "assets" / name,
            Path.cwd() / "assets" / name,
            Path.cwd() / ".." / "assets" / name,
        ]
    )

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved

    raise FileNotFoundError(
        f"{name} was not found. Set PJSEKAI_BG_ASSETS_DIR or place this exe in dependencies."
    )


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def generate_background(base: Image.Image, cover: Image.Image, version: str) -> Image.Image:
    width, height = base.size
    cover_layer = cover_fill(cover, (width, height))
    cover_layer = cover_layer.resize(
        (max(24, width // 36), max(24, height // 36)), Image.Resampling.BILINEAR
    ).resize((width, height), Image.Resampling.BICUBIC)
    cover_layer = ImageEnhance.Color(cover_layer).enhance(1.35)

    left, center, right = sample_palette(cover)
    base_arr = np.asarray(base, dtype=np.float32) / 255.0
    cover_arr = np.asarray(cover_layer, dtype=np.float32) / 255.0

    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)

    left_arr = np.asarray(left, dtype=np.float32)
    center_arr = np.asarray(center, dtype=np.float32)
    right_arr = np.asarray(right, dtype=np.float32)

    gradient = np.empty((width, 3), dtype=np.float32)
    mask = x < 0.5
    t_left = smoothstep_np(np.clip(x[mask] * 2.0, 0.0, 1.0))[:, None]
    t_right = smoothstep_np(np.clip((x[~mask] - 0.5) * 2.0, 0.0, 1.0))[:, None]
    gradient[mask] = left_arr + (center_arr - left_arr) * t_left
    gradient[~mask] = center_arr + (right_arr - center_arr) * t_right
    gradient = gradient[None, :, :]

    xx = x[None, :]
    yy = y[:, None]
    dx = (xx - 0.5) / 0.72
    dy = (yy - 0.56) / 0.62
    falloff = np.clip(1.0 - np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
    accent = center_arr[None, None, :] * (0.72 + 0.56 * smoothstep_np(falloff))[:, :, None]

    cover_rgb = cover_arr[:, :, :3]
    tint = cover_rgb + (gradient - cover_rgb) * 0.55
    tint = tint + (accent - tint) * 0.18
    tint = normalize_tint_np(tint)

    base_rgb = base_arr[:, :, :3]
    alpha = base_arr[:, :, 3:4]
    luma = (
        base_rgb[:, :, 0:1] * 0.299
        + base_rgb[:, :, 1:2] * 0.587
        + base_rgb[:, :, 2:3] * 0.114
    )
    colorized = tint * (0.08 + 1.35 * luma)
    amount = np.where(luma < 0.08, 0.38, np.where(luma > 0.72, 0.86, 0.72))
    final = base_rgb + (colorized - base_rgb) * amount

    glow = smoothstep_np(np.clip((luma - 0.42) / 0.58, 0.0, 1.0))
    final = np.clip(final + tint * glow * 0.12, 0.0, 1.0)

    out_arr = np.concatenate([final, alpha], axis=2)
    background = Image.fromarray(np.round(out_arr * 255.0).astype(np.uint8), "RGBA")
    return add_cover_frame(background, cover, version)


def add_cover_frame(background: Image.Image, cover: Image.Image, version: str) -> Image.Image:
    width, height = background.size
    framed = background.copy()

    if version == "1":
        frame_size = int(min(width * 0.225, height * 0.54))
        center_y = int(height * 0.325)
        border = max(2, round(frame_size * 0.006))
        radius = max(6, round(frame_size * 0.015))
    else:
        frame_size = int(min(width * 0.225, height * 0.39))
        center_y = int(height * 0.34)
        border = max(2, round(frame_size * 0.006))
        radius = max(12, round(frame_size * 0.035))

    center_x = width // 2
    left = center_x - frame_size // 2
    top = center_y - frame_size // 2

    palette = sample_palette(cover)
    accent = tuple(to_byte(v) for v in palette[1])
    sub_accent = tuple(to_byte(v) for v in palette[2])

    panel_size = (frame_size + border * 2, frame_size + border * 2)
    panel = Image.new("RGBA", panel_size, (0, 0, 0, 0))
    panel_mask = rounded_rect_mask(panel_size, radius + border)

    ring_mask = rounded_rect_outline_mask(panel_size, radius + border, border)
    border_img = make_border_gradient(panel_size, accent, sub_accent)
    border_img.putalpha(ring_mask)
    panel.alpha_composite(border_img)

    plate_mask = rounded_rect_mask((frame_size, frame_size), radius)
    plate = Image.new("RGBA", (frame_size, frame_size), (5, 7, 16, 255))
    cover_img = cover_fill(cover, (frame_size, frame_size))
    cover_img = ImageEnhance.Color(cover_img).enhance(1.04)
    cover_img = ImageEnhance.Contrast(cover_img).enhance(1.04)
    cover_img = apply_screen_mask(cover_img, plate_mask, version)
    cover_img.putalpha(plate_mask)
    plate.alpha_composite(cover_img)
    plate.putalpha(plate_mask)
    panel.alpha_composite(plate, (border, border))

    highlight_mask = top_rounded_rect_mask((frame_size, max(2, frame_size // 3)), radius)
    highlight_grad = Image.new("RGBA", highlight_mask.size, (255, 255, 255, 0))
    grad_px = highlight_grad.load()
    for y in range(highlight_grad.height):
        alpha = round(52 * (1.0 - y / max(1, highlight_grad.height - 1)))
        for x in range(highlight_grad.width):
            grad_px[x, y] = (255, 255, 255, alpha)
    highlight_grad.putalpha(ImageChops.multiply(highlight_grad.getchannel("A"), highlight_mask))
    panel.alpha_composite(highlight_grad, (border, border))

    panel.putalpha(ImageChops.multiply(panel.getchannel("A"), panel_mask))
    framed.alpha_composite(panel, (left - border, top - border))

    return framed


def rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def top_rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] + radius), radius=radius, fill=255)
    return mask.crop((0, 0, size[0], size[1]))


def rounded_rect_outline_mask(size: tuple[int, int], radius: int, width: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    inset = max(0, width // 2)
    draw.rounded_rectangle(
        (inset, inset, size[0] - 1 - inset, size[1] - 1 - inset),
        radius=max(0, radius - inset),
        outline=255,
        width=max(1, width),
    )
    return mask


def make_border_gradient(size: tuple[int, int], accent: tuple[int, int, int], sub_accent: tuple[int, int, int]) -> Image.Image:
    width, height = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    px = img.load()
    for y in range(height):
        ny = y / max(1, height - 1)
        for x in range(width):
            nx = x / max(1, width - 1)
            t = smoothstep((nx + ny) * 0.5)
            r = round(accent[0] + (sub_accent[0] - accent[0]) * t)
            g = round(accent[1] + (sub_accent[1] - accent[1]) * t)
            b = round(accent[2] + (sub_accent[2] - accent[2]) * t)
            px[x, y] = (r, g, b, 255)
    return img


def apply_screen_mask(image: Image.Image, mask: Image.Image, version: str) -> Image.Image:
    width, height = image.size
    out = image.convert("RGBA")

    light = Image.new("RGBA", image.size, (255, 255, 255, 0))
    light_draw = ImageDraw.Draw(light)

    pitch = max(9, round(width / 58))
    diamond = max(2, round(pitch * 0.26))
    line_alpha = 28 if version == "1" else 24
    dot_alpha = 62 if version == "1" else 54

    offset = pitch // 2
    points: list[tuple[int, int]] = []
    for y in range(offset, height, pitch):
        for x in range(offset, width, pitch):
            points.append((x, y))

    for x, y in points:
        if x + pitch < width:
            light_draw.line((x, y, x + pitch, y), fill=(255, 255, 255, line_alpha), width=1)
        if y + pitch < height:
            light_draw.line((x, y, x, y + pitch), fill=(255, 255, 255, max(8, line_alpha - 8)), width=1)

    for x, y in points:
        light_draw.polygon(
            (
                (x, y - diamond),
                (x + diamond, y),
                (x, y + diamond),
                (x - diamond, y),
            ),
            fill=(255, 255, 255, dot_alpha),
        )

    vignette = Image.new("L", image.size, 0)
    vignette_px = vignette.load()
    cx = (width - 1) / 2
    cy = (height - 1) / 2
    max_dist = math.sqrt(cx * cx + cy * cy)
    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist
            vignette_px[x, y] = round(34 * smoothstep(max(0.0, (dist - 0.48) / 0.52)))

    vignette_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    vignette_layer.putalpha(ImageChops.multiply(vignette, mask))

    masked_alpha = mask
    light.putalpha(ImageChops.multiply(light.getchannel("A"), masked_alpha))

    out.alpha_composite(light)
    out.alpha_composite(vignette_layer)
    return out


def cover_fill(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize(
        (math.ceil(src_w * scale), math.ceil(src_h * scale)), Image.Resampling.BICUBIC
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def sample_palette(image: Image.Image) -> tuple[RGB, RGB, RGB]:
    small = image.convert("RGBA").resize((64, 64), Image.Resampling.BILINEAR)
    pixels = small.load()
    acc = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    weights = [0.0, 0.0, 0.0]

    for y in range(64):
        ny = y / 63
        for x in range(64):
            nx = x / 63
            r, g, b, a = pixels[x, y]
            if a < 13:
                continue
            c = (r / 255.0, g / 255.0, b / 255.0)
            luma = c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114
            weight = 0.18 + saturation(c) * 1.4 + luma * 0.35
            weight *= 0.65 + 0.35 * math.sin(ny * math.pi)

            side_weights = (
                clamp01(1.0 - nx * 1.7),
                clamp01(1.0 - abs(nx - 0.5) * 2.4),
                clamp01((nx - 0.38) * 1.7),
            )
            for i, side_weight in enumerate(side_weights):
                w = weight * side_weight
                acc[i] = add_weighted(acc[i], c, w)
                weights[i] += w

    fallback = ((0.05, 0.35, 0.95), (0.55, 0.20, 0.85), (0.95, 0.15, 0.55))
    return tuple(boost_color(div_rgb(acc[i], weights[i], fallback[i])) for i in range(3))  # type: ignore[return-value]


def three_point_gradient(left: RGB, center: RGB, right: RGB, t: float) -> RGB:
    if t < 0.5:
        return mix_rgb(left, center, smoothstep(t * 2))
    return mix_rgb(center, right, smoothstep((t - 0.5) * 2))


def radial_accent(center: RGB, x: float, y: float) -> RGB:
    dx = (x - 0.5) / 0.72
    dy = (y - 0.56) / 0.62
    falloff = clamp01(1.0 - math.sqrt(dx * dx + dy * dy))
    return scale_rgb(center, 0.72 + 0.56 * smoothstep(falloff))


def add_glow(base: RGB, tint: RGB, luma: float) -> RGB:
    glow = smoothstep(clamp01((luma - 0.42) / 0.58))
    return tuple(clamp01(base[i] + tint[i] * glow * 0.12) for i in range(3))  # type: ignore[return-value]


def boost_color(c: RGB) -> RGB:
    luma = c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114
    c = mix_rgb((luma, luma, luma), c, 1.45)
    if luma < 0.28:
        c = mix_rgb(c, (0.18, 0.18, 0.22), 0.18)
    return normalize_tint(c)


def normalize_tint(c: RGB) -> RGB:
    max_c = max(c)
    if max_c <= 0:
        return (0.18, 0.18, 0.22)
    if max_c < 0.20:
        c = scale_rgb(c, 0.20 / max_c)
    return tuple(clamp01(v) for v in c)  # type: ignore[return-value]


def saturation(c: RGB) -> float:
    max_c = max(c)
    min_c = min(c)
    if max_c <= 0:
        return 0.0
    return (max_c - min_c) / max_c


def mix_rgb(a: Iterable[float], b: Iterable[float], t: float) -> RGB:
    t = clamp01(t)
    aa = tuple(a)
    bb = tuple(b)
    return tuple(aa[i] + (bb[i] - aa[i]) * t for i in range(3))  # type: ignore[return-value]


def add_weighted(a: RGB, b: RGB, weight: float) -> RGB:
    return (a[0] + b[0] * weight, a[1] + b[1] * weight, a[2] + b[2] * weight)


def div_rgb(c: RGB, weight: float, fallback: RGB) -> RGB:
    if weight <= 0:
        return fallback
    return (c[0] / weight, c[1] / weight, c[2] / weight)


def scale_rgb(c: RGB, value: float) -> RGB:
    return (c[0] * value, c[1] * value, c[2] * value)


def smoothstep(t: float) -> float:
    t = clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def smoothstep_np(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def normalize_tint_np(c: np.ndarray) -> np.ndarray:
    max_c = np.max(c, axis=2, keepdims=True)
    safe_max = np.where(max_c <= 0.0, 1.0, max_c)
    scale = np.where((max_c > 0.0) & (max_c < 0.20), 0.20 / safe_max, 1.0)
    c = c * scale
    fallback = np.asarray((0.18, 0.18, 0.22), dtype=np.float32)
    c = np.where(max_c <= 0.0, fallback[None, None, :], c)
    return np.clip(c, 0.0, 1.0)


def clamp01(value: float) -> float:
    if math.isnan(value) or value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def to_byte(value: float) -> int:
    return round(clamp01(value) * 255)


if __name__ == "__main__":
    raise SystemExit(main())
