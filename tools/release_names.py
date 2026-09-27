"""What a release's file and tag are called, and whether an address agrees with them.

Shared by sign_release.py (which refuses to sign a manifest that disagrees) and
check_release.py (which says so before it even tries the download). One copy, so the two
cannot drift apart and let something through.
"""
from __future__ import annotations

# A GitHub release download address looks like
#     https://github.com/<owner>/<repo>/releases/download/<tag>/<file>
# so the version appears TWICE, and both halves have to be right. Checking only the file name
# lets .../download/vN/salaah-1.20.zip through: the manifest then verifies, the mat trusts it,
# and the download 404s from a tag that was never created. That happened.
MARK = "/releases/download/"

# The runbook uses N as a stand-in for the version. Pasted literally it makes a plausible-looking
# address. Named as a placeholder, it is obvious; unnamed, it costs an evening.
PLACEHOLDERS = ("N", "VN", "SALAAH-N.ZIP")


def zip_name(number: str) -> str:
    return f"salaah-{number}.zip"


def tag_name(number: str) -> str:
    return f"v{number}"


def wanted_tail(number: str) -> str:
    return f"{tag_name(number)}/{zip_name(number)}"


def url_complaint(url: str, number: str) -> str:
    """Empty if the address matches this build, otherwise the reason it does not."""
    tail = url.rstrip("/")
    for part in tail.split("/"):
        if part.upper() in PLACEHOLDERS:
            return (f"That address still has {part} in it -- the placeholder from the runbook, "
                    f"not a version. This build is {number}.")
    if MARK in tail:
        after = tail.split(MARK, 1)[1]
        if after != wanted_tail(number):
            return (f"That address ends in {after}, but this build needs {wanted_tail(number)}.\n"
                    "(The version appears twice in a release address: once as the tag, once as "
                    "the file. Both have to be right.)")
        return ""
    asked = tail.rsplit("/", 1)[-1]
    if asked != zip_name(number):
        return f"That address ends in {asked}, but this build is {zip_name(number)}."
    return ""
