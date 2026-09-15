"""The used-posts ledger shared with the alexmaldonado95/carousel pipeline.

Both pipelines build carousels out of the same pool - @the.alexmaldonado's
published Threads posts - so without a shared memory they repeat each other.
That pipeline already keeps a ledger of every post it has used, on the `media`
branch of its own repo, and skips anything listed there. This module lets this
pipeline read the same file and add to it, so "used once" holds across both.

Reading needs nothing: the repo is public. Writing needs a token that can push
to the OTHER repo, which the workflow's GITHUB_TOKEN cannot do - set the
LEDGER_TOKEN secret to a PAT with `contents: write` on alexmaldonado95/carousel.
Without it the read-side skip still works and registration is skipped with a
warning, so a missing token degrades the guarantee instead of failing the run.

The key format is copied from that pipeline verbatim. If it ever changes there,
it has to change here too or the two stop recognising each other's entries.
"""
from __future__ import annotations

import base64
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

from brand import HANDLE

API = "https://api.github.com"
REPO = os.environ.get("LEDGER_REPO", "alexmaldonado95/carousel")
REF = os.environ.get("LEDGER_REF", "media")
PATH = f"used/{HANDLE}.json"
# LEDGER_TOKEN can write to the other repo. GITHUB_TOKEN cannot, but it can
# READ a public one, and an authenticated read is not subject to the 60/hr
# per-IP cap that unauthenticated calls from Actions runners share.
TOKEN = os.environ.get("LEDGER_TOKEN", "")
READ_TOKEN = TOKEN or os.environ.get("GITHUB_TOKEN", "")


# ---------------------------------------------------------------------------
# Copied verbatim from standalone.py in the carousel repo. The ledger key is
# whatever clean_for_slide() leaves behind, so anything less than a faithful
# copy produces keys that repo does not recognise and the dedupe silently stops
# working. check_key_drift() below is the alarm for exactly that.
SIGNATURE_MARKERS = (
    "\u2014 alex maldonado, circle real estate",
    "- alex maldonado, circle real estate",
    "alex maldonado | circle real estate",
)

BAIT_SUFFIXES = (
    "this hit.", "this hit", "anyone else?", "anyone else feel this?",
    "relatable?", "you feel this too?", "this one's personal.",
    "drop a if you get this.", "drop a if you get this",
    "be honest \u2014 this one's you too, right?", "same.", "let's connect!",
    "who's with me?", "tell me i'm not alone.",
)


def straighten(text: str) -> str:
    return (text.replace("\u2019", "'").replace("\u2018", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))


def strip_emoji(text: str) -> str:
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        cp = ord(ch)
        pictographic = (
            0x1F000 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x27BF
            or 0xFE00 <= cp <= 0xFE0F
            or 0x1F1E6 <= cp <= 0x1F1FF
            or cp in (0x200D, 0x20E3, 0x2B50, 0x2B06, 0x2B07)
        )
        if pictographic or cat == "So":
            continue
        out.append(ch)
    return "".join(out)


def clean_for_slide(text: str) -> str:
    t = straighten(text)
    for marker in SIGNATURE_MARKERS:
        idx = t.lower().find(marker)
        if idx != -1:
            t = t[:idx]
    t = strip_emoji(t)
    t = re.sub(r"#\w+", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = t.replace("*", "")
    t = re.sub(r"\s+", " ", t).strip()

    changed = True
    while changed:
        changed = False
        low = t.lower().rstrip()
        for bait in BAIT_SUFFIXES:
            if low.endswith(bait):
                t = t[: len(t) - len(bait)].rstrip()
                changed = True
                break

    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(" -\u2013\u2014|\u00b7,")
    return t


def normalize_key(text: str) -> str:
    t = clean_for_slide(text).lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return " ".join(t.split()[:12])


def _reduced(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_key(text))


def is_used(text: str, used_keys) -> bool:
    """Exact key match, then a looser one.

    The two pipelines occasionally read slightly different stored text for the
    same post (a lead-in like "Real talk:" present in one and not the other),
    which lands them on different keys. Falling back to a spacing- and
    punctuation-free containment check catches that without needing the two
    cleaners to agree character for character.
    """
    key = normalize_key(text)
    if key in used_keys:
        return True
    red = _reduced(text)
    if len(red) < 24:            # too short to match on safely
        return False
    return any(red in _reduced(k) or _reduced(k) in red for k in used_keys)


def check_key_drift(sample_keys) -> None:
    """Warn if this copy has drifted from the one that wrote the ledger.

    Entries whose source post this pipeline also saw should key identically. If
    they stop doing so, the two pipelines have quietly stopped recognising each
    other - louder to say so than to post duplicates for a fortnight.
    """
    if not sample_keys:
        return
    malformed = [k for k in sample_keys
                 if k != " ".join(k.split()[:12]) or re.search(r"[^a-z0-9 ]", k)]
    if malformed:
        print(f"[ledger] WARNING: {len(malformed)} ledger key(s) do not match "
              f"this pipeline's key format - the copied normalizer in "
              f"scripts/ledger.py has drifted from the carousel repo")


def _request(method: str, url: str, body: dict | None = None):
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    auth = READ_TOKEN if method == "GET" else TOKEN
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    req = urllib.request.Request(
        url, method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"detail": e.read().decode(errors="replace")[:300]}
    except Exception as exc:  # noqa: BLE001 - never fail a run over the ledger
        return 0, {"detail": str(exc)}


def load() -> tuple[set[str], list[dict], str | None]:
    """(keys, entries, blob sha). Unreadable is treated as empty: skipping the
    dedupe is a worse day than posting a repeat, but it is not worth a failure."""
    status, data = _request(
        "GET", f"{API}/repos/{REPO}/contents/{PATH}?ref={REF}")
    if status != 200 or "content" not in data:
        print(f"[ledger] could not read {REPO}/{PATH}@{REF} "
              f"(HTTP {status}) - treating it as empty")
        return set(), [], None
    try:
        raw = base64.b64decode(data["content"]).decode("utf-8")
        # The file is {"entries": [...]} - NOT a bare list. Reading it as a list
        # silently yields nothing and the dedupe quietly stops working.
        entries = json.loads(raw).get("entries", [])
        entries = [e for e in entries if isinstance(e, dict) and e.get("key")]
    except Exception as exc:  # noqa: BLE001
        print(f"[ledger] {PATH} is unreadable ({exc}) - treating it as empty")
        return set(), [], None
    print(f"[ledger] {len(entries)} post(s) already used across both pipelines")
    return {e["key"] for e in entries}, entries, data.get("sha")


def register(keys: list[str], day: str) -> bool:
    """Add keys to the shared ledger. Returns False when nothing was written."""
    keys = [k for k in dict.fromkeys(keys) if k]
    if not keys:
        return False
    if not TOKEN:
        print(f"[ledger] LEDGER_TOKEN is not set - {len(keys)} post(s) went out "
              f"WITHOUT being registered; the 6pm carousel may reuse them")
        return False

    # Re-read immediately before writing so a run that raced us is not clobbered.
    existing_keys, entries, sha = load()
    added = [k for k in keys if k not in existing_keys]
    if not added:
        print("[ledger] every post was already registered")
        return True

    entries = entries + [{"key": k, "day": day} for k in added]
    # Byte-for-byte the shape save_ledger() writes in the carousel repo, so the
    # two pipelines never fight over formatting. Pruning is left to that
    # pipeline, which drops entries past its own retention window on each write.
    blob = json.dumps({"entries": entries}, indent=1, ensure_ascii=False) + "\n"
    body = {
        "message": f"ledger: {len(added)} post(s) used by the 9am carousel {day}",
        "content": base64.b64encode(blob.encode("utf-8")).decode("ascii"),
        "branch": REF,
    }
    if sha:
        body["sha"] = sha

    status, data = _request(
        "PUT", f"{API}/repos/{REPO}/contents/{PATH}", body=body)
    if status not in (200, 201):
        print(f"[ledger] could not write the ledger (HTTP {status} "
              f"{data.get('detail','')}) - the post still went out")
        return False
    print(f"[ledger] registered {len(added)} post(s)")
    return True
