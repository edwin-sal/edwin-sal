#!/usr/bin/env python3
"""Regenerates README.md's neofetch-style panel with live GitHub stats.

Run with GH_TOKEN (or GITHUB_TOKEN) set in the environment.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

USERNAME = "edwin-sal"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

ASCII_ART = r"""             ..
          .:----:
         :--==+==-::.
           :=+**+++==-::.   .
             -+*#***++++==:  .:.
             .=++####**+-:.
      .:----:.:-=+####+=--:
             ...:+*##%#*=++==-:::.
       -.      .:=#@@@@%*+=====+*%@@%%#**+-::=--:
            .   .+@@@@@@#=.     -+%@@@@@@@@@@@@@%*:
   ..:::.....  :*@@@@@@@#-  :+:      .*@@@@@@@@@@@#:
  ::::-:-::. .:*@@@@@@@@%*-..=%:   =#. .-+%@@@@@@@@+
  :=--:-:::..-#@@@@@@@@@@@%====+*#%%%#*#%%%@@@@@@@@%-
  :::---::.:=#@@@@@@@@@@@@@@####%@@@@@@@@@@@@@@@@@@%
  .:::--::-+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@=
   ::-:::-+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%
   :--:::-+*#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@-
  .::-:.   :=##%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+
  .:::::...-=+*%#++%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@.
@....::.:-=*#*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+
@+   ..:-=*#+*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%
 -    ...:=**#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@+
  ..     .:====+#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%
   ... .:::::----==*%@@@@@@@@@@@@@@@@@@@@@@@@@-
     ...-===++#%%%%%*===%@@@@@@@@@@@@@@@@@@@@@-
     .:::::-=*#%%@%@@@@@%@@@@@@@@@@@@@@@@@@@@#*=-.
      ===----==*#%%@@@@@@@@@@@@@@@@@@@@@@@@@@@%#*++=-:. .
       ====++*###%@@@@@%@@@@@@@@@@@@@@@@@@@@@@@@@%%%*+*::
        -=+++*%@@@@@@@@@@@@@@@@@@@@@%%%@@@@@@@@@@@@@%#==-
         :---+*%@@@@@@@@@@@@@@#****#%@@@@@@@@@@@@@@@@#=#@
          :..-=+*%%@@%@%##*+==+++*#%@@@@@@@@@@@@@@@@%*@@@@@
             .....:::::::---==++#%@@@@@@@@@@@@@@@@@#*@@@@@@@@
           -=.        ..:-:-=++#%@@@@@@@@@@@@@@@@@*%@@@@@@@@@
           :-:...      ...:-=+*##%@@@@@@@@@@@@@@+*@@@@@@@@@@@@
           --:::...      .:-=++*#%@@@@@@@@@@@@%+@@@@@@@@@@@@@@@
           ::::::..::    .:-=+***%%@@@@@@@@@%+@@@@@@@@@@@@@@@@@@
           :---:: .--:.  .::-==++#%@@@@@@@*=@@@@@@@@@@@@@@@@@@@@@
           -::--:  :=-.  .:::-=++*%%@%%@#=@@@@@@@@@@@@@@@@@@@@@@@@@
           :--==. .---.  ..:::-===*#@@%=#@@@@@@@@@@@@@@@@@@@@@@@@@@@
          --=++= ..-:.. .....:+%@@@@%=*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
         :=+=++-  ..    .-+@@@@@@@#-+@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
       .:-+====:  .:-*#%@@@@@@@%=:*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      .:-=+--=-==+*#%%%%@@@@@@+.*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      ..--===++**#****%@%%%@*.-*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      .:----=++*++++#%%##@%. +*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@""".split("\n")

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
        f"{USERNAME} ------------------------------",
        ". Role: ........................ AI Developer",
        ". Languages.Programming: ....... Python, TypeScript, Java",
        ". Hobbies: ...................... Vibing",
        "",
        "- GitHub Stats -----------------------",
        f". Public Repos: ................. {stats['repos']}",
        f". Followers: .................... {stats['followers']} | Following: {stats['following']}",
        f". Commits (last year): .......... {stats['commits']}",
        "",
        "- Contact -----------------------------",
        ". Site: .......................... edwinsal.vercel.app",
        ". Email: ......................... edwinsal@protonmail.com",
        ". GitHub: ........................ github.com/edwin-sal",
        "",
        f"Last updated: {today} (auto)",
    ]

    lines = []
    for i in range(max(len(ASCII_ART), len(right))):
        left = ASCII_ART[i] if i < len(ASCII_ART) else ""
        r = right[i] if i < len(right) else ""
        lines.append(f"{left.ljust(ART_WIDTH)}   {r}".rstrip())
    return "\n".join(lines)


def render(panel):
    return f"""## Hi there, I'm Edwin 👋

```text
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
