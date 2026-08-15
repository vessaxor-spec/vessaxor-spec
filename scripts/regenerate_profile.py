#!/usr/bin/env python3
"""Regenerate the narrowly dynamic blocks in the VESSAXOR profile README.

The profile identity remains hand-authored. This script only refreshes:
- current public release metadata for explicitly allowlisted repositories;
- the curated public "Now" block from profile/status.toml.

No account-wide repository discovery is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STATUS = ROOT / "profile" / "status.toml"

ALLOWED_REPOSITORIES = {
    "vessaxor-spec/The-ever-evolving-orchestration-",
    "vessaxor-spec/GroX",
}


def load_status() -> dict:
    with STATUS.open("rb") as handle:
        return tomllib.load(handle)


def github_json(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "vessaxor-profile-regenerator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc


def latest_release(repository: str) -> dict:
    if repository not in ALLOWED_REPOSITORIES:
        raise ValueError(f"Repository is not allowlisted: {repository}")

    owner, name = repository.split("/", 1)
    url = (
        "https://api.github.com/repos/"
        f"{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(name, safe='')}/releases/latest"
    )
    payload = github_json(url)
    tag = payload.get("tag_name")
    html_url = payload.get("html_url")
    if not isinstance(tag, str) or not tag:
        raise RuntimeError(f"Latest release for {repository} has no tag_name")
    if not isinstance(html_url, str) or not html_url.startswith("https://github.com/"):
        raise RuntimeError(f"Latest release for {repository} has no valid html_url")
    return {"tag": tag, "url": html_url}


def replace_block(document: str, name: str, body: str) -> str:
    start = f"<!-- AUTO:{name}:START -->"
    end = f"<!-- AUTO:{name}:END -->"

    if document.count(start) != 1 or document.count(end) != 1:
        raise RuntimeError(f"Expected exactly one {name} marker pair in README.md")

    before, remainder = document.split(start, 1)
    _, after = remainder.split(end, 1)
    return f"{before}{start}\n{body.rstrip()}\n{end}{after}"


def project_meta(release: dict, status: str) -> str:
    return f"[`{release['tag']}`]({release['url']}) · `{status}`"


def build_now(status: dict) -> str:
    profile = status["profile"]
    projects = status["projects"]
    research = status["research"]

    return "\n".join(
        [
            f"<sub>Current public focus · {profile['as_of']}</sub>",
            "",
            f"- **TEO:** {projects['teo']['focus']}",
            f"- **GroX:** {projects['grox']['focus']}",
            f"- **Research:** {research['focus']}",
        ]
    )


def regenerate() -> str:
    status = load_status()
    projects = status["projects"]

    teo_repo = projects["teo"]["repository"]
    grox_repo = projects["grox"]["repository"]

    # Validate configured repositories before making any network request.
    for repository in (teo_repo, grox_repo):
        if repository not in ALLOWED_REPOSITORIES:
            raise ValueError(f"Repository is not allowlisted: {repository}")

    teo_release = latest_release(teo_repo)
    grox_release = latest_release(grox_repo)

    document = README.read_text(encoding="utf-8")
    document = replace_block(
        document,
        "TEO_META",
        project_meta(teo_release, projects["teo"]["status"]),
    )
    document = replace_block(
        document,
        "GROX_META",
        project_meta(grox_release, projects["grox"]["status"]),
    )
    document = replace_block(document, "NOW", build_now(status))
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 when README.md would change.",
    )
    args = parser.parse_args()

    try:
        current = README.read_text(encoding="utf-8")
        generated = regenerate()
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"profile regeneration failed: {exc}", file=sys.stderr)
        return 2

    if generated == current:
        print("README.md is already current")
        return 0

    if args.check:
        print("README.md is stale")
        return 1

    README.write_text(generated, encoding="utf-8")
    print("README.md regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
