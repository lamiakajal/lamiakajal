#!/usr/bin/env python3
"""
Builds three animated profile cards as SVG files in ./stats :
  github-stats.svg      stars / repos / followers / contributions
  github-streak.svg     total contributions, current streak, longest streak
  github-languages.svg  most used languages
Runs inside GitHub Actions (see .github/workflows/stats.yml). Uses only the Python standard library.
"""
import datetime
import json
import os
import sys
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "lamiakajal")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = "stats"
PLACEHOLDER = "--placeholder" in sys.argv          # draws empty cards ("-" everywhere)

LANG_COLORS = {
    "HTML": "#e34c26", "CSS": "#8957e5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "Java": "#b07219", "C": "#8b8b8b", "C++": "#f34b7d", "C#": "#178600", "PHP": "#4F5D95", "Shell": "#89e051",
    "SCSS": "#c6538c", "Vue": "#41b883", "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Go": "#00ADD8", "Rust": "#dea584",
    "Jupyter Notebook": "#DA5B0B", "Dockerfile": "#384d54", "EJS": "#a91e50", "Svelte": "#ff3e00", "MDX": "#fcb32c",
}
FALLBACK = ["#58a6ff", "#bc8cff", "#ff7bb0", "#7ee787", "#ffa657", "#39d0d8", "#f2cc60"]


# ----------------------------------------------------------------------------- GitHub API
def _request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rest(url):
    return _request(url)


def graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    res = _request("https://api.github.com/graphql", body)
    if "errors" in res:
        raise RuntimeError(res["errors"])
    return res["data"]


def fetch_data():
    user = rest(f"https://api.github.com/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = rest(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r.get("fork")]
    data = {
        "repos": user.get("public_repos", len(repos)),
        "followers": user.get("followers", 0),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "total": None, "current": None, "longest": None, "langs": {},
        "weekday": None, "weeks": None, "repo_langs": {},
    }
    # languages (bytes per language over every own repo)
    langs = {}
    for r in own:
        try:
            for k, v in rest(r["languages_url"]).items():
                langs[k] = langs.get(k, 0) + v
        except Exception as e:                                   # one broken repo must not stop the run
            print("language lookup failed for", r.get("name"), e, file=sys.stderr)
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
    data["langs"] = langs
    rl = {}
    for r in own:
        if r.get("language"):
            rl[r["language"]] = rl.get(r["language"], 0) + 1
    data["repo_langs"] = rl
    # contributions + streaks
    try:
        q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
               totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        cal = graphql(q, {"login": USER})["user"]["contributionsCollection"]["contributionCalendar"]
        days = [(datetime.date.fromisoformat(d["date"]), d["contributionCount"])
                for w in cal["weeks"] for d in w["contributionDays"]]
        data["total"] = cal["totalContributions"]
        wd = [0] * 7                                          # Mon..Sun
        for d, c in days:
            wd[d.weekday()] += c
        data["weekday"] = wd
        grid = [[x["contributionCount"] for x in w["contributionDays"]] for w in cal["weeks"]][-26:]
        data["weeks"] = [w + [None] * (7 - len(w)) for w in grid]       # Sunday..Saturday, like GitHub
        data["current"], data["longest"] = streaks(days, datetime.date.today())
    except Exception as e:
        print("contribution lookup failed:", e, file=sys.stderr)
    return data


def streaks(days, today):
    """days: chronological list of (date, count). returns ((length,start,end) current, (length,start,end) longest)"""
    best = (0, None, None)
    run, start = 0, None
    for d, c in days:
        if c > 0:
            if run == 0:
                start = d
            run += 1
            if run > best[0]:
                best = (run, start, d)
        else:
            run = 0
    i = len(days) - 1
    while i >= 0 and days[i][0] > today:
        i -= 1
    if i >= 0 and days[i][1] == 0 and days[i][0] == today:       # today not finished yet -> do not break the streak
        i -= 1
    end, j = (days[i][0] if i >= 0 else None), i
    while j >= 0 and days[j][1] > 0:
        j -= 1
    length = i - j
    cur = (length, days[j + 1][0] if length else None, end if length else None)
    return cur, best


# ----------------------------------------------------------------------------- SVG helpers
def fmt(n):
    return "-" if n is None else f"{n:,}"


def fmt_range(a, b):
    if not a or not b:
        return " "
    f = lambda d: f"{d.strftime('%b')} {d.day}"
    return f(a) if a == b else f"{f(a)} - {f(b)}"


def head(w, h, title, T=6.0):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f'<title>{escape(title)}</title>'
        '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace}'
        '.t{font-size:20px;font-weight:bold}.lb{font-size:15px;fill:#c9d1d9}.vl{font-size:18px;font-weight:bold}'
        '.sm{font-size:12px;fill:#8b949e}.mid{font-size:13px;fill:#c9d1d9}</style>'
        '<defs>'
        f'<linearGradient id="rb" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{w}" y2="0" spreadMethod="repeat">'
        '<stop offset="0" stop-color="#ff5f6d"/><stop offset=".2" stop-color="#ffc371"/><stop offset=".4" stop-color="#7ee787"/>'
        '<stop offset=".6" stop-color="#58a6ff"/><stop offset=".8" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff5f6d"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="{w} 0" dur="7s" repeatCount="indefinite"/></linearGradient>'
        '<linearGradient id="bd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#58a6ff"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff7bb0"/></linearGradient>'
        '<linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#58a6ff"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff7bb0"/></linearGradient>'
        '</defs>'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="#0d1117" stroke="url(#bd)" stroke-width="1.5"/>'
    )


def fade(t, T=6.0):
    """element appears once at time t and stays"""
    return (f'<animate attributeName="opacity" values="0;0;1;1" keyTimes="0;{t/T:.4f};{(t+.45)/T:.4f};1" '
            f'dur="{T}s" fill="freeze"/>')


# ----------------------------------------------------------------------------- the three cards
def card_stats(d):
    w, h = 490, 230
    rows = [("Total Stars", d["stars"], "#f2cc60"), ("Public Repos", d["repos"], "#58a6ff"),
            ("Followers", d["followers"], "#bc8cff"), ("Contributions (1y)", d["total"], "#7ee787")]
    s = [head(w, h, "GitHub Stats"), f'<text class="t" x="28" y="42" fill="url(#rb)">GitHub Stats</text>']
    for i, (label, val, col) in enumerate(rows):
        y = 90 + i * 36
        s.append(f'<g>{fade(0.3 + i * 0.35)}<circle cx="36" cy="{y-5}" r="5" fill="{col}"/>'
                 f'<text class="lb" x="52" y="{y}">{escape(label)}</text>'
                 f'<text class="vl" x="{w-30}" y="{y}" text-anchor="end" fill="{col}">{fmt(val)}</text>'
                 f'<line x1="28" y1="{y+14}" x2="{w-28}" y2="{y+14}" stroke="#21262d"/></g>')
    s.append("</svg>")
    return "".join(s)


def card_streak(d):
    w, h = 490, 230
    cur, longest = d["current"] or (None, None, None), d["longest"] or (None, None, None)
    frac = 0.0
    if cur[0] is not None and longest[0]:
        frac = max(0.04, min(1.0, cur[0] / longest[0])) if cur[0] else 0.0
    R = 40; circ = 2 * 3.14159265 * R
    cx, cy = 245, 118
    s = [head(w, h, "Contribution Streak"), f'<text class="t" x="28" y="42" fill="url(#rb)">Contribution Streak</text>']
    s.append(f'<g>{fade(0.3)}<text x="82" y="128" text-anchor="middle" font-size="32" font-weight="bold" fill="#58a6ff">{fmt(d["total"])}</text>'
             f'<text class="mid" x="82" y="158" text-anchor="middle">Total Contributions</text>'
             f'<text class="sm" x="82" y="178" text-anchor="middle">last 12 months</text></g>')
    s.append(f'<g>{fade(0.7)}<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#21262d" stroke-width="7"/>'
             f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="url(#pg)" stroke-width="7" stroke-linecap="round" '
             f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ*(1-frac):.1f}" transform="rotate(-90 {cx} {cy})">'
             f'<animate attributeName="stroke-dashoffset" values="{circ:.1f};{circ:.1f};{circ*(1-frac):.1f}" keyTimes="0;0.4;1" dur="2.3s" fill="freeze"/></circle>'
             f'<circle cx="{cx}" cy="{cy-R}" r="12" fill="#0d1117"/>'
             f'<path transform="translate({cx},{cy-R+1}) scale(.9)" d="M0,-10 C7,-4 9,3 4,9 C1,12 -5,11 -7,6 C-9,1 -4,-3 0,-10 Z" fill="#ffa657"/>'
             f'<text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="28" font-weight="bold" fill="#ffa657">{fmt(cur[0])}</text>'
             f'<text class="mid" x="{cx}" y="{cy+R+30}" text-anchor="middle" fill="#ffa657" style="font-weight:bold;fill:#ffa657">Current Streak</text>'
             f'<text class="sm" x="{cx}" y="{cy+R+48}" text-anchor="middle">{escape(fmt_range(cur[1], cur[2]))}</text></g>')
    s.append(f'<g>{fade(1.1)}<text x="408" y="128" text-anchor="middle" font-size="32" font-weight="bold" fill="#bc8cff">{fmt(longest[0])}</text>'
             f'<text class="mid" x="408" y="158" text-anchor="middle">Longest Streak</text>'
             f'<text class="sm" x="408" y="178" text-anchor="middle">{escape(fmt_range(longest[1], longest[2]))}</text></g>')
    s.append("</svg>")
    return "".join(s)


def card_languages(d):
    w, h = 1000, 200
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs) or 1
    top = langs[:6]
    s = [head(w, h, "Top Languages"), f'<text class="t" x="28" y="42" fill="url(#rb)">Top Languages</text>']
    bx, by, bw, bh = 28, 62, w - 56, 18
    s.append(f'<defs><clipPath id="round"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="9"/></clipPath>'
             f'<clipPath id="grow"><rect x="{bx}" y="{by-2}" width="{bw}" height="{bh+4}"><animate attributeName="width" values="0;0;{bw}" keyTimes="0;0.2;1" dur="1.6s" fill="freeze"/></rect></clipPath></defs>')
    s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="9" fill="#21262d"/>')
    if top and not PLACEHOLDER:
        s.append('<g clip-path="url(#round)"><g clip-path="url(#grow)">')
        x = bx
        for i, (name, val) in enumerate(top):
            seg = bw * val / total
            col = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
            s.append(f'<rect x="{x:.1f}" y="{by}" width="{seg+0.6:.1f}" height="{bh}" fill="{col}"/>')
            x += seg
        s.append('</g></g>')
    for i in range(6):
        col_x, row_y = 40 + (i % 3) * 320, 120 + (i // 3) * 36
        if i < len(top) and not PLACEHOLDER:
            name, val = top[i]
            col = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
            pct = f"{100 * val / total:.1f}%"
            s.append(f'<g>{fade(0.8 + i * 0.25)}<circle cx="{col_x}" cy="{row_y-5}" r="6" fill="{col}"/>'
                     f'<text class="lb" x="{col_x+16}" y="{row_y}">{escape(name)}</text>'
                     f'<text class="vl" x="{col_x+250}" y="{row_y}" text-anchor="end" fill="{col}" style="font-size:15px">{pct}</text></g>')
        elif PLACEHOLDER and i == 0:
            s.append(f'<text class="lb" x="{col_x}" y="{row_y}">Loading... (updates automatically)</text>')
    s.append("</svg>")
    return "".join(s)


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
    pal = ["#ffffff"]
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


# ----------------------------------------------------------------------------- dashboard + spent-my-time cards
PANEL = '#111826'
NB = "&#160;"
CYC = 9.0             # every panel replays every 9 s, each on its own turn - the card never goes blank


def head2(w, h, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f'<title>{escape(title)}</title>'
        '<style>text{font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;white-space:pre}'
        '.t{font-size:22px;font-weight:bold}.sm{font-size:11px;fill:#8b949e}</style>'
        '<defs>'
        f'<linearGradient id="rb" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{w}" y2="0" spreadMethod="repeat">'
        '<stop offset="0" stop-color="#ff5f6d"/><stop offset=".2" stop-color="#ffc371"/><stop offset=".4" stop-color="#7ee787"/>'
        '<stop offset=".6" stop-color="#58a6ff"/><stop offset=".8" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff5f6d"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="{w} 0" dur="7s" repeatCount="indefinite"/></linearGradient>'
        '<linearGradient id="bd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#58a6ff"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff7bb0"/></linearGradient>'
        '<linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#39d0d8"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#ff7bb0"/></linearGradient>'
        '<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff7bb0"/><stop offset=".5" stop-color="#bc8cff"/><stop offset="1" stop-color="#58a6ff"/></linearGradient>'
        '</defs>'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" fill="#0d1117" stroke="url(#bd)" stroke-width="1.5"/>'
    )


def _kts(xs):
    return ";".join(f"{min(1.0, max(0.0, x)):.4f}" for x in xs)


class Card:
    """texts type in, charts fill, then each PANEL resets on its own turn (phase), so the card never goes blank"""

    def __init__(self, T, speed=0.45):
        self.T, self.defs, self.n, self.phase, self.speed = T, [], 0, 0.0, speed

    def _b(self):
        return f' begin="-{self.phase:.2f}s"' if self.phase else ""

    def text(self, txt, x, y, size, fill, t0, anchor="start", weight="bold", dt=0.04):
        txt = str(txt)
        if not txt.strip():
            return ""
        T, n = self.T, len(txt)
        t0, dt = t0 * self.speed, dt * self.speed
        cw = size * 0.6
        wd = n * cw
        x0 = x - wd / 2 if anchor == "middle" else (x - wd if anchor == "end" else x)
        end = T - 0.3
        if t0 + n * dt > end - 0.1:
            dt = max(0.006, (end - 0.1 - t0) / n)
        widths = [0.0] + [(k + 1) * cw for k in range(n)] + [0.0]
        times = [0.0] + [t0 + (k + 1) * dt for k in range(n)] + [end]
        self.n += 1
        cid = f"k{self.n}"
        self.defs.append(f'<clipPath id="{cid}"><rect x="{x0:.1f}" y="{y - size:.1f}" width="{wd:.1f}" height="{size * 1.5:.1f}">'
                         f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in widths)}" keyTimes="{_kts([t / T for t in times])}" '
                         f'calcMode="discrete" dur="{T}s"{self._b()} repeatCount="indefinite"/></rect></clipPath>')
        body = "".join(NB if c == " " else escape(c) for c in txt)
        return (f'<g clip-path="url(#{cid})"><text x="{x0:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                f'textLength="{wd:.1f}" lengthAdjust="spacing">{body}</text></g>')

    def life(self, attr, a, b, v0, v1, tail=0.8):
        """value goes v0 -> v1 quickly, holds for a long time, snaps back just before the panel plays again"""
        T = self.T
        a, b = a * self.speed, b * self.speed
        return (f'<animate attributeName="{attr}" values="{v0};{v0};{v1};{v1};{v0};{v0}" '
                f'keyTimes="{_kts([0, a / T, b / T, (T - tail) / T, (T - 0.3) / T, 1])}" dur="{T}s"{self._b()} repeatCount="indefinite"/>')

    def pop(self, a):
        T = self.T
        a = a * self.speed
        return (f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{_kts([0, a / T, (a + .2) / T, (T - 0.8) / T, (T - 0.3) / T, 1])}" '
                f'dur="{T}s"{self._b()} repeatCount="indefinite"/>')

    def defs_block(self):
        return "<defs>" + "".join(self.defs) + "</defs>"


def panel(x, y, w, h):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{PANEL}" fill-opacity=".82" stroke="#222d42"/>'


def lang_items(counts, limit=5):
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return [(n, v, LANG_COLORS.get(n, FALLBACK[i % len(FALLBACK)])) for i, (n, v) in enumerate(top)]


def card_dashboard(d):
    w, h = 1000, 650
    K = Card(CYC)
    T = CYC
    s = [head2(w, h, "GitHub Stats dashboard"), '<text class="t" x="28" y="44" fill="url(#rb)">GitHub Stats</text>',
         f'<text class="sm" x="{w-28}" y="42" text-anchor="end">live from GitHub - updates every day</text>']
    # ---- row A left: contributions / streak ring / longest streak
    ax, ay, aw, ah = 28, 62, 472, 214
    s.append(panel(ax, ay, aw, ah))
    cur = d["current"] or (None, None, None)
    longest = d["longest"] or (None, None, None)
    frac = max(0.05, min(1.0, cur[0] / longest[0])) if (cur[0] and longest[0]) else 0.0
    R = 48
    circ = 2 * 3.14159265 * R
    c1, c2, c3 = ax + 80, ax + 236, ax + 392
    cy = ay + 98
    s.append(K.text(fmt(d["total"]), c1, cy + 8, 40, "#58a6ff", 0.3, "middle"))
    s.append(K.text("Contributions", c1, cy + 44, 14, "#c9d1d9", 0.9, "middle", "normal"))
    s.append(K.text("last 12 months", c1, cy + 62, 11, "#8b949e", 1.3, "middle", "normal"))
    s.append(f'<circle cx="{c2}" cy="{cy}" r="{R}" fill="none" stroke="#1b2438" stroke-width="8"/>'
             f'<circle cx="{c2}" cy="{cy}" r="{R}" fill="none" stroke="url(#pg)" stroke-width="8" stroke-linecap="round" '
             f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - frac):.1f}" transform="rotate(-90 {c2} {cy})">'
             + K.life("stroke-dashoffset", 0.5, 2.3, f"{circ:.1f}", f"{circ * (1 - frac):.1f}") + '</circle>'
             f'<g><animateTransform attributeName="transform" type="rotate" from="0 {c2} {cy}" to="360 {c2} {cy}" dur="6s" repeatCount="indefinite"/>'
             f'<circle cx="{c2}" cy="{cy - R}" r="4.5" fill="#ffffff"/></g>'
             f'<circle cx="{c2}" cy="{cy - R - 16}" r="11" fill="{PANEL}"/>'
             f'<path transform="translate({c2},{cy - R - 16}) scale(.8)" d="M0,-10 C7,-4 9,3 4,9 C1,12 -5,11 -7,6 C-9,1 -4,-3 0,-10 Z" fill="#ffa657">'
             '<animate attributeName="opacity" values="1;.6;1" dur="1.6s" repeatCount="indefinite"/></path>')
    s.append(K.text(fmt(cur[0]), c2, cy + 11, 32, "#ffa657", 0.6, "middle"))
    s.append(K.text("Current Streak", c2, cy + R + 26, 14, "#ffa657", 1.1, "middle"))
    s.append(K.text(fmt_range(cur[1], cur[2]), c2, cy + R + 44, 11, "#8b949e", 1.5, "middle", "normal"))
    s.append(K.text(fmt(longest[0]), c3, cy + 8, 40, "#bc8cff", 0.7, "middle"))
    s.append(K.text("Longest Streak", c3, cy + 44, 14, "#c9d1d9", 1.2, "middle", "normal"))
    s.append(K.text(fmt_range(longest[1], longest[2]), c3, cy + 62, 11, "#8b949e", 1.6, "middle", "normal"))
    K.phase = 2.2
    # ---- row A right: contributions by weekday (bars rise from the bottom, then drop and rise again)
    bx, by, bw, bh = 516, 62, 456, 214
    s.append(panel(bx, by, bw, bh))
    wd = d["weekday"] or [0] * 7
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    peak = max(range(7), key=lambda i: wd[i]) if any(wd) else None
    s.append(K.text("Contributions by Weekday", bx + 24, by + 34, 14, "#e6edf3", 0.4))
    if peak is not None:
        s.append(K.text("most active: " + names[peak], bx + bw - 24, by + 33, 11, "#8b949e", 1.0, "end", "normal"))
    base, maxh = by + 170, 100
    mx = max(wd) or 1
    for i in range(7):
        x, bwid = bx + 28 + i * 62, 38
        hh = max(3.0, maxh * wd[i] / mx) if wd[i] else 3.0
        a = 0.8 + i * 0.14
        fill = "#ffffff" if i == peak else "url(#bar)"
        s.append(f'<rect x="{x}" y="{base - hh:.1f}" width="{bwid}" height="{hh:.1f}" rx="6" fill="{fill}">'
                 + K.life("height", a, a + 0.8, "3", f"{hh:.1f}") + K.life("y", a, a + 0.8, f"{base - 3}", f"{base - hh:.1f}")
                 + f'<animate attributeName="opacity" values="1;.6;1" dur="3s" begin="{4 + i * 0.3:.1f}s" repeatCount="indefinite"/></rect>')
        s.append(K.text(wd[i] if d["weekday"] else "-", x + bwid / 2, base - hh - 8, 14, "#e6edf3", a + 0.7, "middle"))
        s.append(K.text(names[i], x + bwid / 2, base + 20, 11, "#8b949e", a + 0.2, "middle", "normal"))
    # ---- row B: two donut charts that fill clockwise, segment after segment
    for k, (px, pw, title, counts, unit) in enumerate([(28, 472, "Top Languages by Repository", d["repo_langs"], "repos"),
                                                       (516, 456, "Top Languages by Code Size", d["langs"], "code")]):
        py, ph = 292, 262
        K.phase = 4.4 + k * 2.2
        s.append(panel(px, py, pw, ph))
        s.append(K.text(title, px + 24, py + 34, 14, "#e6edf3", 0.5 + k * 0.2))
        items = lang_items(counts) if not PLACEHOLDER else []
        cx, cy2, Rr = px + 108, py + 150, 64
        C = 2 * 3.14159265 * Rr
        tot = sum(v for _, v, _ in items)
        s.append(f'<circle cx="{cx}" cy="{cy2}" r="{Rr}" fill="none" stroke="#1b2438" stroke-width="24"/>')
        acc = 0.0
        for i, (name, val, col) in enumerate(items):
            L = max(0.0, C * val / tot - 2.5)
            start = C * acc / tot
            a = 1.0 + k * 0.3 + i * 0.35
            s.append(f'<circle cx="{cx}" cy="{cy2}" r="{Rr}" fill="none" stroke="{col}" stroke-width="24" '
                     f'stroke-dasharray="{L:.2f} {C - L:.2f}" stroke-dashoffset="{-start:.2f}" transform="rotate(-90 {cx} {cy2})">'
                     + K.life("stroke-dasharray", a, a + 1.0, f"0 {C:.2f}", f"{L:.2f} {C - L:.2f}") + '</circle>')
            acc += val
        centre = (f"{tot}" if unit == "repos" else f"{tot / 1024:.0f}K") if items else "-"
        s.append(K.text(centre, cx, cy2 + 6, 22, "#e6edf3", 2.2 + k * 0.2, "middle"))
        if items:
            s.append(K.text(unit, cx, cy2 + 24, 11, "#8b949e", 2.6 + k * 0.2, "middle", "normal"))
        for i, (name, val, col) in enumerate(items):
            ly = py + 88 + i * 34
            t = 1.6 + k * 0.3 + i * 0.35
            s.append(f'<circle cx="{px + 212}" cy="{ly - 5}" r="6" fill="{col}">{K.pop(t)}</circle>')
            s.append(K.text(name, px + 228, ly, 14, "#c9d1d9", t, "start", "normal"))
            s.append(K.text(f"{100 * val / tot:.1f}%", px + pw - 26, ly, 14, col, t + 0.3, "end"))
        if not items:
            s.append(K.text("Loading... (updates automatically)", px + 212, py + 110, 14, "#c9d1d9", 0.8, "start", "normal"))
    K.phase = 3.3
    # ---- row C: small totals
    for i, (label, val, col) in enumerate([("Public Repos", d["repos"], "#58a6ff"), ("Total Stars", d["stars"], "#f2cc60"), ("Followers", d["followers"], "#7ee787")]):
        x, y, ww = 28 + i * 324, 570, 296
        s.append(f'<rect x="{x}" y="{y}" width="{ww}" height="52" rx="14" fill="{PANEL}" fill-opacity=".82" stroke="#222d42"/>'
                 f'<circle cx="{x + 26}" cy="{y + 26}" r="6" fill="{col}"><animate attributeName="r" values="6;8;6" dur="2.4s" repeatCount="indefinite"/></circle>')
        s.append(K.text(label, x + 44, y + 31, 14, "#c9d1d9", 2.8 + i * 0.3, "start", "normal"))
        s.append(K.text(fmt(val), x + ww - 24, y + 32, 20, col, 3.0 + i * 0.3, "end"))
    s.insert(1, K.defs_block())
    s.append("</svg>")
    return "".join(s)


CODE = [
    [("const ", "#ff7bb0"), ("dev", "#79c0ff"), (" = {", "#e6edf3")],
    [("  name: ", "#e6edf3"), ('"Lamia Kajal"', "#7ee787"), (",", "#e6edf3")],
    [("  role: ", "#e6edf3"), ('"Full Stack Dev"', "#7ee787"), (",", "#e6edf3")],
    [("  stack: [", "#e6edf3"), ('"Next.js"', "#7ee787"), (", ", "#e6edf3"), ('"Node.js"', "#7ee787"), ("],", "#e6edf3")],
    [("};", "#e6edf3")],
    [("build", "#d2a8ff"), ("(dev);  ", "#e6edf3"), ("// ship it", "#8b949e")],
]
LEVELS = ["#161b22", "#1f6f8b", "#39d0d8", "#7ee787", "#ffc371", "#ff7bb0"]


def level(c, mx):
    return 0 if not c else 1 + min(4, int(4.999 * c / max(mx, 1)))


def card_activity(d):
    w, h, T = 1000, 424, 10.0
    K = Card(T)
    s = [head2(w, h, "Spent my time"), '<text class="t" x="28" y="44" fill="url(#rb)">Spent My Time</text>',
         f'<text class="sm" x="{w-28}" y="42" text-anchor="end">last 26 weeks - every square is a day</text>']
    # ---- mini laptop: the code types itself, is wiped, and types again
    lx, ly, lw, lh = 28, 66, 330, 196
    s.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="12" fill="#0b1220" fill-opacity=".9" stroke="#2a3552" stroke-width="2"/>')
    s.append(f'<rect x="{lx - 14}" y="{ly + lh + 2}" width="{lw + 28}" height="12" rx="6" fill="#1b2438"/>')
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        s.append(f'<circle cx="{lx + 18 + i * 16}" cy="{ly + 16}" r="4.5" fill="{c}"/>')
    cw = 7.8
    t = 0.6
    cur = []
    for i, segs in enumerate(CODE):
        total = sum(len(x) for x, _ in segs)
        yy = ly + 52 + i * 22
        widths = [0.0] + [(k + 1) * cw for k in range(total)] + [0.0]
        times = [0.0] + [t + (k + 1) * 0.02 for k in range(total)] + [T - 0.3]
        K.defs.append(f'<clipPath id="k{i}"><rect x="{lx + 16}" y="{yy - 16}" width="{total * cw:.1f}" height="22">'
                      f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in widths)}" keyTimes="{_kts([x / T for x in times])}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></rect></clipPath>')
        x = lx + 16
        g = [f'<g clip-path="url(#k{i})">']
        for txt, col in segs:
            core = txt.strip(" ")
            if core:
                lead = len(txt) - len(txt.lstrip(" "))
                body = "".join(NB if ch == " " else escape(ch) for ch in core)
                g.append(f'<text x="{x + lead * cw:.1f}" y="{yy}" font-size="13" fill="{col}" textLength="{len(core) * cw:.1f}" lengthAdjust="spacing">{body}</text>')
            x += len(txt) * cw
        g.append("</g>")
        s.append("".join(g))
        for k in range(total + 1):
            cur.append((t + k * 0.02, lx + 16 + k * cw, yy - 13))
        t += total * 0.02 + 0.1
    K.n = 50
    ct = [0.0] + [c[0] for c in cur]
    ct = [max(ct[:i + 1]) for i in range(len(ct))]
    xs = [cur[0][1]] + [c[1] for c in cur]
    ys = [cur[0][2]] + [c[2] for c in cur]
    s.append(f'<g opacity="0"><animate attributeName="opacity" values="0;1;0;0" keyTimes="{_kts([0, cur[0][0] / T, t / T, 1])}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/>'
             f'<rect width="7" height="16" fill="#7ee787" x="{xs[0]:.1f}" y="{ys[0]:.1f}">'
             f'<animate attributeName="x" values="{";".join(f"{v:.1f}" for v in xs)}" keyTimes="{_kts([x / T for x in ct])}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/>'
             f'<animate attributeName="y" values="{";".join(f"{v:.1f}" for v in ys)}" keyTimes="{_kts([x / T for x in ct])}" calcMode="discrete" dur="{T}s" repeatCount="indefinite"/>'
             '<animate attributeName="opacity" values="1;0;1" dur=".9s" repeatCount="indefinite"/></rect></g>')
    K.phase = 3.3
    # ---- heatmap: squares appear one after another like typing, hold, vanish, appear again
    weeks = d["weeks"] or [[None] * 7 for _ in range(26)]
    mx = max([c for wk in weeks for c in wk if c] or [1])
    gx, gy, cs, gap = 396, 76, 17, 4
    idx = 0
    for ci, wk in enumerate(weeks):
        for ri, c in enumerate(wk):
            if c is None:
                continue
            lv = level(c, mx)
            x, y = gx + ci * (cs + gap), gy + ri * (cs + gap)
            a = 0.8 + idx * 0.016
            idx += 1
            tw = ""
            if lv >= 2:
                tw = f'<animate attributeName="opacity" values="1;.5;1" dur="{2.2 + (ci * 7 + ri) % 5 * 0.4:.1f}s" begin="{4 + (ci * 3 + ri) % 7 * 0.5:.1f}s" repeatCount="indefinite"/>'
            s.append(f'<g>{tw}<rect x="{x}" y="{y}" width="{cs}" height="{cs}" rx="4" fill="{LEVELS[lv]}">{K.pop(a)}</rect></g>')
    ly2 = gy + 7 * (cs + gap) + 12
    s.append(f'<text class="sm" x="{gx}" y="{ly2 + 10}">Less</text>')
    for i, col in enumerate(LEVELS):
        s.append(f'<rect x="{gx + 34 + i * 20}" y="{ly2}" width="14" height="14" rx="4" fill="{col}"/>')
    s.append(f'<text class="sm" x="{gx + 34 + 6 * 20 + 4}" y="{ly2 + 10}">More</text>')
    flat = [c for wk in weeks for c in wk if c is not None]
    active = sum(1 for c in flat if c > 0) if d["weeks"] else None
    best = max(flat) if (d["weeks"] and flat) else None
    last = sum(c for c in weeks[-1] if c) if d["weeks"] else None
    for i, (lab, val, col) in enumerate([("Active days", active, "#7ee787"), ("Best day", best, "#ffc371"), ("This week", last, "#58a6ff")]):
        x = 396 + i * 196
        s.append(K.text(fmt(val), x, ly2 + 52, 24, col, 4.4 + i * 0.4))
        s.append(K.text(lab, x, ly2 + 70, 11, "#8b949e", 4.8 + i * 0.4, "start", "normal"))
    K.phase = 6.6
    # ---- code by language: names type in, bars fill from zero, retract, fill again
    tl = sum(d["langs"].values()) or 1
    top3 = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:3] if not PLACEHOLDER else []
    by = 336
    s.append(K.text("Where my code goes", 28, by, 14, "#e6edf3", 5.2))
    for i in range(3):
        x, wbar, y = 28 + i * 324, 296, by + 28
        s.append(f'<rect x="{x}" y="{y + 10}" width="{wbar}" height="12" rx="6" fill="#1b2438"/>')
        if i < len(top3):
            name, val = top3[i]
            pct = 100 * val / tl
            col = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
            fillw = max(6.0, wbar * pct / 100)
            a0 = 5.6 + i * 0.5
            s.append(K.text(name, x, y, 14, "#c9d1d9", a0, "start", "normal"))
            s.append(K.text(f"{pct:.1f}%", x + wbar, y, 14, col, a0 + 0.3, "end"))
            s.append(f'<rect x="{x}" y="{y + 10}" width="{fillw:.1f}" height="12" rx="6" fill="{col}">'
                     + K.life("width", a0 + 0.2, a0 + 1.6, "0", f"{fillw:.1f}") + '</rect>')
    s.insert(1, K.defs_block())
    s.append("</svg>")
    return "".join(s)


def main():
    os.makedirs(OUT, exist_ok=True)
    if PLACEHOLDER:
        data = {"repos": None, "followers": None, "stars": None, "total": None, "current": None, "longest": None, "langs": {},
                "weekday": None, "weeks": None, "repo_langs": {}}
    else:
        data = fetch_data()
    for name, fn in (("github-stats", card_stats), ("github-streak", card_streak), ("github-languages", card_languages),
                     ("github-dashboard", card_dashboard), ("github-activity", card_activity)):
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            svg = fn(data)
            f.write(fx_stars(svg, seed=len(name)) if name in ("github-dashboard", "github-activity") else svg)
    print("cards written to", OUT, "| repos", data["repos"], "| stars", data["stars"], "| total", data["total"])


if __name__ == "__main__":
    main()
