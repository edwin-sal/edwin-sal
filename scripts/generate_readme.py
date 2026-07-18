#!/usr/bin/env python3
"""Regenerates the profile SVG with live GitHub stats.

GitHub READMEs don't render ANSI color codes in fenced code blocks, so the
neofetch-style panel is drawn as an SVG (real colored text) and embedded in
README.md via <img>. Run with GH_TOKEN (or GITHUB_TOKEN) set in the
environment.
"""
import json
import os
import time
import urllib.error
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
GREEN = "#3fb950"
RED = "#f85149"

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


def fetch_repos():
    repos, page = [], 1
    while True:
        batch = api_get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(r for r in batch if not r["fork"])
        page += 1
    return repos


def fetch_code_stats(repos):
    """Sums this user's additions/deletions across all owned repos.

    The contributor-stats endpoint returns 202 while GitHub computes the
    cache; retry a few times before giving up on a given repo.
    """
    additions = deletions = 0
    for repo in repos:
        data = None
        for attempt in range(4):
            req = urllib.request.Request(
                f"https://api.github.com/repos/{USERNAME}/{repo['name']}/stats/contributors",
                headers={"Accept": "application/vnd.github+json"},
            )
            if TOKEN:
                req.add_header("Authorization", f"Bearer {TOKEN}")
            try:
                with urllib.request.urlopen(req) as resp:
                    if resp.status == 202:
                        data = None
                    else:
                        body = resp.read()
                        data = json.loads(body) if body else None
            except urllib.error.HTTPError:
                data = None
            if data:
                break
            time.sleep(2)
        if not data:
            continue
        for entry in data:
            if entry.get("author", {}).get("login") == USERNAME:
                for week in entry["weeks"]:
                    additions += week["a"]
                    deletions += week["d"]
    return additions, deletions


def fetch_stats():
    user = api_get(f"https://api.github.com/users/{USERNAME}")
    repos = fetch_repos()
    stats = {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "following": user["following"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "commits": "n/a",
        "contributed_to": "n/a",
    }
    if TOKEN:
        gql = graphql(
            '{ user(login: "%s") { contributionsCollection { totalCommitContributions } '
            "repositoriesContributedTo(first: 1) { totalCount } } }" % USERNAME
        )
        u = gql["data"]["user"]
        stats["commits"] = u["contributionsCollection"]["totalCommitContributions"]
        stats["contributed_to"] = u["repositoriesContributedTo"]["totalCount"]
    stats["additions"], stats["deletions"] = fetch_code_stats(repos)
    return stats


def header_row(name, total_width):
    dashes = "-" * max(1, total_width - len(name) - 1)
    return [(name, WHITE, False), (" " + dashes, GRAY, False)]


def section_row(name, total_width):
    dashes = "-" * max(1, total_width - len(name) - 3)
    return [("- ", GRAY, False), (name, WHITE, False), (" " + dashes, GRAY, False)]


def _value_segments(value):
    """Normalize a field value into a list of (text, color) segments."""
    if isinstance(value, list):
        return [(str(t), c) for t, c in value]
    return [(str(value), WHITE)]


def field_row(label, value, target_width):
    """Right-align value against target_width; dots stretch to fill the gap.

    value may be a plain string/number (rendered white) or a list of
    (text, color) segments for lines that mix colors, e.g. green/red diffs.
    """
    value_segs = _value_segments(value)
    value_len = sum(len(t) for t, _ in value_segs)
    # layout: ". " + "label:" + " " + dots + " " + value
    fixed = 2 + (len(label) + 1) + 1 + 1 + value_len
    dots = "." * max(1, target_width - fixed)
    return [
        (". ", GRAY, False),
        (f"{label}:", ORANGE, False),
        (" " + dots + " ", GRAY, False),
        *[(t, c, False) for t, c in value_segs],
    ]


def plain_row(text):
    return [(text, GRAY, False)]


def build_rows(stats):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repos_value = [
        (f"{stats['repos']}", WHITE),
        (f" {{Contributed: {stats['contributed_to']}}}", ORANGE),
        (" | ", GRAY),
        ("Stars:", ORANGE),
        (f" {stats['stars']}", WHITE),
    ]
    followers_value = [
        (f"{stats['commits']}", WHITE),
        (" | ", GRAY),
        ("Followers:", ORANGE),
        (f" {stats['followers']}", WHITE),
    ]
    loc_value = [
        (f"{stats['additions'] + stats['deletions']:,} (", WHITE),
        (f"{stats['additions']:,}++", GREEN),
        (", ", WHITE),
        (f"{stats['deletions']:,}--", RED),
        (")", WHITE),
    ]

    # (label, value) pairs; value is a str or a list of (text, color) segments
    fields = [
        ("Role", "AI Developer"),
        ("Languages.Programming", "Python, TypeScript, Java"),
        ("Hobbies", "Vibing"),
        ("Site", "edwinsal.vercel.app"),
        ("Email", "edwinsal@protonmail.com"),
        ("GitHub", "github.com/edwin-sal"),
        ("Repos", repos_value),
        ("Commits", followers_value),
        ("Lines of Code on GitHub", loc_value),
    ]

    # panel width = widest field line with at least a couple of dots
    panel_width = max(
        len(label) + 5 + sum(len(t) for t, _ in _value_segments(value)) + 2
        for label, value in fields
    )

    fr = {label: field_row(label, value, panel_width) for label, value in fields}

    return [
        header_row(USERNAME, panel_width),
        fr["Role"],
        fr["Languages.Programming"],
        fr["Hobbies"],
        [],
        section_row("Contact", panel_width),
        fr["Site"],
        fr["Email"],
        fr["GitHub"],
        [],
        section_row("GitHub Stats", panel_width),
        fr["Repos"],
        fr["Commits"],
        fr["Lines of Code on GitHub"],
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
