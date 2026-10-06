#!/usr/bin/env python3
"""
Featured Projects, synced with the repositories you PIN on your GitHub profile.

  * pin / unpin a repo on GitHub  ->  the card appears / disappears (runs every day, or press "Run workflow")
  * card text comes from the repo:  About description, Topics, primary language, Website (= live demo link)
  * projects.json is optional:      "overrides" change a card's text/colour, "extra" adds projects that are not pinned

Writes one animated SVG card per project into ui-v3/ and rewrites the block between
<!-- PROJECTS:START --> and <!-- PROJECTS:END --> in README.md.  Only the Python standard library is used.
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


def _request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-project-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_pins():
    query = """query($login:String!){user(login:$login){pinnedItems(first:6,types:[REPOSITORY]){nodes{
        ... on Repository{name description url homepageUrl primaryLanguage{name}
        repositoryTopics(first:4){nodes{topic{name}}}}}}}}"""
    body = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    res = _request("https://api.github.com/graphql", body)
    if "errors" in res:
        raise RuntimeError(res["errors"])
    projects = []
    for n in res["data"]["user"]["pinnedItems"]["nodes"]:
        if not n:
            continue
        demo = (n.get("homepageUrl") or "").strip()
        if not demo:                                   # no Website set -> use GitHub Pages if the repo has it
            try:
                if _request(f"https://api.github.com/repos/{USER}/{n['name']}").get("has_pages"):
                    demo = f"https://{USER}.github.io/{n['name']}/"
            except Exception:
                pass
        tech = []
        lang = (n.get("primaryLanguage") or {}).get("name")
        if lang:
            tech.append(lang)
        for t in n["repositoryTopics"]["nodes"]:
            nm = t["topic"]["name"]
            if nm.lower() not in [x.lower() for x in tech]:
                tech.append(nm)
        projects.append({"name": n["name"], "description": (n.get("description") or "").strip() or "Add a description in this repository's About box.",
                         "tech": tech[:4] or ["Project"], "demo": demo, "url": n["url"]})
    return projects


def build(projects):
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
            f.write(card_svg(i, p))
        link = p.get("demo") or p.get("url") or "#"
        items.append(f'<a href="{escape(link, quote=True)}"><img src="{CARD_DIR}/{fname}" alt="{escape(p["name"], quote=True)}" width="48%" /></a>')
    for fn in os.listdir(CARD_DIR):                    # remove cards of repos that are no longer pinned
        if fn.startswith("project-") and fn.endswith(".svg") and fn not in keep:
            os.remove(os.path.join(CARD_DIR, fn))
    block = "<!-- PROJECTS:START -->\n<p align=\"center\">\n" + "\n".join(items) + "\n</p>\n<!-- PROJECTS:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(r"<!-- PROJECTS:START -->.*?<!-- PROJECTS:END -->", re.S)
    if not pattern.search(text):
        print("::warning::README.md has no PROJECTS:START / PROJECTS:END block")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(pattern.sub(lambda m: block, text))
    print("project cards:", [p["name"] for p in projects])


def fetch_pinned():
    """Pinned repositories of the profile, in the order shown on GitHub."""
    query = """query($login:String!){user(login:$login){pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{
               name description url homepageUrl primaryLanguage{name} repositoryTopics(first:6){nodes{topic{name}}}}}}}}"""
    body = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-projects"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if "errors" in res:
        raise RuntimeError(res["errors"])
    out = []
    for n in res["data"]["user"]["pinnedItems"]["nodes"]:
        if not n:
            continue
        lang = (n.get("primaryLanguage") or {}).get("name")
        topics = [t["topic"]["name"].replace("-", " ") for t in n["repositoryTopics"]["nodes"]]
        tech, seen = [], set()
        for t in ([lang] if lang else []) + topics:
            if t.lower() not in seen:
                seen.add(t.lower())
                tech.append(t)
        out.append({"name": n["name"], "description": n.get("description") or f"{n['name']} project.",
                    "tech": tech[:5], "url": n["url"], "demo": n.get("homepageUrl") or ""})
    return out


def load_config():
    if not os.path.exists(JSON_FILE):
        return {}, []
    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):                      # old format: a plain list of projects
        return {}, data
    return {k.lower(): v for k, v in data.get("overrides", {}).items()}, data.get("extra", [])


def main():
    overrides, extra = load_config()
    projects = fetch_pinned() if "--no-pins" not in sys.argv else []
    for p in projects:
        for k, v in (overrides.get(p["name"].lower()) or {}).items():
            if v not in (None, "", []):
                p[k] = v
    projects += extra
    if not projects:
        sys.exit("No pinned repositories and no extra projects found - pin some repos on your profile first.")
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
            f.write(card_svg(i, p))
        link = p.get("demo") or p.get("url") or "#"
        items.append(f'<a href="{escape(link, quote=True)}"><img src="{CARD_DIR}/{fname}" alt="{escape(p["name"], quote=True)}" width="48%" /></a>')
    for fn in os.listdir(CARD_DIR):                         # remove cards of projects that are no longer featured
        if fn.startswith("project-") and fn.endswith(".svg") and fn not in keep:
            os.remove(os.path.join(CARD_DIR, fn))
    block = "<!-- PROJECTS:START -->\n<p align=\"center\">\n" + "\n".join(items) + "\n</p>\n<!-- PROJECTS:END -->"
    with open(README, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(r"<!-- PROJECTS:START -->.*?<!-- PROJECTS:END -->", re.S)
    if not pattern.search(text):
        sys.exit("README.md has no <!-- PROJECTS:START --> ... <!-- PROJECTS:END --> block")
    with open(README, "w", encoding="utf-8") as f:
        f.write(pattern.sub(lambda m: block, text))
    print("cards written:", sorted(keep))


if __name__ == "__main__":
    main()
