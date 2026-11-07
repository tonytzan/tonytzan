#!/usr/bin/env python3
"""Compare the facts in README.md (and assets/harness.svg) with the portfolio site.

Exit codes: 0 = in sync, 1 = drift found (report written), 2 = could not read the site.
Usage: check_site_drift.py [--site URL_OR_FILE] [--report FILE]
"""
import argparse
import html
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SITE = "https://tonytzan.github.io/"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip().lower()


def load_site(src: str) -> str:
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "readme-site-drift-check"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    return Path(src).read_text(encoding="utf-8")


def section(text: str, start_re: str, end_re: str) -> str:
    m = re.search(start_re, text)
    if not m:
        return ""
    rest = text[m.end():]
    e = re.search(end_re, rest)
    return rest[: e.start()] if e else rest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=DEFAULT_SITE)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    try:
        site = load_site(args.site)
    except Exception as exc:  # network or file problem: not drift
        print(f"could not read the site ({args.site}): {exc}", file=sys.stderr)
        return 2

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    harness_svg = (ROOT / "assets" / "harness.svg").read_text(encoding="utf-8")
    readme_n, harness_n = norm(readme), norm(harness_svg)
    problems: list[str] = []

    # 1. role title
    m = re.search(r"<title>(.*?)</title>", site, re.S)
    role = html.unescape(m.group(1)).split("—")[-1].strip() if m else ""
    if not role:
        problems.append("Could not find the site title, so the role line was not checked.")
    elif norm(role) not in readme_n:
        problems.append(f"Role/title: the site says **{role}**, but the README does not contain it.")

    # 2. headline metrics (proof strip)
    proof = section(site, r'<section class="proof"[^>]*>', r"</section>")
    for value, label in re.findall(r"<b>(.*?)</b><span>(.*?)</span>", proof):
        if norm(value) not in readme_n:
            problems.append(f"Metric: the site shows **{html.unescape(value)}** ({html.unescape(label)}); it is missing from the README.")

    # 3. projects, both directions
    work = section(site, r'<section id="work"[^>]*>', r"</section>")
    site_projects = [html.unescape(p).strip() for p in re.findall(r"<h3>(?:<img[^>]*>)?(?:<a[^>]*>)?([^<]+)", work)]
    cards = section(readme, r"###\s+`~/projects`", r"\n---")
    readme_projects = [html.unescape(p).strip() for p in re.findall(r"<strong>([^<]+)</strong>", cards)]
    for p in site_projects:
        if norm(p) not in {norm(x) for x in readme_projects}:
            problems.append(f"Project: **{p}** is on the site but has no card in the README.")
    for p in readme_projects:
        if norm(p) not in {norm(x) for x in site_projects}:
            problems.append(f"Project: **{p}** has a card in the README but is no longer on the site.")
    if not site_projects:
        problems.append("Could not read the project list from the site; the project check was skipped.")

    # 4. harness steps (shown in assets/harness.svg)
    for _label, title in re.findall(r'<div class="step[^"]*"[^>]*><small>(.*?)</small><b>(.*?)</b>', site):
        if norm(title) not in harness_n:
            problems.append(f"Harness step: **{html.unescape(title)}** is on the site but not in assets/harness.svg.")

    # 5. harness receipts
    receipts = section(site, r'class="receipts"', r"</section>")
    for value, label in re.findall(r"<div><b>(.*?)</b><span>(.*?)</span></div>", receipts):
        v = html.unescape(value).strip()
        if re.search(r"\d", v) and f"**{v}**" not in readme:
            problems.append(f"Receipts: the site shows **{v}** ({html.unescape(label)}); the README does not have it in bold.")

    if not problems:
        print("README and assets match the site.")
        return 0

    body = (
        "The README looks out of sync with the portfolio site "
        f"(<{args.site}>).\n\n"
        + "\n".join(f"- {p}" for p in problems)
        + "\n\nUpdate `README.md` / `assets/harness.svg`, or adjust `.github/scripts/check_site_drift.py` "
        "if the difference is intentional. This issue closes itself once the check passes.\n"
    )
    print(body)
    if args.report:
        Path(args.report).write_text(body, encoding="utf-8")
    return 1


if __name__ == "__main__":
    sys.exit(main())
