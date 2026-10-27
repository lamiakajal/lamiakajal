#!/usr/bin/env python3
"""
Latest Blog Posts: reads your Blogger feed, draws one animated card (SVG) per post into ui-v3/
and rewrites the block between <!-- BLOG:START --> and <!-- BLOG:END --> in README.md.
Write a new post on your blog and it shows up here automatically. Standard library only.
"""
import email.utils
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from html import escape

FEED = os.environ.get("BLOG_FEED", "https://lamiakajal.blogspot.com/feeds/posts/default?alt=rss")
CARD_DIR = "ui-v3"
README = "README.md"
MAX_POSTS = 4
PALETTE = ["#58a6ff", "#7ee787", "#bc8cff", "#ffa657", "#ff7bb0", "#39d0d8"]
NB = "&#160;"
PW, PH, PADB = 440, 176, 5
WRAP, MAX_LINES = 36, 3


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


def clean_title(t):
    t = re.sub(r"[^\u0020-\u007E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2026]", "", t or "")   # emoji / unsupported glyphs
    t = re.sub(r"\s+", " ", t).strip(" |-")
    return t


def wrap(text, width=WRAP, max_lines=MAX_LINES):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if len(trial) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 3].rstrip() + "..."
    return [l[:width] for l in lines] or ["Untitled post"]


def row_text(text, x0, y, cw, cls, fill, extra=""):
    s = text.rstrip()
    lead = len(s) - len(s.lstrip(" "))
    s = s.lstrip(" ")
    if not s:
        return ""
    body = "".join(NB if c == " " else escape(c) for c in s)
    return (f'<text class="{cls}" fill="{fill}" x="{x0 + lead * cw:.1f}" y="{y:.1f}" '
            f'textLength="{len(s) * cw:.1f}" lengthAdjust="spacing"{extra}>{body}</text>')


def fetch_posts():
    req = urllib.request.Request(FEED, headers={"User-Agent": "profile-blog-cards"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    posts = []
    for it in root.findall("./channel/item"):
        title, link = clean_title(it.findtext("title")), (it.findtext("link") or "").strip()
        if not link or not title:                       # posts without a title are skipped
            continue
        date = ""
        try:
            d = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
            date = f"{d.strftime('%b')} {d.day}, {d.year}"
        except Exception:
            pass
        posts.append({"title": title, "link": link, "date": date})
        if len(posts) == MAX_POSTS:
            break
    return posts


def card_svg(idx, p):
    col = PALETTE[idx % len(PALETTE)]
    lines = wrap(p["title"])
    a = 0.4 + idx * 0.5
    t_chip, t_title = a + 0.3, a + 0.6
    t_foot = t_title + len(lines) * 0.3 + 0.2
    T = t_foot + 0.8

    def fade(t):
        return (f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{t / T:.4f};{(t + .35) / T:.4f};1" '
                f'dur="{T:.3f}s" fill="freeze"/>')

    g = [f'<g class="pulse" style="animation-delay:-{(idx * 0.5) % 2.4:.2f}s"><g transform="translate({PADB},{PADB})">',
         f'<g>{fade(a)}<rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14" fill="#161b22" stroke="{col}" stroke-opacity=".6"/></g>',
         f'<g>{fade(t_chip)}<rect x="24" y="20" width="62" height="24" rx="12" fill="{col}" fill-opacity=".14" stroke="{col}" stroke-opacity=".6"/>'
         + row_text("BLOG", 37, 36.5, 7.2, "m", col, ' style="font-size:12px"') + '</g>']
    if p["date"]:
        g.append(f'<g>{fade(t_chip)}' + row_text(p["date"], PW - 24 - len(p["date"]) * 7.2, 36.5, 7.2, "m", "#8b949e", ' style="font-size:12px;font-weight:normal"') + '</g>')
    for i, ln in enumerate(lines):
        g.append(f'<g>{fade(t_title + i * 0.3)}' + row_text(ln, 24, 78 + i * 24, 9.6, "m", "#e6edf3", ' style="font-size:16px"') + '</g>')
    g.append(f'<g>{fade(t_foot)}' + row_text("Read post ->", PW - 24 - 12 * 7.8, PH - 16, 7.8, "m", col, ' style="font-size:13px"') + '</g>')
    g.append('</g></g>')
    w, h = PW + 2 * PADB, PH + 2 * PADB
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(p["title"])}">'
            f'<title>{escape(p["title"])}</title>'
            '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;white-space:pre}.m{font-weight:bold}'
            '.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
            '@keyframes pulse{0%,100%{transform:scale(.95)}50%{transform:scale(1.05)}}</style>' + "".join(g) + '</svg>')


def build(posts):
    os.makedirs(CARD_DIR, exist_ok=True)
    keep, items = set(), []
    for i, p in enumerate(posts):
        fname = f"blog-{i + 1}.svg"
        keep.add(fname)
        with open(os.path.join(CARD_DIR, fname), "w", encoding="utf-8") as f:
            f.write(fx_button(card_svg(i, p)))
        items.append(f'<a href="{escape(p["link"], quote=True)}"><img src="{CARD_DIR}/{fname}" alt="{escape(p["title"], quote=True)}" width="48%" /></a>')
    for fn in os.listdir(CARD_DIR):
        if fn.startswith("blog-") and fn.endswith(".svg") and fn not in keep:
            os.remove(os.path.join(CARD_DIR, fn))
    block = "<!-- BLOG:START -->\n<p align=\"center\">\n" + "\n".join(items) + "\n</p>\n<!-- BLOG:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(r"<!-- BLOG:START -->.*?<!-- BLOG:END -->", re.S)
    if not pattern.search(text):
        print("::warning::README.md has no BLOG:START / BLOG:END block")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(pattern.sub(lambda m: block, text))
    print("blog cards:", [p["title"] for p in posts])


def main():
    try:
        posts = fetch_posts()
    except Exception as e:
        print(f"::warning::could not read the blog feed ({e}); keeping the old cards")
        return
    if not posts:
        print("::warning::no posts found in the feed; keeping the old cards")
        return
    build(posts)


if __name__ == "__main__":
    main()
