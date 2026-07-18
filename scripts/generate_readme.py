#!/usr/bin/env python3
"""Regenerates README.md's neofetch-style panel with live GitHub stats.

Run with GH_TOKEN (or GITHUB_TOKEN) set in the environment.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USERNAME = "edwin-sal"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
ORANGE = "\x1b[38;5;215m"
GRAY = "\x1b[38;5;245m"
WHITE = "\x1b[38;5;255m"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def vljust(s, width):
    return s + " " * max(0, width - visible_len(s))


def header_line(name, total_width=44):
    dashes = "-" * max(1, total_width - len(name) - 1)
    return f"{BOLD}{WHITE}{name}{RESET} {GRAY}{dashes}{RESET}"


def section_line(name, total_width=40):
    dashes = "-" * max(1, total_width - len(name) - 3)
    return f"{GRAY}- {ORANGE}{BOLD}{name}{RESET} {GRAY}{dashes}{RESET}"


def field_line(label, value, dot_width=34):
    prefix = f". {label}: "
    dots = "." * max(1, dot_width - len(prefix))
    return f"{GRAY}. {ORANGE}{label}:{RESET} {GRAY}{dots}{RESET} {WHITE}{value}{RESET}"

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


def build_panel(stats):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    right = [
        header_line(USERNAME),
        field_line("Role", "AI Developer"),
        field_line("Languages.Programming", "Python, TypeScript, Java"),
        field_line("Hobbies", "Vibing"),
        "",
        section_line("GitHub Stats"),
        field_line("Public Repos", stats["repos"]),
        field_line("Followers", f"{stats['followers']} | Following: {stats['following']}"),
        field_line("Commits (last year)", stats["commits"]),
        "",
        section_line("Contact"),
        field_line("Site", "edwinsal.vercel.app"),
        field_line("Email", "edwinsal@protonmail.com"),
        field_line("GitHub", "github.com/edwin-sal"),
        "",
        f"{GRAY}Last updated: {today} (auto){RESET}",
    ]

    lines = []
    for i in range(max(len(ASCII_ART), len(right))):
        left = ASCII_ART[i] if i < len(ASCII_ART) else ""
        r = right[i] if i < len(right) else ""
        lines.append(f"{left.ljust(ART_WIDTH)}   {r}")
    return "\n".join(lines)


def render(panel):
    return f"""## Hi there, I'm Edwin 👋

```ansi
{panel}
```

<sub>Stats auto-update daily via GitHub Actions.</sub>
"""


def main():
    stats = fetch_stats()
    panel = build_panel(stats)
    content = render(panel)
    with open(os.path.join(os.path.dirname(__file__), "..", "README.md"), "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
