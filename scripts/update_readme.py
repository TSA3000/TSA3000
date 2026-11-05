#!/usr/bin/env python3
"""Fill README markers with live repo data from the GitHub API."""
import datetime as dt
import json
import os
import re
import urllib.request

# ── Settings ────────────────────────────────────────────────────────────────
USER = "TSA3000"
README = "README.md"
EXCLUDE = {USER.lower()}                  # skip the profile repo itself
HIDE_FORKS = True
KEEP_FORKS = {"deluge-remote-modern"}     # forks you actively maintain
HIDE_ARCHIVED = False
MAX_REPOS = 15
MAX_EVENTS = 6
TOKEN = os.environ.get("GITHUB_TOKEN")
# ────────────────────────────────────────────────────────────────────────────


def gh(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as r:
        return json.load(r)


def ago(iso):
    s = int((dt.datetime.now(dt.timezone.utc) -
             dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds())
    for unit, sec in (("year", 31536000), ("month", 2592000), ("week", 604800),
                      ("day", 86400), ("hour", 3600), ("minute", 60)):
        if s >= sec:
            n = s // sec
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"


def get_repos():
    repos, page = [], 1
    while True:
        batch = gh(f"https://api.github.com/users/{USER}/repos"
                   f"?per_page=100&page={page}&type=owner&sort=pushed")
        if not batch:
            return repos
        repos += batch
        page += 1


def filter_repos(repos):
    keep = {k.lower() for k in KEEP_FORKS}
    out = []
    for r in repos:
        name = r["name"].lower()
        if name in EXCLUDE:
            continue
        if HIDE_FORKS and r["fork"] and name not in keep:
            continue
        if HIDE_ARCHIVED and r["archived"]:
            continue
        out.append(r)
    return out


def stats_block(repos):
    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)
    last = max(repos, key=lambda r: r["pushed_at"])
    b = "https://img.shields.io/badge"
    return (
        '<p align="center">\n'
        f'  <img src="{b}/Repos-{len(repos)}-blue?style=for-the-badge&logo=github" />\n'
        f'  <img src="{b}/Total%20stars-{stars}-yellow?style=for-the-badge&logo=starship" />\n'
        f'  <img src="{b}/Forks-{forks}-green?style=for-the-badge&logo=git" />\n'
        '</p>\n\n'
        f'<p align="center"><sub>🕒 Last push: <b><a href="{last["html_url"]}">{last["name"]}</a></b>'
        f' · {ago(last["pushed_at"])} · auto-updated '
        f'{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC</sub></p>'
    )


def repos_block(repos):
    rows = ["| Repository | Description | ⭐ | Language | Updated | |",
            "|---|---|:-:|:-:|:-:|:-:|"]
    for r in repos[:MAX_REPOS]:
        name = f'[**{r["name"]}**]({r["html_url"]})'
        if r["fork"]:
            name += " 🍴"
        if r["archived"]:
            name += " 📦"
        desc = (r["description"] or "—").replace("|", "\\|")
        lang = r["language"] or "—"
        rows.append(
            f'| {name} | {desc} | {r["stargazers_count"]} | `{lang}` | '
            f'{ago(r["pushed_at"])} | [🐛 Issue]({r["html_url"]}/issues/new) |'
        )
    rows.append(f"\n➡️ [See all repositories](https://github.com/{USER}?tab=repositories)")
    return "\n".join(rows)


def activity_block():
    lines, seen = [], set()
    for e in gh(f"https://api.github.com/users/{USER}/events/public?per_page=100"):
        repo = e["repo"]["name"]
        short = repo.split("/")[-1]
        if short.lower() in EXCLUDE:
            continue
        link = f"[{short}](https://github.com/{repo})"
        p, t = e["payload"], e["type"]
        if t == "PushEvent":
            branch = p.get("ref", "").replace("refs/heads/", "")
            key = ("push", repo, branch)
            if key in seen:          # collapse repeated pushes to same branch
                continue
            seen.add(key)
            msg = f"📝 Pushed to {link} `{branch}`"
        elif t == "ReleaseEvent":
            msg = f"🚀 Released **{p['release']['tag_name']}** in {link}"
        elif t == "CreateEvent" and p.get("ref_type") == "repository":
            msg = f"✨ Created repository {link}"
        elif t == "CreateEvent" and p.get("ref_type") == "tag":
            msg = f"🏷️ Tagged **{p['ref']}** in {link}"
        elif t == "IssuesEvent":
            msg = f"🐛 {p['action'].capitalize()} issue #{p['issue']['number']} in {link}"
        elif t == "PullRequestEvent":
            msg = f"🔀 {p['action'].capitalize()} PR #{p['pull_request']['number']} in {link}"
        elif t == "WatchEvent":
            msg = f"⭐ Starred {link}"
        else:
            continue
        lines.append(f"{len(lines) + 1}. {msg} · <sub>{ago(e['created_at'])}</sub>")
        if len(lines) >= MAX_EVENTS:
            break
    return "\n".join(lines) or "_No recent public activity._"


def inject(text, tag, content):
    pattern = rf"(<!-- {tag}:START -->).*?(<!-- {tag}:END -->)"
    return re.sub(pattern, lambda m: f"{m[1]}\n{content}\n{m[2]}", text, flags=re.S)


def main():
    repos = filter_repos(get_repos())
    with open(README, encoding="utf-8") as f:
        text = f.read()
    new = inject(text, "STATS", stats_block(repos))
    new = inject(new, "REPOS", repos_block(repos))
    new = inject(new, "ACTIVITY", activity_block())
    if new != text:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()
