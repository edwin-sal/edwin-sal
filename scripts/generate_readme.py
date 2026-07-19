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
    # A "rule" row: label text followed by a continuous drawn line to the
    # panel's right edge. prefix_chars includes the trailing space gap.
    return {
        "rule": True,
        "prefix": [(name, WHITE, False)],
        "prefix_chars": len(name) + 1,
        "total_width": total_width,
    }


def section_row(name, total_width):
    return {
        "rule": True,
        "prefix": [("- ", GRAY, False), (name, WHITE, False)],
        "prefix_chars": 2 + len(name) + 1,
        "total_width": total_width,
    }


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


def dual_field_row(llabel, lvalue, rlabel, rvalue, pipe_col, target_width):
    """Two label:value pairs on one line, split by a "|" fixed at pipe_col.

    Both halves get dot-leaders; the right value is flush to target_width.
    Every row built at the same pipe_col aligns its divider vertically.
    """
    lsegs = _value_segments(lvalue)
    rsegs = _value_segments(rvalue)
    llen = sum(len(t) for t, _ in lsegs)
    rlen = sum(len(t) for t, _ in rsegs)

    # left half: ". " + llabel + ":" + " " + dots1 + " " + lvalue
    # sized so the " | " divider's pipe lands on the same column every row.
    left_fixed = 2 + (len(llabel) + 1) + 1 + 1 + llen  # everything but dots1
    dots1 = "." * max(1, pipe_col - left_fixed)
    left_len = left_fixed + len(dots1)

    # right half. With a label: " | " + rlabel + ":" + " " + dots2 + " " + rvalue,
    # right value flush to target_width. Without a label (e.g. the LOC breakdown):
    # just " | " + rvalue, no dot leader.
    if rlabel:
        right_fixed = 3 + (len(rlabel) + 1) + 1 + 1 + rlen  # everything but dots2
        dots2 = "." * max(1, target_width - left_len - right_fixed)
        right_segs = [
            (" | ", GRAY, False),
            (f"{rlabel}:", ORANGE, False),
            (" " + dots2 + " ", GRAY, False),
            *[(t, c, False) for t, c in rsegs],
        ]
    else:
        right_segs = [(" | ", GRAY, False), *[(t, c, False) for t, c in rsegs]]

    return [
        (". ", GRAY, False),
        (f"{llabel}:", ORANGE, False),
        (" " + dots1 + " ", GRAY, False),
        *[(t, c, False) for t, c in lsegs],
        *right_segs,
    ]


def plain_row(text):
    return [(text, GRAY, False)]


def _vlen(value):
    return sum(len(t) for t, _ in _value_segments(value))


def build_rows(stats):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # single-value (label, value) pairs; value is a str or (text, color) list
    fields = [
        ("Role", "AI Developer"),
        ("Languages.Programming", "Python, TypeScript, Java"),
        ("Hobbies", "Vibing"),
        ("Site", "edwinsal.vercel.app"),
        ("Email", "edwinsal@protonmail.com"),
        ("GitHub", "github.com/edwin-sal"),
    ]

    # two-column stat rows: (llabel, lvalue, rlabel, rvalue); the pipe divider
    # is fixed at one column so all three align vertically. LOC's right side is
    # the green/red breakdown with no second label.
    total_loc = stats["additions"] + stats["deletions"]
    loc_breakdown = [
        ("(", WHITE),
        (f"{stats['additions']:,}++", GREEN),
        (", ", WHITE),
        (f"{stats['deletions']:,}--", RED),
        (")", WHITE),
    ]
    repos_left = [
        (f"{stats['repos']}", WHITE),
        (f" {{Contributed: {stats['contributed_to']}}}", ORANGE),
    ]
    stat_specs = [
        ("Repos", repos_left, "Stars", stats["stars"]),
        ("Commits", stats["commits"], "Followers", stats["followers"]),
        ("Lines of Code on GitHub", f"{total_loc:,}", "", loc_breakdown),
    ]

    # left_fixed = everything on the left half but the dot leader
    def left_fixed(label, value):
        return 2 + (len(label) + 1) + 1 + 1 + _vlen(value)

    def right_fixed(rlabel, rvalue):
        if not rlabel:
            return 3 + _vlen(rvalue)  # just " | " + value
        return 3 + (len(rlabel) + 1) + 1 + 1 + _vlen(rvalue)

    # pipe column clears the longest left half (LOC's label is the long one)
    pipe_col = max(left_fixed(s[0], s[1]) for s in stat_specs) + 2

    # panel width must fit the widest field line and the widest stat line
    field_natural = max(len(l) + 5 + _vlen(v) + 2 for l, v in fields)
    stat_natural = max(pipe_col + right_fixed(s[2], s[3]) for s in stat_specs)
    panel_width = max(field_natural, stat_natural)

    fr = {label: field_row(label, value, panel_width) for label, value in fields}
    stat_rows = [
        dual_field_row(llabel, lvalue, rlabel, rvalue, pipe_col, panel_width)
        for llabel, lvalue, rlabel, rvalue in stat_specs
    ]

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
        *stat_rows,
        [],
        plain_row(f"Last updated: {today} (auto)"),
    ]


def render_svg(stats):
    rows = build_rows(stats)
    n_lines = max(len(ASCII_ART), len(rows))
    max_row_chars = max(
        (
            row["total_width"]
            if isinstance(row, dict)
            else sum(len(t) for t, _, _ in row)
            for row in rows
            if row
        ),
        default=0,
    )
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

        # Force every line to an exact pixel width (chars * CHAR_WIDTH) with
        # lengthAdjust, so column alignment holds even when GitHub falls back
        # to a proportional font instead of a real monospace one.
        if i < len(ASCII_ART) and ASCII_ART[i]:
            art = ASCII_ART[i]
            tl = len(art) * CHAR_WIDTH
            lines.append(
                f'<text x="{art_x}" y="{y}" fill="{FG}" xml:space="preserve" '
                f'textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs">{escape(art)}</text>'
            )

        if i < len(rows) and rows[i]:
            row = rows[i]
            if isinstance(row, dict) and row.get("rule"):
                # label prefix at fixed width, then a continuous drawn line
                prefix = row["prefix"]
                prefix_chars = row["prefix_chars"]
                label_chars = prefix_chars - 1  # exclude the trailing-space gap
                ptl = label_chars * CHAR_WIDTH
                spans = "".join(
                    f'<tspan fill="{c}"{" font-weight=\"bold\"" if b else ""} '
                    f'xml:space="preserve">{escape(t)}</tspan>'
                    for t, c, b in prefix
                )
                lines.append(
                    f'<text x="{stats_x}" y="{y}" textLength="{ptl:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs">{spans}</text>'
                )
                line_x1 = stats_x + prefix_chars * CHAR_WIDTH
                line_x2 = stats_x + row["total_width"] * CHAR_WIDTH
                line_y = y - FONT_SIZE * 0.32
                lines.append(
                    f'<line x1="{line_x1:.1f}" y1="{line_y:.1f}" x2="{line_x2:.1f}" '
                    f'y2="{line_y:.1f}" stroke="{GRAY}" stroke-width="1"/>'
                )
            else:
                char_count = sum(len(t) for t, _, _ in row)
                tl = char_count * CHAR_WIDTH
                spans = []
                for text, color, bold in row:
                    weight = ' font-weight="bold"' if bold else ""
                    spans.append(f'<tspan fill="{color}"{weight} xml:space="preserve">{escape(text)}</tspan>')
                lines.append(
                    f'<text x="{stats_x}" y="{y}" textLength="{tl:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs">{"".join(spans)}</text>'
                )

    lines.append("</svg>")
    return "\n".join(lines)


def render_readme():
    return """![profile stats](./assets/profile.svg)

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
