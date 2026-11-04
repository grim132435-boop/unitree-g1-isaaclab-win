#!/usr/bin/env python3
"""Draw circles, arrows, wires and labels on real photos / composite sheets.

Two commands:

  grid      Overlay a labelled coordinate grid on a photo so positions can be
            read off precisely before annotating.
              python annotate.py grid photo.jpg photo_grid.png --step 100

  render    Apply a JSON spec of marks to a photo (or to a blank canvas with
            several component photos placed on it) and write a PNG.
              python annotate.py render spec.json out.png

Spec format (all coordinates are pixels in the ORIGINAL image, or 0..1
fractions when "units": "frac"):

{
  "image": "photo.jpg",                 # or omit and use "canvas"
  "canvas": {"w": 1600, "h": 900, "bg": "white"},
  "place": [                            # component photos on the canvas
    {"image": "plc.jpg", "x": 40, "y": 80, "w": 600, "title": "PLC"}
  ],
  "enhance": true,                      # auto-contrast + sharpen phone photos
  "units": "px",
  "title": "X1 단자대 결선",
  "marks": [
    {"type": "circle", "at": [420, 310], "r": 40, "label": "24V+ 여기",
                       "label_pos": "ne"},            # ne|nw|n|s|e|w
    {"type": "box",    "xy": [100, 100, 300, 220], "label": "X1"},
    {"type": "arrow",  "from": [50, 50], "to": [410, 300], "label": "갈색선"},
    {"type": "marker", "at": [600, 200], "n": 1},
    {"type": "wire",   "points": [[620,300],[800,300],[800,500]],
                       "color": "#c00000", "label": "BN 24V", "width": 6},
    {"type": "text",   "at": [30, 30], "text": "메모"}
  ],
  "legend": [{"color": "#8B4513", "text": "BN = +24V"}]
}

Every mark accepts optional "color" (default red) and "width".
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]

DEFAULT_COLOR = "#ff1a1a"


def load_font(size: int) -> ImageFont.ImageFont:
    env = os.environ.get("ANNOTATE_FONT")
    for path in ([env] if env else []) + FONT_CANDIDATES:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def open_photo(path: str | Path, enhance: bool) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")  # phone photos are often rotated via EXIF
    if enhance:
        img = ImageOps.autocontrast(img, cutoff=1)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
        img = ImageEnhance.Color(img).enhance(1.1)
    return img


# ---------------------------------------------------------------- drawing ---

class Painter:
    def __init__(self, img: Image.Image, scale: float = 1.0):
        self.img = img
        self.d = ImageDraw.Draw(img)
        # stroke/label size follows image size so marks stay readable
        self.base = max(2, round(min(img.size) / 250))
        self.font = load_font(max(14, self.base * 9))
        self.small = load_font(max(12, self.base * 7))
        self.scale = scale

    def p(self, pt):
        return (pt[0] * self.scale, pt[1] * self.scale)

    def label(self, xy, text, color=DEFAULT_COLOR, anchor="lb", font=None):
        font = font or self.font
        x, y = xy
        bbox = self.d.textbbox((x, y), text, font=font, anchor=anchor)
        pad = self.base * 2
        box = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
        # keep label on the image
        dx = max(0, -box[0]) - max(0, box[2] - self.img.width)
        dy = max(0, -box[1]) - max(0, box[3] - self.img.height)
        box = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
        self.d.rounded_rectangle(box, radius=pad, fill="white", outline=color, width=max(2, self.base))
        self.d.text((x + dx, y + dy), text, fill=color, font=font, anchor=anchor)

    def circle(self, m):
        c = m.get("color", DEFAULT_COLOR)
        w = m.get("width", self.base * 2)
        cx, cy = self.p(m["at"])
        r = m.get("r", 30) * self.scale
        rx, ry = (r, r) if "rx" not in m else (m["rx"] * self.scale, m["ry"] * self.scale)
        # white halo first so the ring is visible on dark AND light backgrounds
        self.d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline="white", width=w + self.base * 2)
        self.d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=c, width=w)
        if m.get("label"):
            gap = self.base * 3
            pos = {  # where the label sits relative to the ring
                "ne": ((cx + rx * 0.75, cy - ry * 0.75 - gap), "lb"),
                "nw": ((cx - rx * 0.75, cy - ry * 0.75 - gap), "rb"),
                "n": ((cx, cy - ry - gap), "mb"),
                "s": ((cx, cy + ry + gap), "mt"),
                "e": ((cx + rx + gap, cy), "lm"),
                "w": ((cx - rx - gap, cy), "rm"),
            }[m.get("label_pos", "ne")]
            self.label(pos[0], m["label"], c, anchor=pos[1])

    def box(self, m):
        c = m.get("color", DEFAULT_COLOR)
        w = m.get("width", self.base * 2)
        x1, y1 = self.p(m["xy"][:2])
        x2, y2 = self.p(m["xy"][2:])
        self.d.rectangle((x1, y1, x2, y2), outline="white", width=w + self.base * 2)
        self.d.rectangle((x1, y1, x2, y2), outline=c, width=w)
        if m.get("label"):
            self.label((x1, y1 - self.base * 3), m["label"], c)

    def _arrowhead(self, a, b, c, size):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        pts = [b]
        for s in (1, -1):
            pts.append((b[0] - size * math.cos(ang + s * 0.45), b[1] - size * math.sin(ang + s * 0.45)))
        self.d.polygon(pts, fill=c, outline="white")

    def arrow(self, m):
        c = m.get("color", DEFAULT_COLOR)
        w = m.get("width", self.base * 2)
        a, b = self.p(m["from"]), self.p(m["to"])
        self.d.line([a, b], fill="white", width=w + self.base * 2)
        self.d.line([a, b], fill=c, width=w)
        self._arrowhead(a, b, c, w * 5)
        if m.get("label"):
            self.label(a, m["label"], c, anchor="mm")

    def marker(self, m):
        c = m.get("color", DEFAULT_COLOR)
        cx, cy = self.p(m["at"])
        r = m.get("r", self.base * 9)
        self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c, outline="white", width=self.base)
        self.d.text((cx, cy), str(m.get("n", "")), fill="white", font=load_font(int(r * 1.2)), anchor="mm")
        if m.get("label"):
            self.label((cx + r + self.base * 2, cy), m["label"], c, anchor="lm")

    def wire(self, m):
        c = m.get("color", DEFAULT_COLOR)
        w = m.get("width", self.base * 3)
        pts = [self.p(p) for p in m["points"]]
        self.d.line(pts, fill="black", width=w + self.base * 2, joint="curve")
        self.d.line(pts, fill=c, width=w, joint="curve")
        for p in (pts[0], pts[-1]):
            r = w * 1.2
            self.d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=c, outline="black", width=self.base)
        if m.get("label"):
            # label at the midpoint of the longest segment
            seg = max(zip(pts, pts[1:]), key=lambda s: math.dist(*s))
            mid = ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
            self.label(mid, m["label"], c, anchor="mm", font=self.small)
        if m.get("arrow"):
            self._arrowhead(pts[-2], pts[-1], c, w * 4)

    def text(self, m):
        self.label(self.p(m["at"]), m["text"], m.get("color", "black"), anchor="lt")


def draw_title_and_legend(img: Image.Image, title: str | None, legend: list | None) -> Image.Image:
    if not title and not legend:
        return img
    base = max(2, round(min(img.size) / 250))
    tf, lf = load_font(base * 12), load_font(base * 8)
    head = (base * 20 if title else 0)
    rows = len(legend or [])
    foot = (base * 12 * rows + base * 6) if rows else 0
    out = Image.new("RGB", (img.width, img.height + head + foot), "white")
    out.paste(img, (0, head))
    d = ImageDraw.Draw(out)
    if title:
        d.text((base * 6, head // 2), title, fill="black", font=tf, anchor="lm")
    y = img.height + head + base * 4
    for item in legend or []:
        d.line((base * 6, y + base * 4, base * 26, y + base * 4), fill=item.get("color", DEFAULT_COLOR), width=base * 4)
        d.text((base * 32, y + base * 4), item["text"], fill="black", font=lf, anchor="lm")
        y += base * 12
    return out


def render(spec: dict, spec_dir: Path) -> Image.Image:
    enhance = spec.get("enhance", False)
    if "image" in spec:
        img = open_photo(spec_dir / spec["image"], enhance)
    else:
        cv = spec.get("canvas", {"w": 1600, "h": 900})
        img = Image.new("RGB", (cv["w"], cv["h"]), cv.get("bg", "white"))
        p = Painter(img)
        for pl in spec.get("place", []):
            ph = open_photo(spec_dir / pl["image"], enhance)
            if "w" in pl:
                ph = ph.resize((pl["w"], round(ph.height * pl["w"] / ph.width)), Image.LANCZOS)
            img.paste(ph, (pl["x"], pl["y"]))
            p.d.rectangle((pl["x"], pl["y"], pl["x"] + ph.width, pl["y"] + ph.height), outline="#888", width=2)
            if pl.get("title"):
                p.d.text((pl["x"], pl["y"] - 6), pl["title"], fill="black", font=p.font, anchor="lb")

    scale = 1.0
    max_w = spec.get("max_width")
    if max_w and img.width > max_w:
        scale = max_w / img.width
        img = img.resize((max_w, round(img.height * scale)), Image.LANCZOS)

    painter = Painter(img, scale)
    if spec.get("units") == "frac":
        painter.scale = 1.0
        W, H = img.size
        conv = lambda pt: (pt[0] * W, pt[1] * H)  # noqa: E731
        painter.p = conv

    order = {"wire": 0, "box": 1, "circle": 2, "arrow": 3, "marker": 4, "text": 5}
    for m in sorted(spec.get("marks", []), key=lambda m: order.get(m["type"], 9)):
        getattr(painter, m["type"])(m)

    return draw_title_and_legend(img, spec.get("title"), spec.get("legend"))


def grid(src: Path, dst: Path, step: int | None, enhance: bool) -> None:
    img = open_photo(src, enhance)
    step = step or max(50, round(max(img.size) / 12 / 50) * 50)
    d = ImageDraw.Draw(img, "RGBA")
    font = load_font(max(12, step // 5))
    for x in range(0, img.width, step):
        d.line((x, 0, x, img.height), fill=(0, 255, 255, 150), width=1)
        d.text((x + 2, 2), str(x), fill=(255, 255, 0, 255), font=font, stroke_width=2, stroke_fill="black")
    for y in range(0, img.height, step):
        d.line((0, y, img.width, y), fill=(0, 255, 255, 150), width=1)
        d.text((2, y + 2), str(y), fill=(255, 255, 0, 255), font=font, stroke_width=2, stroke_fill="black")
    img.save(dst)
    print(f"{dst}  size={img.width}x{img.height}  step={step}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grid")
    g.add_argument("src")
    g.add_argument("dst")
    g.add_argument("--step", type=int)
    g.add_argument("--enhance", action="store_true")
    r = sub.add_parser("render")
    r.add_argument("spec")
    r.add_argument("dst")
    a = ap.parse_args(argv)

    if a.cmd == "grid":
        grid(Path(a.src), Path(a.dst), a.step, a.enhance)
    else:
        spec_path = Path(a.spec)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        out = render(spec, spec_path.parent)
        out.save(a.dst)
        print(f"{a.dst}  size={out.width}x{out.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
