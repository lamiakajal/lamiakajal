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
    # contributions + streaks
    try:
        q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
               totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        cal = graphql(q, {"login": USER})["user"]["contributionsCollection"]["contributionCalendar"]
        days = [(datetime.date.fromisoformat(d["date"]), d["contributionCount"])
                for w in cal["weeks"] for d in w["contributionDays"]]
        data["total"] = cal["totalContributions"]
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


def main():
    os.makedirs(OUT, exist_ok=True)
    if PLACEHOLDER:
        data = {"repos": None, "followers": None, "stars": None, "total": None, "current": None, "longest": None, "langs": {}}
    else:
        data = fetch_data()
    for name, fn in (("github-stats", card_stats), ("github-streak", card_streak), ("github-languages", card_languages)):
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(fn(data))
    print("cards written to", OUT, "| repos", data["repos"], "| stars", data["stars"], "| total", data["total"])


if __name__ == "__main__":
    main()
