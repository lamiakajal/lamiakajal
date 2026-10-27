#!/usr/bin/env python3
"""
Featured Projects, synced with the repositories you PIN on your GitHub profile.

  * pin / unpin a repo on GitHub  ->  the card appears / disappears (runs every day, or press "Run workflow")
  * card text comes from the repo:  About description, Topics, primary language, Website (= live demo link)
  * projects.json is optional:      "overrides" change a card's text/colour, "extra" adds projects that are not pinned

Writes one animated SVG card per project into ui-v3/ and rewrites the block between
<!-- PROJECTS:START --> and <!-- PROJECTS:END --> in README.md.  Only the Python standard library is used.
If something goes wrong the log says exactly what (read the red step in the Actions tab).
"""
import json
import os
import re
import sys
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "lamiakajal")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
CARD_DIR = "ui-v3"
README = "README.md"
JSON_FILE = "projects.json"
PALETTE = ["#58a6ff", "#7ee787", "#bc8cff", "#ffa657", "#ff7bb0", "#39d0d8", "#f2cc60"]
NB = "&#160;"
PW, PH, PADB = 440, 216, 5
WRAP = 44                       # characters per description line
MAX_LINES = 4


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


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "project"


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
    return lines


def row_text(text, x0, y, cw, cls, fill, extra=""):
    s = text.rstrip()
    lead = len(s) - len(s.lstrip(" "))
    s = s.lstrip(" ")
    if not s:
        return ""
    body = "".join(NB if c == " " else escape(c) for c in s)
    return (f'<text class="{cls}" fill="{fill}" x="{x0 + lead * cw:.1f}" y="{y:.1f}" '
            f'textLength="{len(s) * cw:.1f}" lengthAdjust="spacing"{extra}>{body}</text>')


def once_clip(cid, x, y, hgt, widths, times, T):
    return (f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{y:.1f}" width="{widths[-1]:.1f}" height="{hgt}">'
            f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in widths)}" '
            f'keyTimes="{";".join(f"{t / T:.4f}" for t in times)}" calcMode="discrete" dur="{T:.3f}s" fill="freeze"/></rect></clipPath>')


def card_svg(idx, p):
    name = p["name"]
    col = p.get("color") or PALETTE[idx % len(PALETTE)]
    lines = wrap(p.get("description", ""))
    chips = [str(c) for c in p.get("tech", [])][:5]
    footer = "Live demo ->" if p.get("demo") else "View project ->"
    a = 0.4 + idx * 0.5
    tdt, ts = 0.08, a + 0.3
    t_desc = ts + len(name) * tdt + 0.2
    t_chip = t_desc + len(lines) * 0.25 + 0.15
    t_foot = t_chip + len(chips) * 0.2 + 0.2
    T = t_foot + 0.8

    def fade(t):
        return (f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{t / T:.4f};{(t + .35) / T:.4f};1" '
                f'dur="{T:.3f}s" fill="freeze"/>')

    nx, cw = 62, 12.0
    shown = name[:22]
    widths = [0.0, 0.0] + [(k + 1) * cw for k in range(len(shown))]
    times = [0.0, ts] + [ts + (k + 1) * tdt for k in range(len(shown))]
    g = [f'<g class="pulse" style="animation-delay:-{(idx * 0.5) % 2.4:.2f}s"><g transform="translate({PADB},{PADB})">',
         f'<g>{fade(a)}<rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14" fill="#161b22" stroke="{col}" stroke-opacity=".6"/>'
         f'<path transform="translate(24,26)" d="M0,4 a3,3 0 0 1 3,-3 h7 l3,3.5 h10 a3,3 0 0 1 3,3 v14 a3,3 0 0 1 -3,3 h-20 a3,3 0 0 1 -3,-3 z" fill="{col}" fill-opacity=".9"/></g>',
         row_text(shown, nx, 46, cw, "n", col, ' clip-path="url(#n)" style="font-size:20px"')]
    for i, ln in enumerate(lines):
        g.append(f'<g>{fade(t_desc + i * 0.25)}' + row_text(ln, 24, 82 + i * 19, 7.8, "m", "#c9d1d9", ' style="font-size:13px;font-weight:normal"') + '</g>')
    cx, cy = 24.0, PH - 62
    for i, ch in enumerate(chips):
        wch = len(ch) * 7.2 + 20
        if cx + wch > PW - 24:
            break
        g.append(f'<g>{fade(t_chip + i * 0.2)}<rect x="{cx:.1f}" y="{cy}" width="{wch:.1f}" height="24" rx="12" fill="{col}" fill-opacity=".14" stroke="{col}" stroke-opacity=".6"/>'
                 + row_text(ch, cx + 10, cy + 16.5, 7.2, "m", col, ' style="font-size:12px;font-weight:bold"') + '</g>')
        cx += wch + 8
    g.append(f'<g>{fade(t_foot)}' + row_text(footer, PW - 24 - len(footer) * 7.8, PH - 18, 7.8, "m", "#58a6ff", ' style="font-size:13px"') + '</g>')
    g.append('</g></g>')
    w, h = PW + 2 * PADB, PH + 2 * PADB
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(name)}">'
            f'<title>{escape(name)}</title>'
            '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;white-space:pre}'
            '.n{font-weight:bold}.m{font-weight:bold}'
            '.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
            '@keyframes pulse{0%,100%{transform:scale(.95)}50%{transform:scale(1.05)}}</style>'
            f'<defs>{once_clip("n", nx, 20, 36, widths, times, T)}</defs>' + "".join(g) + '</svg>')


def http(url, data=None, accept="application/vnd.github+json"):
    headers = {"User-Agent": "Mozilla/5.0 (profile-projects)", "Accept": accept}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def tidy_tech(lang, topics):
    tech, seen = [], set()
    for t in ([lang] if lang else []) + [x.replace("-", " ") for x in topics]:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tech.append(t)
    return tech[:5]


def pinned_graphql():
    query = """query($login:String!){user(login:$login){pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{
               name description url homepageUrl primaryLanguage{name} repositoryTopics(first:6){nodes{topic{name}}}}}}}}"""
    body = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    res = json.loads(http("https://api.github.com/graphql", body))
    if "errors" in res:
        raise RuntimeError(res["errors"])
    out = []
    for n in res["data"]["user"]["pinnedItems"]["nodes"]:
        if not n:
            continue
        lang = (n.get("primaryLanguage") or {}).get("name")
        topics = [t["topic"]["name"] for t in n["repositoryTopics"]["nodes"]]
        out.append({"name": n["name"], "description": n.get("description") or f"{n['name']} project.",
                    "tech": tidy_tech(lang, topics), "url": n["url"], "demo": n.get("homepageUrl") or ""})
    return out


def pinned_from_profile_page():
    """Fallback: read the repo names from your public profile page, then ask the REST API for each repo."""
    page = http(f"https://github.com/{USER}", accept="text/html")
    names = []
    for n in re.findall(r'<span class="repo"[^>]*>\s*([^<\s]+)\s*</span>', page):
        if n not in names:
            names.append(n)
    out = []
    for n in names[:6]:
        r = json.loads(http(f"https://api.github.com/repos/{USER}/{n}"))
        out.append({"name": r["name"], "description": r.get("description") or f"{r['name']} project.",
                    "tech": tidy_tech(r.get("language"), r.get("topics") or []), "url": r["html_url"],
                    "demo": r.get("homepage") or ""})
    return out


def fetch_pinned():
    try:
        found = pinned_graphql()
        print(f"[ok] read {len(found)} pinned repos with the GitHub API:", [p["name"] for p in found])
        if found:
            return found
        print("[warn] the API returned no pinned repos, trying the profile page instead")
    except Exception as e:
        print("[warn] GitHub GraphQL failed:", repr(e)[:500])
        print("[warn] trying the profile page instead")
    found = pinned_from_profile_page()
    print(f"[ok] read {len(found)} pinned repos from the profile page:", [p["name"] for p in found])
    return found


def load_config():
    if not os.path.exists(JSON_FILE):
        print("[info] no projects.json - using the pinned repos as they are")
        return {}, []
    try:
        with open(JSON_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[warn] projects.json has a typo (line {e.lineno}, column {e.colno}: {e.msg}) - ignoring it for now")
        return {}, []
    if isinstance(data, list):                      # old format: a plain list of projects
        return {}, data
    return {k.lower(): v for k, v in data.get("overrides", {}).items()}, data.get("extra", [])


def put_block(text, block):
    pattern = re.compile(r"<!-- PROJECTS:START -->.*?<!-- PROJECTS:END -->", re.S)
    if pattern.search(text):
        return pattern.sub(lambda m: block, text)
    print("[warn] README.md had no PROJECTS markers - adding the section automatically")
    heading = re.search(r'<img src="ui-v3/heading-featured\.svg"[^\n]*\n', text)
    if heading:
        return text[:heading.end()] + "\n" + block + "\n" + text[heading.end():]
    social = text.find('<img src="ui-v3/heading-social.svg"')
    if social >= 0:
        sect = '<img src="ui-v3/heading-featured.svg" alt="Featured Projects" width="100%" />\n\n' + block + "\n\n"
        return text[:social] + sect + text[social:]
    sys.exit("README.md has no Featured Projects heading, no Find Me Online heading and no PROJECTS markers - cannot place the cards")


def main():
    overrides, extra = load_config()
    projects = fetch_pinned() if "--no-pins" not in sys.argv else []
    for p in projects:
        for k, v in (overrides.get(p["name"].lower()) or {}).items():
            if v not in (None, "", []):
                p[k] = v
    projects += extra
    if not projects:
        sys.exit("No pinned repositories found. Pin some repos on your profile (Customize your pins) and run again.")
    os.makedirs(CARD_DIR, exist_ok=True)
    keep, items, used = set(), [], set()
    for i, p in enumerate(projects):
        slug = slugify(p["name"])
        while slug in used:
            slug += "-2"
        used.add(slug)
        fname = f"project-{slug}.svg"
        keep.add(fname)
        with open(os.path.join(CARD_DIR, fname), "w", encoding="utf-8") as f:
            f.write(fx_button(card_svg(i, p)))
        link = p.get("demo") or p.get("url") or "#"
        items.append(f'<a href="{escape(link, quote=True)}"><img src="{CARD_DIR}/{fname}" alt="{escape(p["name"], quote=True)}" width="48%" /></a>')
    for fn in os.listdir(CARD_DIR):                         # remove cards of projects that are no longer featured
        if fn.startswith("project-") and fn.endswith(".svg") and fn not in keep:
            os.remove(os.path.join(CARD_DIR, fn))
    block = "<!-- PROJECTS:START -->\n<p align=\"center\">\n" + "\n".join(items) + "\n</p>\n<!-- PROJECTS:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    with open(README, "w", encoding="utf-8") as f:
        f.write(put_block(text, block))
    print("cards written:", sorted(keep))


if __name__ == "__main__":
    main()
