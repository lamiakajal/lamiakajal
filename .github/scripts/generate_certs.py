#!/usr/bin/env python3
"""
Certifications section: reads certificates.json, draws one animated card (SVG) per certificate into ui-v3/
and rewrites the block between <!-- CERTS:START --> and <!-- CERTS:END --> in README.md.
No certificates in the file  ->  the section stays empty (nothing is shown).
Each entry:
  {"title": "...", "issuer": "...", "year": "2025", "note": "...", "image": "certificates/file.jpg",
   "url": "https://...", "link_label": "View ->", "color": "#58a6ff"}
  (only "title" is required; "image" = picture of the certificate inside your repo, shown as a small tilted preview;
   "url" makes the whole card clickable)
"""
import re
# ---- shared card effects (embedded in the generator scripts) -------------------------------------------
import random as _random
import re as _re
import zlib as _zlib


def fx_stars(svg, seed=None, aurora=False):
    """twinkling sparkle background (+ optional soft aurora) inside a full-width dark card; idempotent"""
    if "fxbl" in svg:
        return svg
    m = _re.search(r'<rect x="\.5" y="\.5" width="([\d.]+)" height="([\d.]+)" rx="(\d+)" fill="#0d1117"[^>]*/>', svg)
    if not m:
        return svg
    w, h, rx = float(m.group(1)) + 1, float(m.group(2)) + 1, m.group(3)
    rnd = _random.Random(seed if seed is not None else _zlib.crc32(svg[:400].encode()))
    n = max(10, min(40, int(w * h / 9500)))
    pal = ["#ffffff", "#ffffff", "#bcd4ff", "#ffd9ec", "#d6ffe1", "#fff3b0", "#d9c8ff"]
    defs = (f'<filter id="fxbl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"/></filter>'
            f'<clipPath id="fxcard"><rect x="1" y="1" width="{w-2:.1f}" height="{h-2:.1f}" rx="{rx}"/></clipPath>'
            '<linearGradient id="fxshoot" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".95"/></linearGradient>')
    g = ['<g clip-path="url(#fxcard)">']
    if aurora:
        for i, col in enumerate(("#58a6ff", "#bc8cff", "#ff7bb0")):
            cx, cy = rnd.uniform(0.15, 0.85) * w, rnd.uniform(0.2, 0.8) * h
            r = rnd.uniform(0.16, 0.26) * w
            g.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{col}" opacity=".13" filter="url(#fxbl)">'
                     f'<animateTransform attributeName="transform" type="translate" values="0 0;{rnd.randint(-90,90)} {rnd.randint(-40,40)};0 0" dur="{rnd.uniform(14,22):.1f}s" repeatCount="indefinite"/>'
                     f'<animate attributeName="opacity" values=".08;.2;.08" dur="{rnd.uniform(7,11):.1f}s" repeatCount="indefinite"/></circle>')
    for i in range(n):
        x, y = rnd.uniform(14, w - 14), rnd.uniform(10, h - 10)
        col = rnd.choice(pal); dur = rnd.uniform(1.8, 4.6); beg = rnd.uniform(0, 4)
        if rnd.random() < 0.38:                                    # four-point sparkle
            r = rnd.choice([3.2, 4.2, 5.4, 6.8]); k = 0.28
            d = f"M0,{-r} L{r*k:.2f},{-r*k:.2f} L{r},0 L{r*k:.2f},{r*k:.2f} L0,{r} L{-r*k:.2f},{r*k:.2f} L{-r},0 L{-r*k:.2f},{-r*k:.2f} Z"
            g.append(f'<g transform="translate({x:.0f},{y:.0f})"><path d="{d}" fill="{col}" opacity=".2">'
                     f'<animate attributeName="opacity" values=".12;.95;.12" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/>'
                     f'<animateTransform attributeName="transform" type="scale" values=".5;1.15;.5" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></path></g>')
        else:
            g.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.choice([1.1, 1.5, 2.0])}" fill="{col}" opacity=".2">'
                     f'<animate attributeName="opacity" values=".1;.9;.1" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></circle>')
    for i in range(2):                                              # rare shooting stars
        sx, sy = rnd.uniform(0.1, 0.7) * w, rnd.uniform(0.05, 0.5) * h; D = rnd.uniform(9, 15)
        g.append(f'<g transform="translate({sx:.0f},{sy:.0f}) rotate(24)"><rect x="-46" y="-1" width="46" height="2" rx="1" fill="url(#fxshoot)" opacity="0">'
                 f'<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;0.02;0.09;1" dur="{D:.1f}s" begin="{rnd.uniform(1, 8):.1f}s" repeatCount="indefinite"/>'
                 f'<animateTransform attributeName="transform" type="translate" values="0 0;170 0;170 0" keyTimes="0;0.09;1" dur="{D:.1f}s" begin="{rnd.uniform(1, 8):.1f}s" repeatCount="indefinite"/></rect></g>')
    g.append("</g>")
    svg = svg.replace(m.group(0), m.group(0) + "".join(g), 1)
    return svg.replace("</defs>", defs + "</defs>", 1) if "</defs>" in svg else svg


def fx_button(svg, delay=None):
    """card/button effect: gentle float (never overlaps neighbours) + breathing glow + light sweep"""
    if 'id="fxg"' in svg:
        return svg
    m = _re.search(r'<rect x="1" y="1" width="([\d.]+)" height="([\d.]+)" rx="(\d+)" fill="#161b22" stroke="(#[0-9a-fA-F]{3,8})" stroke-opacity="[.\d]+"/>', svg)
    svg = _re.sub(r'\.pulse\{animation:pulse[^}]*\}\s*@keyframes pulse\{\s*0%,100%\{[^}]*\}\s*50%\{[^}]*\}\s*\}',
                  '.pulse{animation:fxfloat 3.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
                  '@keyframes fxfloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-2.5px)}}', svg)
    if not m:
        return svg
    w, h, rx, col = m.group(1), m.group(2), m.group(3), m.group(4)
    d = (_zlib.crc32(svg[:300].encode()) % 400) / 100 if delay is None else delay
    defs = ('<filter id="fxg" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="3.2"/></filter>'
            f'<clipPath id="fxcl"><rect x="1" y="1" width="{w}" height="{h}" rx="{rx}"/></clipPath>'
            '<linearGradient id="fxs" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".5" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    glow = (f'<rect x="1" y="1" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{col}" stroke-width="3" filter="url(#fxg)" opacity=".15">'
            f'<animate attributeName="opacity" values=".1;.5;.1" dur="3.8s" begin="{d:.2f}s" repeatCount="indefinite"/></rect>')
    sweep = (f'<rect x="-80" y="1" width="46" height="{h}" fill="url(#fxs)" clip-path="url(#fxcl)" transform="skewX(-18)">'
             f'<animate attributeName="x" values="-80;-80;{float(w)+60:.0f};{float(w)+60:.0f}" keyTimes="0;0.15;0.4;1" dur="7s" begin="{d:.2f}s" repeatCount="indefinite"/></rect>')
    svg = svg.replace(m.group(0), glow + m.group(0) + sweep, 1)
    return svg.replace("</defs>", defs + "</defs>", 1) if "</defs>" in svg else svg


import base64
import io
import json
import math
import os
import sys
from html import escape

CARD_DIR, README, JSON_FILE = "ui-v3", "README.md", "certificates.json"
PALETTE = ["#58a6ff", "#7ee787", "#bc8cff", "#ffa657", "#ff7bb0", "#39d0d8", "#f2cc60"]
NB = "&#160;"
PW, PH, PADB = 440, 196, 5
T = 14.0
TX = 196                                   # left edge of the text column


def thumb_uri(path):
    """small JPEG data-URI of the certificate picture (needs Pillow for resizing; falls back to the file itself if it is small)"""
    if not path or not os.path.exists(path):
        return None
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((520, 390))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=78, optimize=True)
        data = buf.getvalue()
    except Exception:
        data = open(path, "rb").read()
        if len(data) > 160_000:
            return None
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def wrap(text, width, max_lines):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if len(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 3].rstrip() + "..."
    return lines


def star(cx, cy, ro, ri):
    pts = []
    for i in range(10):
        r = ro if i % 2 == 0 else ri
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


def kts(xs):
    return ";".join(f"{min(1.0, max(0.0, x)):.4f}" for x in xs)


def card_svg(idx, c, uri):
    col = c.get("color") or PALETTE[idx % len(PALETTE)]
    a = 0.4 + idx * 0.25
    defs, g = [], []
    cw_t, size_t = 9.6, 16

    def typed(txt, x, y, size, fill, t0, weight="bold", dt=0.045, cid=None):
        n = len(txt)
        cw = size * 0.6
        end = T - 0.5
        if t0 + n * dt > end - 0.1:
            dt = max(0.008, (end - 0.1 - t0) / n)
        widths = [0.0] + [(k + 1) * cw for k in range(n)] + [0.0]
        times = [0.0] + [t0 + (k + 1) * dt for k in range(n)] + [end]
        defs.append(f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y - size:.1f}" width="{n * cw:.1f}" height="{size * 1.5:.1f}">'
                    f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in widths)}" keyTimes="{kts([t / T for t in times])}" '
                    f'calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></rect></clipPath>')
        body = "".join(NB if ch == " " else escape(ch) for ch in txt)
        return (f'<g clip-path="url(#{cid})"><text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                f'textLength="{n * cw:.1f}" lengthAdjust="spacing">{body}</text></g>', t0 + n * dt)

    t = a + 0.4
    for i, ln in enumerate(wrap(c["title"], 22, 2)):
        m, t_end = typed(ln, TX, 52 + i * 24, size_t, "#e6edf3", t, cid=f"t{i}")
        g.append(m)
        t = t_end + 0.12
    n_title = len(wrap(c["title"], 22, 2))
    y = 52 + (n_title - 1) * 24 + 26
    if c.get("issuer"):
        m, t_end = typed(str(c["issuer"])[:28], TX, y, 13, col, t, cid="is", dt=0.04)
        g.append(m)
        t = t_end + 0.1
        y += 20
    if c.get("note"):
        m, t_end = typed(str(c["note"])[:30], TX, y, 11, "#8b949e", t, "normal", 0.035, "nt")
        g.append(m)
        t = t_end + 0.1
    fy = PH - 40
    if c.get("year"):
        yr = str(c["year"])
        wy = len(yr) * 7.8 + 24
        m, _ = typed(yr, TX + 12, fy + 16.5, 13, col, t, cid="yr")
        g.append(f'<rect x="{TX}" y="{fy}" width="{wy:.1f}" height="24" rx="12" fill="{col}" fill-opacity=".15" stroke="{col}" stroke-opacity=".7">'
                 f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kts([0, t / T, (t + .3) / T, (T - 1) / T, (T - 0.5) / T, 1])}" dur="{T}s" repeatCount="indefinite"/></rect>' + m)
    if c.get("url"):
        label = str(c.get("link_label") or "View ->")[:14]
        m, _ = typed(label, PW - 24 - len(label) * 7.8, PH - 18, 13, "#58a6ff", t + 0.3, cid="vw")
        g.append(m)
    # ---- left side: the certificate itself (or a medal when there is no picture)
    if uri:
        tw, th = 156, 117
        tx0, ty0 = 20, 30
        defs.append(f'<clipPath id="th"><rect x="{tx0}" y="{ty0}" width="{tw}" height="{th}" rx="8"/></clipPath>')
        left = (f'<g transform="rotate(-3 {tx0 + tw / 2} {ty0 + th / 2})">'
                f'<rect x="{tx0 - 3}" y="{ty0 - 3}" width="{tw + 6}" height="{th + 6}" rx="10" fill="{col}" fill-opacity=".25"/>'
                f'<image href="{uri}" x="{tx0}" y="{ty0}" width="{tw}" height="{th}" preserveAspectRatio="xMidYMid slice" clip-path="url(#th)"/>'
                f'<rect x="{tx0}" y="{ty0}" width="{tw}" height="{th}" rx="8" fill="none" stroke="#ffffff" stroke-opacity=".55" stroke-width="1.5"/>'
                f'<rect x="-60" y="{ty0}" width="34" height="{th}" fill="url(#fxs)" clip-path="url(#th)" transform="skewX(-16)">'
                f'<animate attributeName="x" values="-60;-60;{tx0 + tw + 70};{tx0 + tw + 70}" keyTimes="0;0.25;0.45;1" dur="{T}s" repeatCount="indefinite"/></rect></g>'
                f'<g transform="translate({tx0 + tw - 12},{ty0 + th + 6})"><circle r="13" fill="{col}"/>'
                f'<polygon points="{star(0, 0, 8, 3.6)}" fill="#0d1117"/></g>')
    else:
        left = (f'<g transform="translate(40,44)"><path d="M12 38 L4 62 L18 55 L24 66 L29 40 Z" fill="{col}" fill-opacity=".75"/>'
                f'<path d="M44 38 L52 62 L38 55 L32 66 L27 40 Z" fill="{col}" fill-opacity=".55"/>'
                f'<circle cx="28" cy="26" r="24" fill="{col}" fill-opacity=".16" stroke="{col}" stroke-width="3"/>'
                f'<polygon points="{star(28, 26, 12, 5.2)}" fill="{col}"><animate attributeName="opacity" values="1;.55;1" dur="2.4s" repeatCount="indefinite"/></polygon></g>')
    inner = (f'<rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14" fill="#161b22" stroke="{col}" stroke-opacity=".6"/>' + left + "".join(g))
    w, h = PW + 2 * PADB, PH + 2 * PADB
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(c["title"])}">'
            f'<title>{escape(c["title"])}</title>'
            '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;white-space:pre}'
            '.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
            '@keyframes pulse{0%,100%{transform:scale(.95)}50%{transform:scale(1.05)}}</style>'
            f'<defs>{"".join(defs)}</defs>'
            f'<g class="pulse" style="animation-delay:-{(idx * 0.5) % 2.4:.2f}s"><g transform="translate({PADB},{PADB})">{inner}</g></g></svg>')


def main():
    certs = []
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, encoding="utf-8") as f:
                certs = [c for c in json.load(f) if isinstance(c, dict) and c.get("title")]
        except json.JSONDecodeError as e:
            sys.exit(f"certificates.json has a typo (line {e.lineno}, column {e.colno}: {e.msg}) - fix it and run again")
    os.makedirs(CARD_DIR, exist_ok=True)
    keep, items = set(), []
    for i, c in enumerate(certs):
        fname = f"cert-{i + 1}.svg"
        keep.add(fname)
        with open(os.path.join(CARD_DIR, fname), "w", encoding="utf-8") as f:
            f.write(fx_button(card_svg(i, c, thumb_uri(c.get("image")))))
        img = f'<img src="{CARD_DIR}/{fname}" alt="{escape(c["title"], quote=True)}" width="48%" />'
        items.append(f'<a href="{escape(c["url"], quote=True)}">{img}</a>' if c.get("url") else img)
    for fn in os.listdir(CARD_DIR):
        if fn.startswith("cert-") and fn.endswith(".svg") and fn not in keep:
            os.remove(os.path.join(CARD_DIR, fn))
    if items:
        block = ("<!-- CERTS:START -->\n" + f'<img src="{CARD_DIR}/heading-certs.svg" alt="Certifications" width="100%" />\n\n'
                 '<p align="center">\n' + "\n".join(items) + "\n</p>\n<!-- CERTS:END -->")
    else:
        block = "<!-- CERTS:START -->\n<!-- CERTS:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(r"<!-- CERTS:START -->.*?<!-- CERTS:END -->", re.S)
    if not pattern.search(text):
        print("[warn] README.md has no <!-- CERTS:START --> ... <!-- CERTS:END --> block - nothing to update")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(pattern.sub(lambda m: block, text))
    print(f"certificates: {len(items)} card(s) written")


if __name__ == "__main__":
    main()
