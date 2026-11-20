#!/usr/bin/env python3
"""Собрать «фильм» для кинематографичного героя и нарезать его на кадры WebP.

Сейчас: бесплатная версия из готовых фото (наезд камеры + панорама + наплыв).
Потом: тот же конвейер для ИИ-видео (Kling / Higgsfield / Veo) —
    python3 build_frames.py --video hero.mp4
кадры из ролика вырезаются через ffmpeg, страница не меняется.

Запуск из корня репозитория:  python3 cinematic/build_frames.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess

from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames")
W, H = 1280, 720
QUALITY = 62

# (файл, кадров, начальный зум, конечный зум, сдвиг x от→до, сдвиг y от→до), сдвиги в долях
SHOTS = [
    ("../concierge/img/speedboat.jpg", 60, 1.00, 1.35, (0.00, 0.10), (0.05, 0.00)),
    ("../concierge/img/excursions.jpg", 60, 1.25, 1.05, (0.25, -0.15), (0.00, -0.05)),
    ("../concierge/img/massage.jpg", 60, 1.05, 1.30, (-0.05, 0.12), (0.00, 0.02)),
]
FADE = 14  # кадров наплыва между планами


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def render(img: Image.Image, zoom: float, dx: float, dy: float) -> Image.Image:
    """Кадр 16:9 «cover» с зумом и сдвигом (как камера над фото)."""
    iw, ih = img.size
    base = max(W / iw, H / ih)
    s = base * zoom
    cw, ch = W / s, H / s                     # размер окна в пикселях исходника
    cx = iw / 2 + dx * (iw - cw) / 2
    cy = ih / 2 + dy * (ih - ch) / 2
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return img.transform((W, H), Image.Transform.EXTENT, box, Image.Resampling.BICUBIC)


def shot_frames(path: str, n: int, z0: float, z1: float, xs, ys) -> list[Image.Image]:
    img = Image.open(os.path.join(HERE, path)).convert("RGB")
    out = []
    for i in range(n):
        t = ease(i / (n - 1))
        out.append(render(img, z0 + (z1 - z0) * t, xs[0] + (xs[1] - xs[0]) * t,
                          ys[0] + (ys[1] - ys[0]) * t))
    return out


def from_photos() -> list[Image.Image]:
    film: list[Image.Image] = []
    for k, spec in enumerate(SHOTS):
        frames = shot_frames(*spec)
        if film:  # наплыв: хвост прошлого плана смешиваем с началом нового
            tail = film[-FADE:]
            del film[-FADE:]
            for j in range(FADE):
                a = ease((j + 1) / (FADE + 1))
                film.append(Image.blend(tail[j], frames[j], a))
            frames = frames[FADE:]
        film.extend(frames)
    # лёгкое затемнение к концу — под финальную надпись
    n = len(film)
    for i in range(int(n * 0.85), n):
        k = 1 - 0.35 * (i - n * 0.85) / (n * 0.15)
        film[i] = ImageEnhance.Brightness(film[i]).enhance(k)
    return film


def from_video(video: str, fps: int) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video, "-vf",
                    f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                    "-c:v", "libwebp", "-quality", str(QUALITY), os.path.join(OUT, "f_%03d.webp")],
                   check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", help="ИИ-ролик (mp4) вместо фото")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, "f_*.webp")):
        os.remove(f)
    if a.video:
        from_video(a.video, a.fps)
        names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(OUT, "f_*.webp")))
        # ffmpeg нумерует с 1 — переименуем с 0 для единообразия
        for i, nm in enumerate(names):
            os.rename(os.path.join(OUT, nm), os.path.join(OUT, f"_tmp_{i:03d}.webp"))
        for i in range(len(names)):
            os.rename(os.path.join(OUT, f"_tmp_{i:03d}.webp"), os.path.join(OUT, f"f_{i:03d}.webp"))
        count = len(names)
    else:
        film = from_photos()
        for i, fr in enumerate(film):
            fr.save(os.path.join(OUT, f"f_{i:03d}.webp"), "WEBP", quality=QUALITY, method=6)
        count = len(film)
    size = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, "f_*.webp")))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({"count": count, "width": W, "height": H}, f)
    print(f"{count} кадров, {size / 1e6:.1f} МБ → {OUT}")


if __name__ == "__main__":
    main()
