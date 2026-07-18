#!/usr/bin/env python3
"""Regenerates the profile SVG with live GitHub stats.

GitHub READMEs don't render ANSI color codes in fenced code blocks, so the
neofetch-style panel is drawn as an SVG (real colored text) and embedded in
README.md via <img>. Run with GH_TOKEN (or GITHUB_TOKEN) set in the
environment.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

USERNAME = "edwin-sal"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

BG = "#0d1117"
FG = "#e6edf3"
ORANGE = "#ffa657"
GRAY = "#8b949e"
WHITE = "#f0f6fc"

FONT_SIZE = 14
LINE_HEIGHT = 18
CHAR_WIDTH = 8.42
PAD = 20

ASCII_ART = r"""       .
     -=+=:.
       +#*++=: :
       .:*##=+=::
      . .@@@#.  -%@@@@@@%:
 ::--: :@@@@%-.%  # -%@@@@
 .:-:-%@@@@@@@@@@@@@@@@@@@
  -::+#@@@@@@@@@@@@@@@@@@-
 .::..=*#+@@@@@@@@@@@@@@@
   ..=*@@@@@@@@@@@@@@@@@
  . :::--=%@@@@@@@@@@@@-
   ==--=#%@@@@@@@@@@@@@%*+-..
    -++%@@@@@@@@@@%%@@@@@@%=-
     :.=*%@@#*=++#@@@@@@@@%@@@
      -..   .:=*#@@@@@@@+@@@@@@
      :::.:  :=**%@@@@%@@@@@@@@@
      :-: =. ::=+%@%#@@@@@@@@@@@@@
     ==+ .  .+@@@#+@@@@@@@@@@@@@@@@
   .-+--=*%%@@@+*@@@@@@@@@@@@@@@@@@@@""".split("\n")

ART_WIDTH = max(len(l) for l in ASCII_ART)


def api_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def graphql(query):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_stats():
    user = api_get(f"https://api.github.com/users/{USERNAME}")
    stats = {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "following": user["following"],
        "commits": "n/a",
    }
    if TOKEN:
        gql = graphql(
            '{ user(login: "%s") { contributionsCollection { totalCommitContributions } } }' % USERNAME
        )
        stats["commits"] = gql["data"]["user"]["contributionsCollection"]["totalCommitContributions"]
    return stats


def header_row(name, total_width=44):
    dashes = "-" * max(1, total_width - len(name) - 1)
    return [(name, WHITE, True), (" " + dashes, GRAY, False)]


def section_row(name, total_width=40):
    dashes = "-" * max(1, total_width - len(name) - 3)
    return [("- ", GRAY, False), (name, ORANGE, True), (" " + dashes, GRAY, False)]


def field_row(label, value, dot_width=34):
    prefix = f". {label}: "
    dots = "." * max(1, dot_width - len(prefix))
    return [
        (". ", GRAY, False),
        (f"{label}:", ORANGE, False),
        (" " + dots + " ", GRAY, False),
        (str(value), WHITE, False),
    ]


def plain_row(text):
    return [(text, GRAY, False)]


def build_rows(stats):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        header_row(USERNAME),
        field_row("Role", "AI Developer"),
        field_row("Languages.Programming", "Python, TypeScript, Java"),
        field_row("Hobbies", "Vibing"),
        [],
        section_row("GitHub Stats"),
        field_row("Public Repos", stats["repos"]),
        field_row("Followers", f"{stats['followers']} | Following: {stats['following']}"),
        field_row("Commits (last year)", stats["commits"]),
        [],
        section_row("Contact"),
        field_row("Site", "edwinsal.vercel.app"),
        field_row("Email", "edwinsal@protonmail.com"),
        field_row("GitHub", "github.com/edwin-sal"),
        [],
        plain_row(f"Last updated: {today} (auto)"),
    ]


def render_svg(stats):
    rows = build_rows(stats)
    n_lines = max(len(ASCII_ART), len(rows))
    max_row_chars = max((sum(len(t) for t, _, _ in row) for row in rows if row), default=0)
    width = int(PAD * 2 + (ART_WIDTH + 3 + max_row_chars) * CHAR_WIDTH)
    height = int(PAD * 2 + n_lines * LINE_HEIGHT)

    art_x = PAD
    stats_x = PAD + (ART_WIDTH + 3) * CHAR_WIDTH

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace" '
        f'font-size="{FONT_SIZE}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
    ]

    for i in range(n_lines):
        y = PAD + FONT_SIZE + i * LINE_HEIGHT

        if i < len(ASCII_ART) and ASCII_ART[i]:
            lines.append(
                f'<text x="{art_x}" y="{y}" fill="{FG}" xml:space="preserve">{escape(ASCII_ART[i])}</text>'
            )

        if i < len(rows) and rows[i]:
            spans = []
            for text, color, bold in rows[i]:
                weight = ' font-weight="bold"' if bold else ""
                spans.append(f'<tspan fill="{color}"{weight} xml:space="preserve">{escape(text)}</tspan>')
            lines.append(f'<text x="{stats_x}" y="{y}">{"".join(spans)}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def render_readme():
    return """## Hi there, I'm Edwin 👋

![profile stats](./assets/profile.svg)

<sub>Stats auto-update daily via GitHub Actions.</sub>
"""


def main():
    stats = fetch_stats()
    svg = render_svg(stats)
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    os.makedirs(os.path.join(repo_root, "assets"), exist_ok=True)
    with open(os.path.join(repo_root, "assets", "profile.svg"), "w") as f:
        f.write(svg)
    with open(os.path.join(repo_root, "README.md"), "w") as f:
        f.write(render_readme())


if __name__ == "__main__":
    main()
