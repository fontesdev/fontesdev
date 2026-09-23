#!/usr/bin/env python3
"""Generates the monochrome stats card (dark + light) from the GitHub GraphQL API.

No third-party service: github-readme-stats goes down, this does not.
Run by .github/workflows/stats.yml with GITHUB_TOKEN in the environment.
"""
import json
import os
import urllib.request
from pathlib import Path

USER = os.environ.get("STATS_USER", "fontesdev")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(__file__).resolve().parents[1] / "assets"

QUERY = """
query($login:String!) {
  user(login:$login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    pullRequests(states:MERGED) { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, orderBy:{field:STARGAZERS, direction:DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def api(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]


def collect():
    u = api(QUERY, {"login": USER})["user"]
    c = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]

    langs = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] = langs.get(edge["node"]["name"], 0) + edge["size"]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]

    days = [d for w in c["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    current = longest = run = 0
    for day in days:
        run = run + 1 if day["contributionCount"] > 0 else 0
        longest = max(longest, run)
    for day in reversed(days):
        if day["contributionCount"] > 0:
            current += 1
        elif current or day is not days[-1]:
            break

    return {
        "commits": c["totalCommitContributions"] + c["restrictedContributionsCount"],
        "contributions": c["contributionCalendar"]["totalContributions"],
        "prs": u["pullRequests"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "current_streak": current,
        "longest_streak": longest,
        "langs": [(name, size / total) for name, size in top],
    }


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(d, bg, fg):
    W, H = 900, 330
    mono = "'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace"
    sans = "'Helvetica Neue',Helvetica,Arial,sans-serif"
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="GitHub stats for {USER}">',
        f'<rect width="{W}" height="{H}" fill="{bg}"/>',
        f'<path d="M14 14h30M14 14v30" stroke="{fg}" stroke-width="3" fill="none"/>',
        f'<path d="M{W-14} {H-14}h-30M{W-14} {H-14}v-30" stroke="{fg}" stroke-width="3" fill="none"/>',
        f'<text x="40" y="58" font-family="{sans}" font-size="26" font-weight="800" letter-spacing="2" fill="{fg}">THE NUMBERS</text>',
        f'<rect x="40" y="72" width="{W-80}" height="3" fill="{fg}"/>',
    ]

    stats = [
        ("COMMITS / YR", f"{d['commits']:,}"),
        ("CONTRIBUTIONS", f"{d['contributions']:,}"),
        ("PRs MERGED", f"{d['prs']:,}"),
        ("REPOS", f"{d['repos']:,}"),
        ("STREAK / NOW", f"{d['current_streak']}d"),
        ("STREAK / BEST", f"{d['longest_streak']}d"),
    ]
    for i, (label, value) in enumerate(stats):
        x = 40 + (i % 3) * 176
        y = 128 + (i // 3) * 82
        p.append(f'<text x="{x}" y="{y}" font-family="{sans}" font-size="38" font-weight="800" fill="{fg}">{value}</text>')
        p.append(f'<text x="{x}" y="{y+22}" font-family="{mono}" font-size="12" letter-spacing="1.5" fill="{fg}" opacity="0.6">{label}</text>')

    # language bars, drawn with an animated width so the card builds itself
    bx, bw = 580, 280
    p.append(f'<text x="{bx}" y="112" font-family="{mono}" font-size="12" letter-spacing="1.5" fill="{fg}" opacity="0.6">LANGUAGE SHARE</text>')
    for i, (name, share) in enumerate(d["langs"]):
        y = 132 + i * 30
        p.append(f'<text x="{bx}" y="{y}" font-family="{mono}" font-size="13" fill="{fg}">{esc(name)}</text>')
        p.append(f'<text x="{bx+bw}" y="{y}" text-anchor="end" font-family="{mono}" font-size="13" fill="{fg}" opacity="0.6">{share*100:.1f}%</text>')
        p.append(f'<rect x="{bx}" y="{y+6}" width="{bw}" height="6" fill="{fg}" opacity="0.15"/>')
        p.append(
            f'<rect x="{bx}" y="{y+6}" width="0" height="6" fill="{fg}">'
            f'<animate attributeName="width" from="0" to="{bw*share:.1f}" begin="{0.15*i:.2f}s" dur="0.9s" fill="freeze"/></rect>'
        )

    p.append(f'<text x="40" y="{H-26}" font-family="{mono}" font-size="11" letter-spacing="1.5" fill="{fg}" opacity="0.45">SELF-GENERATED · NO THIRD-PARTY CARD SERVICE</text>')
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    data = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stats-dark.svg").write_text(card(data, "#000000", "#ffffff"))
    (OUT / "stats-light.svg").write_text(card(data, "#ffffff", "#000000"))
    print(json.dumps({k: v for k, v in data.items() if k != "langs"}, indent=2))
