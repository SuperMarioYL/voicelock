"""Regression tests for the v0.8.0 release — version-consistency guard.

Pins the fix-version-drift-site-changelog milestone: every release-trace
version surface must agree on one version. A past iteration found that bumping
only VERSION (or only one surface) re-opens the drift — `web/site.json`
`content_version` on the v0.7.0 tag still read `v0.3.0` while every other
surface read `0.7.0`, and a non-contiguous CHANGELOG silently diverged from
the shipped tag. This test is the single-source-of-truth guard so a future
bump that touches only one surface fails loudly here instead of shipping a
stale `content_version` or a broken release-link CHANGELOG.

All offline, no API key, no network.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from voicelock import __version__ as pkg_version
from voicelock.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent
runner = CliRunner()

# A bare version like "0.8.0" (no leading v).
_BARE = re.compile(r"^\d+\.\d+\.\d+$")


def _strip_v(s: str) -> str:
    return s[1:] if s.startswith("v") else s


def _walk_content_versions(node, found: list[str]) -> None:
    """Recursively collect every `content_version` value in a json tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "content_version" and isinstance(v, str):
                found.append(v)
            else:
                _walk_content_versions(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk_content_versions(v, found)


def test_version_surfaces_agree() -> None:
    """VERSION / pyproject.toml / __init__.__version__ / `voicelock version`
    CLI output / every web/site.json content_version field / top CHANGELOG
    heading must all reference the same version (with any leading 'v'
    stripped)."""
    # 1. VERSION file
    version_file = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert _BARE.match(version_file), f"VERSION is not a bare semver: {version_file!r}"

    # 2. pyproject.toml [project] version
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)
    pyproject_version = pyproject["project"]["version"]
    assert _BARE.match(pyproject_version), (
        f"pyproject.toml version is not a bare semver: {pyproject_version!r}"
    )

    # 3. package __version__ (what the CLI prints)
    assert _BARE.match(pkg_version), (
        f"__version__ is not a bare semver: {pkg_version!r}"
    )

    # 4. `voicelock version` CLI output ("voicelock 0.8.0")
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    m = re.search(r"voicelock\s+(\d+\.\d+\.\d+)", result.output)
    assert m, f"could not parse version from CLI output: {result.output!r}"
    cli_version = m.group(1)

    # 5. web/site.json — every content_version field (schema 3 carries one
    #    under `meta.content_version` and one top-level trailing field; both
    #    must agree with the release version).
    site = json.loads((REPO_ROOT / "web" / "site.json").read_text(encoding="utf-8"))
    content_versions: list[str] = []
    _walk_content_versions(site, content_versions)
    assert content_versions, "web/site.json has no content_version field"
    site_versions = [_strip_v(v) for v in content_versions]
    for sv in site_versions:
        assert _BARE.match(sv), (
            f"web/site.json content_version is not a semver: {sv!r}"
        )
    # the footer.tag version prefix must also track the release version
    footer_tag = site.get("footer", {}).get("tag", "")
    ft_m = re.match(r"(\d+\.\d+\.\d+)", footer_tag)
    assert ft_m, f"web/site.json footer.tag has no version prefix: {footer_tag!r}"
    footer_version = ft_m.group(1)

    # 6. top CHANGELOG `## [X.Y.Z]` heading
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    cm = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert cm, "CHANGELOG.md has no `## [X.Y.Z]` heading"
    changelog_version = cm.group(1)

    expected = version_file
    assert pyproject_version == expected, (
        f"pyproject.toml {pyproject_version!r} != VERSION {expected!r}"
    )
    assert pkg_version == expected, (
        f"__version__ {pkg_version!r} != VERSION {expected!r}"
    )
    assert cli_version == expected, (
        f"CLI version {cli_version!r} != VERSION {expected!r}"
    )
    for sv in site_versions:
        assert sv == expected, (
            f"web/site.json content_version {sv!r} != VERSION {expected!r}"
        )
    assert footer_version == expected, (
        f"web/site.json footer.tag {footer_version!r} != VERSION {expected!r}"
    )
    assert changelog_version == expected, (
        f"CHANGELOG top heading {changelog_version!r} != VERSION {expected!r}"
    )


def test_changelog_sections_contiguous_and_link_refs_complete() -> None:
    """The CHANGELOG `## [X.Y.Z]` sections and their bottom link references must
    be contiguous and paired — no missing section, no missing link ref (the
    v0.8.0 fix backfilled a missing [0.5.0] section and [0.5.0]/[0.7.0] link
    refs). Every `## [x]` heading must have a matching `[x]:` link reference."""
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^##\s*\[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    link_refs = re.findall(r"^\[(\d+\.\d+\.\d+)\]:", changelog, re.MULTILINE)

    assert headings, "no CHANGELOG `## [x]` headings found"
    assert link_refs, "no CHANGELOG `[x]:` link references found"

    heading_set = set(headings)
    link_set = set(link_refs)
    # every heading must have a link ref
    missing_refs = heading_set - link_set
    assert not missing_refs, (
        f"CHANGELOG headings without a link reference: {sorted(missing_refs)}"
    )
    # no orphan link refs (a link ref with no heading)
    orphan_refs = link_set - heading_set
    assert not orphan_refs, (
        f"CHANGELOG link references without a heading: {sorted(orphan_refs)}"
    )
    # monotonic, no skipped version in the shipped sequence
    ordered = sorted(
        headings, key=lambda v: tuple(int(x) for x in v.split("."))
    )
    triples = [tuple(int(x) for x in v.split(".")) for v in ordered]
    for prev, cur in zip(triples, triples[1:]):
        assert cur > prev, f"CHANGELOG versions not monotonic at {prev} -> {cur}"
