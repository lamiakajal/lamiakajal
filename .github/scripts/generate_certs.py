#!/usr/bin/env python3
"""
Certifications section: reads certificates.json, draws one animated card (SVG) per certificate into ui-v3/
and rewrites the block between <!-- CERTS:START --> and <!-- CERTS:END --> in README.md.
No certificates in the file  ->  the section stays empty (nothing is shown).
Each entry:  {"title": "...", "issuer": "...", "year": "2025", "url": "https://...", "color": "#58a6ff"}   (year, url, color are optional)
Only the Python standard library is used.
"""
import json
import math
import os
import re
import sys
from html import escape

CARD_DIR, README, JSON_FILE = "ui-v3", "README.md", "certificates.json"
PALETTE = ["#58a6ff", "#7ee787", "#bc8cff", "#ffa657", "#ff7bb0", "#39d0d8", "#f2cc60"]
NB = "&#160;"
PW, PH, PADB = 440, 168, 5
T = 14.0


def row_text(text, x0, y, cw, fill, size, weight="bold"):
    s = text.rstrip()
    lead = len(s) - len(s.lstrip(" "))
    s = s.lstrip(" ")
    if not s:
        return ""
    body = "".join(NB if c == " " else escape(c) for c in s)
    return (f'<text fill="{fill}" x="{x0 + lead * cw:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'textLength="{len(s) * cw:.1f}" lengthAdjust="spacing">{body}</text>')


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


def fade(t0, t1=0.4):
    return (f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{t0 / T:.4f};{(t0 + t1) / T:.4f};1" '
            f'dur="{T}s" repeatCount="indefinite"/>')


def card_svg(idx, c):
    col = c.get("color") or PALETTE[idx % len(PALETTE)]
    title_lines = wrap(c["title"], 28, 2)
    issuer = c.get("issuer", "")[:44]
    year = str(c.get("year", ""))
    a = 0.4 + idx * 0.3
    cw, tdt = 9.6, 0.06
    defs, g = [], []
    t = a + 0.4
    for i, ln in enumerate(title_lines):
        wv = [0.0, 0.0] + [(k + 1) * cw for k in range(len(ln))]
        tv = [0.0, t / T] + [(t + (k + 1) * tdt) / T for k in range(len(ln))]
        defs.append(f'<clipPath id="t{i}"><rect x="84" y="{34 + i * 24}" width="{len(ln) * cw:.1f}" height="26">'
                    f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in wv)}" '
                    f'keyTimes="{";".join(f"{x:.4f}" for x in tv)}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></rect></clipPath>')
        g.append(f'<g clip-path="url(#t{i})">' + row_text(ln, 84, 54 + i * 24, cw, "#e6edf3", 16) + "</g>")
        t += len(ln) * tdt + 0.15
    y_issuer = 54 + len(title_lines) * 24 + 8
    g.append(f'<g>{fade(t)}' + row_text(issuer, 84, y_issuer, 7.8, "#c9d1d9", 13, "normal") + "</g>")
    fy = PH - 34
    if year:
        wy = len(year) * 7.8 + 24
        g.append(f'<g>{fade(t + 0.3)}<rect x="24" y="{fy}" width="{wy:.1f}" height="24" rx="12" fill="{col}" fill-opacity=".15" stroke="{col}" stroke-opacity=".7"/>'
                 + row_text(year, 36, fy + 16.5, 7.8, col, 13) + "</g>")
    if c.get("url"):
        label = "Verify ->"
        g.append(f'<g>{fade(t + 0.5)}' + row_text(label, PW - 24 - len(label) * 7.8, PH - 16, 7.8, "#58a6ff", 13) + "</g>")
    medal = (f'<g transform="translate(24,26)"><path d="M12 30 L5 50 L16 44 L21 52 L25 32 Z" fill="{col}" fill-opacity=".75"/>'
             f'<path d="M36 30 L43 50 L32 44 L27 52 L23 32 Z" fill="{col}" fill-opacity=".55"/>'
             f'<circle cx="24" cy="20" r="18" fill="{col}" fill-opacity=".16" stroke="{col}" stroke-width="3"/>'
             f'<polygon points="{star(24, 20, 9, 4)}" fill="{col}"><animate attributeName="opacity" values="1;.55;1" dur="2.4s" repeatCount="indefinite"/></polygon></g>')
    shimmer = (f'<rect x="-140" y="0" width="90" height="{PH}" fill="#ffffff" fill-opacity=".10" transform="skewX(-20)" clip-path="url(#card)">'
               f'<animate attributeName="x" values="-140;-140;{PW + 80};{PW + 80}" keyTimes="0;{(a + 3.5) / T:.4f};{(a + 5.2) / T:.4f};1" dur="{T}s" repeatCount="indefinite"/></rect>')
    defs.append(f'<clipPath id="card"><rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14"/></clipPath>')
    inner = (f'<rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14" fill="#161b22" stroke="{col}" stroke-opacity=".6"/>'
             + medal + "".join(g) + shimmer)
    w, h = PW + 2 * PADB, PH + 2 * PADB
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(c["title"])}">'
            f'<title>{escape(c["title"])}</title>'
            '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;white-space:pre}'
            '.pulse{animation:pulse 2.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
            '@keyframes pulse{0%,100%{transform:scale(.97)}50%{transform:scale(1.03)}}</style>'
            f'<defs>{"".join(defs)}</defs>'
            f'<g class="pulse" style="animation-delay:-{(idx * 0.5) % 2.6:.2f}s"><g transform="translate({PADB},{PADB})">'
            f'<g><animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.03;0.92;0.97;1" dur="{T}s" repeatCount="indefinite"/>{inner}</g></g></g></svg>')


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
            f.write(card_svg(i, c))
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
