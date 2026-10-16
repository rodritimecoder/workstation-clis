#!/usr/bin/env python3
"""
pi_emote_icm.py — Autonomous ICM Pipeline for pi-emote Pixel Art Avatar Sets.

Transforms 1 raw concept avatar image into a fully-consistent 10-state,
4-talk-variation emote set for https://github.com/cgxeiji/pi-emote.

Stages:
  01_concept/         Raw AI image / concept sketch
  02_squared_nobg/    Chroma-keyed transparency + centered 1:1 square canvas
  03_pixelated/       Quantized 32x32 grid master + 128x128 Nearest-Neighbor sprite
  04_layers/          Modular sprite slices (Base body, Eyes, Mouths, Props)
  05_states/          Composited frames across all 10 emote triggers
  06_dist/            Final pi-emote package with verified emotes.json
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("❌ Error: Pillow is required. Install via `pip install Pillow`.")


def auto_remove_background(img: Image.Image, tolerance: int = 30) -> Image.Image:
    """Removes green-screen or solid/flat background using chroma keying."""
    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    # 1. Check for bright green screen (e.g. #00FF00)
    green_count = 0
    sample_points = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 4, 0)]
    for sx, sy in sample_points:
        r, g, b, a = pixels[sx, sy]
        if g > 140 and g > r * 1.35 and g > b * 1.35:
            green_count += 1

    if green_count >= 3:
        # Green screen mode with edge defringing
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if g > 110 and g > r * 1.15 and g > b * 1.15:
                    pixels[x, y] = (0, 0, 0, 0)
                elif a > 0 and g > r and g > b:
                    pixels[x, y] = (0, 0, 0, 0)
                elif a < 64:
                    pixels[x, y] = (0, 0, 0, 0)
        return img

    # 2. General corner-based keying
    corners = [pixels[0, 0], pixels[w - 1, 0], pixels[0, h - 1], pixels[w - 1, h - 1]]
    bg_color = max(set(corners), key=corners.count)
    if bg_color[3] == 0:
        return img

    br, bg, bb = bg_color[0], bg_color[1], bg_color[2]
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0 and abs(r - br) <= tolerance and abs(g - bg) <= tolerance and abs(b - bb) <= tolerance:
                pixels[x, y] = (0, 0, 0, 0)

    return img


def square_and_center(img: Image.Image, target_size: int = 128) -> Image.Image:
    """Crops transparent bounding box and centers into a 1:1 square canvas."""
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    w, h = img.size
    max_dim = max(w, h)
    
    # Create square canvas with 5% breathing margin
    side = int(max_dim * 1.05)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    paste_x = (side - w) // 2
    paste_y = (side - h) // 2
    square.paste(img, (paste_x, paste_y), img)

    return square.resize((target_size, target_size), resample=Image.Resampling.LANCZOS)


def pixelate_nearest_neighbor(
    img: Image.Image,
    grid_size: int = 128,
    target_size: int = 128,
    palette_colors: int = 32,
) -> Tuple[Image.Image, Image.Image]:
    """
    Downsamples to grid_size, optionally clamps palette,
    then upscales back to target_size using NEAREST resampling.
    Returns (grid_image, upscaled_image).
    """
    img = img.convert("RGBA")
    
    if grid_size >= target_size:
        # Native resolution mode — preserve all hand-drawn / AI pixel details
        final_img = img.resize((target_size, target_size), resample=Image.Resampling.LANCZOS)
        return final_img, final_img

    # 1. Downsample to small pixel grid
    small = img.resize((grid_size, grid_size), resample=Image.Resampling.BOX)

    # 2. Color Palette Quantization (preserves alpha)
    alpha = small.split()[3]
    rgb = small.convert("RGB").quantize(colors=palette_colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    quantized = Image.new("RGBA", (grid_size, grid_size))
    quantized.paste(rgb, (0, 0))
    quantized.putalpha(alpha)

    # 3. Nearest-Neighbor upscale to target canvas size
    upscaled = quantized.resize((target_size, target_size), resample=Image.Resampling.NEAREST)

    return quantized, upscaled


def init_workspace(slug: str, base_dir: Path) -> Path:
    """Scaffolds a 6-stage ICM workspace for the avatar."""
    ws = base_dir / slug
    stages = [
        "01_concept",
        "02_squared_nobg",
        "03_pixelated",
        "04_layers",
        "05_states",
        "06_dist",
    ]
    for s in stages:
        (ws / s).mkdir(parents=True, exist_ok=True)

    icm_map = f"""# ICM Workspace: {slug}
**Target Output**: `pi-emote` Emote Set (`~/.pi/agent/extensions/pi-emote/emotes/{slug}/`)

## 📂 Stage Walk
1. `01_concept/`: Place raw avatar image here (`avatar.png`).
2. `02_squared_nobg/`: Auto-keyed alpha channel & 1:1 squared canvas.
3. `03_pixelated/`: 32x32 pixel master & 128x128 Nearest-Neighbor sprite.
4. `04_layers/`: Decomposed sprite slices (base body, eyes, mouths, props).
5. `05_states/`: Composited frames for all 10 states + 4 talk weights.
6. `06_dist/`: Clean package containing `emotes.json` and all state folders.
"""
    (ws / "ICM_MAP.md").write_text(icm_map, encoding="utf-8")
    print(f"✅ [pi-emote-icm] Initialized ICM workspace -> {ws}")
    return ws


def decompose_sprite_layers(sprite_128: Image.Image, layers_dir: Path) -> Dict[str, Path]:
    """
    Generates base body canvas and procedural feature overlays for eyes, mouths, and props.
    All layers match the 128x128 canvas dimensions for zero-offset compositing.
    """
    layers_dir.mkdir(parents=True, exist_ok=True)
    w, h = sprite_128.size
    
    # 1. Base Layer (Body & Head)
    base_path = layers_dir / "base.png"
    sprite_128.save(base_path)

    # Bounding box of character face region
    bbox = sprite_128.getbbox() or (0, 0, w, h)
    bx0, by0, bx1, by1 = bbox
    # Anchor points for face features
    cx = 64
    lx = 51
    rx = 76
    ey = 51
    my = 64

    # Sample skin color from face center
    pixels = sprite_128.load()
    skin_cand = pixels[cx, my - 6]
    skin = skin_cand if skin_cand[3] > 100 else (250, 222, 210, 255)
    eyelash = (42, 28, 48, 255)

    # 2. Eye Layers
    # Eye: Open (empty layer so natural face shines through)
    img_eyes_open = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img_eyes_open.save(layers_dir / "eyes_open.png")

    # Eye: Blink (covers pupil with skin tone and draws curved eyelid lashes)
    img_eyes_blink = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_eyes_blink)
    d.rectangle([lx - 6, ey - 2, lx + 7, ey + 3], fill=skin)
    d.rectangle([rx - 6, ey - 2, rx + 7, ey + 3], fill=skin)
    d.line([(lx - 6, ey), (lx, ey + 2), (lx + 6, ey)], fill=eyelash, width=2)
    d.line([(rx - 6, ey), (rx, ey + 2), (rx + 6, ey)], fill=eyelash, width=2)
    img_eyes_blink.save(layers_dir / "eyes_blink.png")

    # Eye: Look Up / Think
    img_eyes_think = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_eyes_think)
    d.rectangle([lx - 6, ey - 2, lx + 7, ey + 3], fill=skin)
    d.rectangle([rx - 6, ey - 2, rx + 7, ey + 3], fill=skin)
    d.line([(lx - 6, ey + 1), (lx, ey - 2), (lx + 6, ey + 1)], fill=eyelash, width=2)
    d.line([(rx - 6, ey + 1), (rx, ey - 2), (rx + 6, ey + 1)], fill=eyelash, width=2)
    img_eyes_think.save(layers_dir / "eyes_look_up.png")

    # Eye: Sparkle (Success / Hi)
    img_eyes_sparkle = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_eyes_sparkle)
    d.rectangle([lx - 6, ey - 2, lx + 7, ey + 3], fill=skin)
    d.rectangle([rx - 6, ey - 2, rx + 7, ey + 3], fill=skin)
    d.line([(lx - 6, ey + 1), (lx, ey - 2), (lx + 6, ey + 1)], fill=eyelash, width=2)
    d.line([(rx - 6, ey + 1), (rx, ey - 2), (rx + 6, ey + 1)], fill=eyelash, width=2)
    # Yellow sparkle stars next to eyes
    d.point([(lx - 8, ey - 3), (lx + 8, ey - 3), (rx - 8, ey - 3), (rx + 8, ey - 3)], fill=(255, 230, 80, 255))
    img_eyes_sparkle.save(layers_dir / "eyes_sparkle.png")

    # Eye: X / Dead (Failure)
    img_eyes_x = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_eyes_x)
    d.rectangle([lx - 6, ey - 2, lx + 7, ey + 3], fill=skin)
    d.rectangle([rx - 6, ey - 2, rx + 7, ey + 3], fill=skin)
    d.line([lx - 4, ey - 2, lx + 4, ey + 2], fill=(220, 40, 50, 255), width=2)
    d.line([lx - 4, ey + 2, lx + 4, ey - 2], fill=(220, 40, 50, 255), width=2)
    d.line([rx - 4, ey - 2, rx + 4, ey + 2], fill=(220, 40, 50, 255), width=2)
    d.line([rx - 4, ey + 2, rx + 4, ey - 2], fill=(220, 40, 50, 255), width=2)
    img_eyes_x.save(layers_dir / "eyes_x.png")

    # 3. Mouth Layers (4 pi-emote weights)
    # talk_close: Empty layer (natural face closed mouth)
    img_mouth_close = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img_mouth_close.save(layers_dir / "mouth_close.png")

    # talk_small: Small speaking dot / slit
    img_mouth_small = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_mouth_small)
    d.rectangle([cx - 4, my - 1, cx + 4, my + 3], fill=skin)
    d.rectangle([cx - 2, my, cx + 2, my + 2], fill=(160, 30, 40, 255), outline=eyelash)
    img_mouth_small.save(layers_dir / "mouth_small.png")

    # talk_mid: Medium speaking curve
    img_mouth_mid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_mouth_mid)
    d.rectangle([cx - 5, my - 1, cx + 5, my + 4], fill=skin)
    d.polygon([(cx - 3, my), (cx + 3, my), (cx, my + 4)], fill=(170, 30, 40, 255), outline=eyelash)
    img_mouth_mid.save(layers_dir / "mouth_mid.png")

    # talk_wide: Wide open speaking mouth
    img_mouth_wide = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_mouth_wide)
    d.rectangle([cx - 6, my - 1, cx + 6, my + 5], fill=skin)
    d.polygon([(cx - 5, my), (cx + 5, my), (cx, my + 6)], fill=(180, 30, 40, 255), outline=eyelash)
    img_mouth_wide.save(layers_dir / "mouth_wide.png")

    # 4. Props
    # prop_book (Read)
    img_book = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_book)
    by_prop = by1 - 16
    d.rectangle([cx - 16, by_prop, cx + 16, by_prop + 12], fill=(80, 140, 220, 255), outline=eyelash)
    d.line([cx, by_prop, cx, by_prop + 12], fill=(240, 240, 240, 255), width=2)
    img_book.save(layers_dir / "prop_book.png")

    # prop_wrench (Tool)
    img_tool = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_tool)
    tx = bx1 - 8
    ty = by0 + int((by1 - by0) * 0.6)
    d.line([tx - 12, ty + 12, tx + 6, ty - 6], fill=(180, 180, 190, 255), width=3)
    img_tool.save(layers_dir / "prop_wrench.png")

    # prop_sweat (Failure / Think Hard)
    img_sweat = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img_sweat)
    sx = bx1 - 12
    sy = by0 + 8
    d.polygon([(sx, sy), (sx - 3, sy + 6), (sx + 3, sy + 6)], fill=(60, 180, 240, 255), outline=eyelash)
    img_sweat.save(layers_dir / "prop_sweat.png")

    return {
        "base": base_path,
        "layers_dir": layers_dir,
    }


def composite_frame(base: Image.Image, *overlays: Image.Image) -> Image.Image:
    """Composites transparent overlay layers onto a base image."""
    canvas = base.copy().convert("RGBA")
    for ov in overlays:
        if ov:
            ov = ov.convert("RGBA")
            canvas.paste(ov, (0, 0), ov)
    return canvas


def assemble_emote_set(layers_dir: Path, states_dir: Path, dist_dir: Path) -> Path:
    """
    Assembles the 10 pi-emote states + 4 talk weights from modular layers,
    and creates the standard emotes.json.
    """
    states_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    base = Image.open(layers_dir / "base.png")
    eyes_open = Image.open(layers_dir / "eyes_open.png")
    eyes_blink = Image.open(layers_dir / "eyes_blink.png")
    eyes_think = Image.open(layers_dir / "eyes_look_up.png")
    eyes_sparkle = Image.open(layers_dir / "eyes_sparkle.png")
    eyes_x = Image.open(layers_dir / "eyes_x.png")

    mouth_close = Image.open(layers_dir / "mouth_close.png")
    mouth_small = Image.open(layers_dir / "mouth_small.png")
    mouth_mid = Image.open(layers_dir / "mouth_mid.png")
    mouth_wide = Image.open(layers_dir / "mouth_wide.png")

    prop_book = Image.open(layers_dir / "prop_book.png")
    prop_wrench = Image.open(layers_dir / "prop_wrench.png")
    prop_sweat = Image.open(layers_dir / "prop_sweat.png")

    # Definitions of states
    state_frames = {
        "idle": {
            "idle.png": composite_frame(base, eyes_open, mouth_close),
            "idle_blink.png": composite_frame(base, eyes_blink, mouth_close),
        },
        "think": {
            "think.png": composite_frame(base, eyes_think, mouth_small),
            "think_hard.png": composite_frame(base, eyes_think, mouth_small, prop_sweat),
        },
        "talk": {
            "talk_close.png": composite_frame(base, eyes_open, mouth_close),
            "talk_small.png": composite_frame(base, eyes_open, mouth_small),
            "talk_mid.png": composite_frame(base, eyes_open, mouth_mid),
            "talk_wide.png": composite_frame(base, eyes_open, mouth_wide),
        },
        "read": {
            "read.png": composite_frame(base, eyes_blink, prop_book),
        },
        "write": {
            "write.png": composite_frame(base, eyes_open, prop_book),
        },
        "tool": {
            "tool.png": composite_frame(base, eyes_open, mouth_close, prop_wrench),
        },
        "hi": {
            "hi.png": composite_frame(base, eyes_sparkle, mouth_mid),
        },
        "success": {
            "success.png": composite_frame(base, eyes_sparkle, mouth_mid),
        },
        "failure": {
            "failure.png": composite_frame(base, eyes_x, mouth_small, prop_sweat),
        },
    }

    # Compact state: Vertically squished character
    compact_squished = base.resize((128, 96), resample=Image.Resampling.LANCZOS)
    compact_canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    compact_canvas.paste(compact_squished, (0, 32), compact_squished)
    state_frames["compact"] = {"compact.png": compact_canvas}

    # Save to states_dir and dist_dir
    for state_name, frames in state_frames.items():
        st_dir = states_dir / state_name
        dt_dir = dist_dir / state_name
        st_dir.mkdir(parents=True, exist_ok=True)
        dt_dir.mkdir(parents=True, exist_ok=True)

        for filename, frame_img in frames.items():
            frame_img.save(st_dir / filename)
            frame_img.save(dt_dir / filename)

    # Standard pi-emote emotes.json
    emotes_json = {
        "idle": {
            "default": "idle.png",
            "blink": "idle_blink.png"
        },
        "think": {
            "default": "think.png",
            "hard": "think_hard.png"
        },
        "talk": {
            "weights": {
                "talk_close.png": 0.15,
                "talk_small.png": 0.30,
                "talk_mid.png": 0.35,
                "talk_wide.png": 0.20
            }
        }
    }

    (dist_dir / "emotes.json").write_text(json.dumps(emotes_json, indent=2), encoding="utf-8")
    print(f"✅ [pi-emote-icm] Emote set compiled with 10 states -> {dist_dir}")
    return dist_dir


def install_emote_set(dist_dir: Path, slug: str, target: str = "user") -> Path:
    """Installs the compiled emote set into the active pi-emote extension directory."""
    if target == "project":
        dest_dir = Path.cwd() / ".pi" / "extensions" / "pi-emote" / "emotes" / slug
    else:
        dest_dir = Path.home() / ".pi" / "agent" / "extensions" / "pi-emote" / "emotes" / slug

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for item in dist_dir.iterdir():
        dest_item = dest_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest_item, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest_item)

    print(f"🚀 [pi-emote-icm] Installed emote set '{slug}' -> {dest_dir}")
    print(f"   Activate in config.json: {{\"emotes\": [{{\"model\": \"*\", \"emote-set\": \"{slug}\"}}]}}")
    return dest_dir


def cmd_build(input_image: str, slug: Optional[str] = None, grid_size: int = 32, install: bool = False, target: str = "user"):
    inp = Path(input_image).resolve()
    if not inp.is_file():
        sys.exit(f"❌ Error: Input image not found: {inp}")

    avatar_slug = slug or inp.stem.lower().replace(" ", "_")
    base_dir = Path.cwd() / "pi-emote-workspaces"
    ws = init_workspace(avatar_slug, base_dir)

    # Stage 1: Concept
    concept_dst = ws / "01_concept" / inp.name
    shutil.copy2(inp, concept_dst)

    # Stage 2: Background removal & Squaring
    raw_img = Image.open(inp)
    nobg_img = auto_remove_background(raw_img)
    squared_img = square_and_center(nobg_img, target_size=128)
    squared_dst = ws / "02_squared_nobg" / "avatar_squared.png"
    squared_img.save(squared_dst)
    print(f"  [02_squared_nobg] Centered & squared -> {squared_dst}")

    # Stage 3: Pixelation (32x32 Grid + Nearest-Neighbor 128x128)
    grid_img, nn_128_img = pixelate_nearest_neighbor(squared_img, grid_size=grid_size, target_size=128)
    grid_dst = ws / "03_pixelated" / f"avatar_{grid_size}x{grid_size}.png"
    nn_dst = ws / "03_pixelated" / "avatar_128x128_nn.png"
    grid_img.save(grid_dst)
    nn_128_img.save(nn_dst)
    print(f"  [03_pixelated] {grid_size}x{grid_size} grid -> {grid_dst}")
    print(f"  [03_pixelated] 128x128 Nearest-Neighbor master -> {nn_dst}")

    # Stage 4: Layer Decomposition
    layers_dir = ws / "04_layers"
    decompose_sprite_layers(nn_128_img, layers_dir)
    print(f"  [04_layers] Decomposed modular sprite layers -> {layers_dir}")

    # Stage 5 & 6: Assembly & Distribution
    states_dir = ws / "05_states"
    dist_dir = ws / "06_dist"
    assemble_emote_set(layers_dir, states_dir, dist_dir)

    if install:
        install_emote_set(dist_dir, avatar_slug, target=target)


def cmd_slice_sheet(
    sheet_path: Path,
    slug: Optional[str] = None,
    grid: str = "2x2",
    install: bool = False,
    target: str = "user",
    gif: bool = False,
) -> Path:
    sheet_img = Image.open(sheet_path).convert("RGBA")
    w, h = sheet_img.size
    avatar_slug = slug or sheet_path.stem.lower().replace(" ", "_").replace("-", "_")
    base_dir = Path.cwd() / "pi-emote-workspaces"
    ws = init_workspace(avatar_slug, base_dir)

    concept_dst = ws / "01_concept" / sheet_path.name
    shutil.copy2(sheet_path, concept_dst)

    if grid == "2x2":
        hw, hh = w // 2, h // 2
        pad = 6
        crops = {
            "idle": (pad, pad, hw - pad, hh - pad),
            "blink": (hw + pad, pad, w - pad, hh - pad),
            "talk_small": (pad, hh + pad, hw - pad, h - pad),
            "talk_wide": (hw + pad, hh + pad, w - pad, h - pad),
        }
    else:
        pw = w // 4
        pad = 6
        crops = {
            "idle": (pad, pad, pw - pad, h - pad),
            "blink": (pw + pad, pad, pw * 2 - pad, h - pad),
            "talk_small": (pw * 2 + pad, pad, pw * 3 - pad, h - pad),
            "talk_wide": (pw * 3 + pad, pad, w - pad, h - pad),
        }

    panels: Dict[str, Image.Image] = {}
    for name, box in crops.items():
        cropped = sheet_img.crop(box)
        nobg = auto_remove_background(cropped)
        sq = square_and_center(nobg, target_size=128)
        panels[name] = sq
        sq.save(ws / "02_squared_nobg" / f"panel_{name}.png")

    p_idle = panels["idle"]
    p_blink = panels["blink"]
    p_small = panels["talk_small"]
    p_wide = panels["talk_wide"]
    p_mid = Image.blend(p_small, p_wide, 0.5)

    dist_dir = ws / "06_dist"
    for state in ["idle", "talk", "hi", "think", "read", "write", "tool", "success", "failure", "compact"]:
        (dist_dir / state).mkdir(parents=True, exist_ok=True)

    p_idle.save(dist_dir / "idle" / "idle.png")
    p_blink.save(dist_dir / "idle" / "idle_blink.png")

    p_idle.save(dist_dir / "talk" / "talk_close.png")
    p_small.save(dist_dir / "talk" / "talk_small.png")
    p_mid.save(dist_dir / "talk" / "talk_mid.png")
    p_wide.save(dist_dir / "talk" / "talk_wide.png")

    p_idle.save(dist_dir / "hi" / "hi.png")
    p_idle.save(dist_dir / "think" / "think.png")
    p_blink.save(dist_dir / "think" / "think_hard.png")
    p_blink.save(dist_dir / "read" / "read.png")
    p_blink.save(dist_dir / "write" / "write.png")
    p_idle.save(dist_dir / "tool" / "tool.png")
    p_wide.save(dist_dir / "success" / "success.png")
    p_blink.save(dist_dir / "failure" / "failure.png")
    p_blink.save(dist_dir / "compact" / "compact.png")

    emotes_cfg = {
        "format": "pi-emote-v1",
        "avatar": avatar_slug,
        "resolution": "128x128",
        "states": {
            "idle": {"frames": ["idle.png"], "blink": "idle_blink.png", "interval": 4000},
            "talk": {"mouths": ["talk_close.png", "talk_small.png", "talk_mid.png", "talk_wide.png"], "speed": 120},
            "hi": {"frames": ["hi.png"]},
            "think": {"frames": ["think.png", "think_hard.png"]},
            "read": {"frames": ["read.png"]},
            "write": {"frames": ["write.png"]},
            "tool": {"frames": ["tool.png"]},
            "success": {"frames": ["success.png"]},
            "failure": {"frames": ["failure.png"]},
            "compact": {"frames": ["compact.png"]},
        }
    }
    with open(dist_dir / "emotes.json", "w", encoding="utf-8") as f:
        json.dump(emotes_cfg, f, indent=2)

    print(f"✅ Sliced and assembled genuine sprite sheet -> {dist_dir}")

    if install:
        install_emote_set(dist_dir, avatar_slug, target=target)
    if gif:
        create_showcase_gif(dist_dir, dist_dir / "showcase.gif", scale=2)

    return dist_dir


def create_showcase_gif(dist_dir: Path, out_path: Path, scale: int = 2) -> Path:
    """Assembles all emote states and talk variations into a single looping showcase GIF."""
    sequence = [
        (dist_dir / "hi" / "hi.png", 600),
        (dist_dir / "idle" / "idle.png", 800),
        (dist_dir / "idle" / "idle_blink.png", 160),
        (dist_dir / "idle" / "idle.png", 600),
        (dist_dir / "talk" / "talk_small.png", 130),
        (dist_dir / "talk" / "talk_mid.png", 130),
        (dist_dir / "talk" / "talk_wide.png", 220),
        (dist_dir / "talk" / "talk_mid.png", 130),
        (dist_dir / "talk" / "talk_small.png", 130),
        (dist_dir / "talk" / "talk_close.png", 300),
        (dist_dir / "think" / "think.png", 600),
        (dist_dir / "think" / "think_hard.png", 700),
        (dist_dir / "read" / "read.png", 700),
        (dist_dir / "write" / "write.png", 700),
        (dist_dir / "tool" / "tool.png", 700),
        (dist_dir / "success" / "success.png", 800),
        (dist_dir / "failure" / "failure.png", 800),
        (dist_dir / "compact" / "compact.png", 700),
        (dist_dir / "idle" / "idle.png", 600),
    ]

    frames = []
    durations = []
    target_dim = 128 * scale

    for p, dur in sequence:
        if p.is_file():
            img = Image.open(p).convert("RGBA")
            if scale != 1:
                img = img.resize((target_dim, target_dim), resample=Image.Resampling.NEAREST)
            p_pixels = img.load()
            for py in range(target_dim):
                for px in range(target_dim):
                    if p_pixels[px, py][3] < 128:
                        p_pixels[px, py] = (0, 0, 0, 0)
            frames.append(img)
            durations.append(dur)

    if not frames:
        sys.exit(f"❌ Error: No emote frames found in {dist_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2
    )
    print(f"🎬 [pi-emote-icm] Created showcase GIF ({len(frames)} frames, {target_dim}x{target_dim}) -> {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="pi-emote-icm — Autonomous ICM Pixel Art Pipeline for pi-emote")
    sub = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. init
    p_init = sub.add_parser("init", help="Initialize a 6-stage ICM workspace")
    p_init.add_argument("slug", help="Avatar slug/name")
    p_init.add_argument("--dir", "-d", default=".", help="Base directory")

    # 2. pixelate
    p_pix = sub.add_parser("pixelate", help="Downsample to pixel grid and upscale via Nearest Neighbor")
    p_pix.add_argument("image", help="Input image path")
    p_pix.add_argument("--grid", "-g", type=int, default=32, help="Grid size (default: 32)")
    p_pix.add_argument("--out", "-o", default="pixel_128.png", help="Output 128x128 PNG")

    # 3. decompose
    p_dec = sub.add_parser("decompose", help="Decompose 128x128 sprite into modular layers")
    p_dec.add_argument("sprite", help="Path to 128x128 sprite PNG")
    p_dec.add_argument("--out-dir", "-o", default="layers", help="Layers output folder")

    # 4. assemble
    p_asm = sub.add_parser("assemble", help="Assemble 10 states and emotes.json from layers")
    p_asm.add_argument("layers_dir", help="Path to layers folder")
    p_asm.add_argument("--states-dir", default="states", help="States output folder")
    p_asm.add_argument("--dist-dir", default="dist", help="Distribution package folder")

    # 5. install
    p_ins = sub.add_parser("install", help="Install compiled emote set into pi-emote")
    p_ins.add_argument("dist_dir", help="Path to compiled dist folder")
    p_ins.add_argument("slug", help="Avatar slug name")
    p_ins.add_argument("--target", choices=["user", "project"], default="user", help="Install target (user or project)")

    # 6. gif
    p_gif = sub.add_parser("gif", help="Create a looping animated showcase GIF across all expressions")
    p_gif.add_argument("dist_dir", help="Path to dist directory containing states")
    p_gif.add_argument("--out", "-o", default="showcase.gif", help="Output GIF file path")
    p_gif.add_argument("--scale", "-s", type=int, default=2, help="Pixel scaling multiplier (default: 2 -> 256x256)")

    # 7. build (all-in-one pipeline)
    p_bld = sub.add_parser("build", help="Run full pipeline from raw image to pi-emote package")
    p_bld.add_argument("image", help="Raw concept image path")
    p_bld.add_argument("--slug", "-s", help="Avatar slug name (default: filename)")
    p_bld.add_argument("--grid", "-g", type=int, default=32, help="Pixel grid density (default: 32)")
    p_bld.add_argument("--install", "-i", action="store_true", help="Automatically install into ~/.pi/agent/extensions/pi-emote/emotes/")
    p_bld.add_argument("--target", choices=["user", "project"], default="user", help="Install target")
    p_bld.add_argument("--gif", action="store_true", help="Generate showcase animated GIF in dist folder")

    # 8. slice-sheet (authentic multi-expression grid)
    p_slc = sub.add_parser("slice-sheet", help="Slice and compile authentic 2x2 or 1x4 expression sprite sheet")
    p_slc.add_argument("sheet", help="Path to expression sprite sheet (PNG/JPG)")
    p_slc.add_argument("--slug", "-s", help="Avatar slug name (default: filename)")
    p_slc.add_argument("--grid", choices=["2x2", "1x4"], default="2x2", help="Sprite sheet layout grid")
    p_slc.add_argument("--install", "-i", action="store_true", help="Install into pi-emote emotes directory")
    p_slc.add_argument("--target", choices=["user", "project"], default="user", help="Install target")
    p_slc.add_argument("--gif", action="store_true", help="Generate showcase animated GIF in dist folder")

    args = parser.parse_args()

    if args.command == "init":
        init_workspace(args.slug, Path(args.dir).resolve())
    elif args.command == "pixelate":
        raw = Image.open(args.image)
        nobg = auto_remove_background(raw)
        sq = square_and_center(nobg, target_size=128)
        _, nn = pixelate_nearest_neighbor(sq, grid_size=args.grid, target_size=128)
        nn.save(args.out)
        print(f"✅ Generated 128x128 Nearest-Neighbor pixel art -> {args.out}")
    elif args.command == "decompose":
        sp = Image.open(args.sprite)
        decompose_sprite_layers(sp, Path(args.out_dir).resolve())
    elif args.command == "assemble":
        assemble_emote_set(Path(args.layers_dir).resolve(), Path(args.states_dir).resolve(), Path(args.dist_dir).resolve())
    elif args.command == "install":
        install_emote_set(Path(args.dist_dir).resolve(), args.slug, target=args.target)
    elif args.command == "gif":
        create_showcase_gif(Path(args.dist_dir).resolve(), Path(args.out).resolve(), scale=args.scale)
    elif args.command == "build":
        cmd_build(args.image, slug=args.slug, grid_size=args.grid, install=args.install, target=args.target)
        if args.gif:
            dist_p = Path.cwd() / "pi-emote-workspaces" / (args.slug or Path(args.image).stem.lower().replace(" ", "_")) / "06_dist"
            create_showcase_gif(dist_p, dist_p / "showcase.gif", scale=2)
    elif args.command == "slice-sheet":
        cmd_slice_sheet(Path(args.sheet).resolve(), slug=args.slug, grid=args.grid, install=args.install, target=args.target, gif=args.gif)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
