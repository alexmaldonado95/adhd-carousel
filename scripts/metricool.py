"""Metricool client for the ADHD carousel.

Contract verified against https://app.metricool.com/api/swagger.json and against
the live API on 2026-08-26.

Two gotchas encoded here, both verified rather than assumed:

1. GET /v2/analytics/posts/threads filters by the `timezone` you pass, but the
   `publishedDate.dateTime` it returns is stamped in the ACCOUNT's reporting
   timezone — Europe/Madrid for this account, not UTC and not Pacific. A post
   that reads 2026-08-26T04:02 Madrid is 2026-08-25 19:02 Pacific. Rendering the
   raw string would mislabel roughly a third of every day's slides.
2. `providers` entries are objects ({"network": "instagram"}), not strings.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "https://app.metricool.com/api"
USER_ID = int(os.environ.get("MC_USER_ID", 2761513))
BLOG_ID = int(os.environ.get("MC_BLOG_ID", 5333281))  # ADHD - Alex Maldonado

PACIFIC = ZoneInfo("America/Los_Angeles")
# Fallback only. The real value is read per-response from publishedDate.timezone.
REPORTING_TZ = ZoneInfo("Europe/Madrid")


def token():
    tok = os.environ.get("METRICOOL_TOKEN")
    if tok:
        return tok.strip()
    path = os.path.expanduser("~/.metricool_api_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    raise SystemExit("No Metricool token: set METRICOOL_TOKEN or ~/.metricool_api_key")


def _call(method, path, params=None, body=None):
    q = {"userId": USER_ID, "blogId": BLOG_ID, **(params or {})}
    url = f"{BASE}{path}?{urllib.parse.urlencode(q)}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Mc-Auth", token())
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:800]}


def _to_pacific(published):
    """publishedDate -> aware Pacific datetime. See gotcha 1 in the module docstring."""
    if not published or not published.get("dateTime"):
        return None
    naive = datetime.fromisoformat(published["dateTime"])
    try:
        src = ZoneInfo(published.get("timezone") or "Europe/Madrid")
    except Exception:
        src = REPORTING_TZ
    return naive.replace(tzinfo=src).astimezone(PACIFIC)


def top_threads_posts(day=None, limit=6, min_views=1):
    """Ranked Threads posts for one Pacific calendar day.

    Returns (day_date, [post, ...]) sorted by views desc. Each post carries a
    `pacific` datetime and the raw Metricool metrics. Never fabricates rows.
    """
    if day is None:
        day = (datetime.now(PACIFIC) - timedelta(days=1)).date()

    st, data = _call("GET", "/v2/analytics/posts/threads", params={
        "from": f"{day.isoformat()}T00:00:00",
        "to": f"{day.isoformat()}T23:59:59",
        "timezone": "America/Los_Angeles",
    })
    if st != 200:
        raise SystemExit(f"Threads analytics failed: HTTP {st} {json.dumps(data)[:300]}")

    rows = []
    for p in (data or {}).get("data") or []:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        pac = _to_pacific(p.get("publishedDate"))
        # The API window is inclusive at the edges in the account's own tz, so a
        # post can land just outside the Pacific day. Drop those rather than
        # labelling a slide with the wrong date.
        if pac is None or pac.date() != day:
            continue
        views = p.get("views") or 0
        if views < min_views:
            continue
        rows.append({
            "text": text,
            "views": views,
            "likes": p.get("likes") or 0,
            "replies": p.get("replies") or 0,
            "reposts": p.get("reposts") or 0,
            "permalink": p.get("permalink") or "",
            "shortCode": p.get("shortCode") or "",
            "pacific": pac,
        })

    rows.sort(key=lambda r: (-r["views"], -r["likes"], r["pacific"]))
    return day, rows[:limit]


def build_carousel_post(text, media_urls, publish_at, networks=("instagram",), draft=True):
    """Assemble a ScheduledPost for an image carousel.

    saveExternalMediaFiles=True makes Metricool copy the images to its own CDN at
    schedule time, so the post survives the GitHub repo changing later. Keep it.
    """
    body = {
        "text": text,
        "publicationDate": {
            "dateTime": publish_at,
            "timezone": "America/Los_Angeles",
        },
        "providers": [{"network": n} for n in networks],
        "media": list(media_urls),
        "saveExternalMediaFiles": True,
        "draft": draft,
        "autoPublish": not draft,
        "shortener": False,
    }
    if "instagram" in networks:
        body["instagramData"] = {"autoPublish": not draft, "type": "POST"}
    if "threads" in networks:
        body["threadsData"] = {"replyControl": "EVERYONE"}
    if "tiktok" in networks:
        # These slides are programmatically rendered text cards, not synthetic
        # media depicting a real person, so TikTok's AIGC disclosure does not
        # apply the way it does to the AI-twin video pipeline. Flip to True if
        # this ever carries generated imagery.
        body["tiktokData"] = {"isAigc": False, "privacyOption": "PUBLIC_TO_EVERYONE"}
    return body


def schedule(post_body):
    return _call("POST", "/v2/scheduler/posts", body=post_body)


def scheduled_posts(start, end):
    return _call("GET", "/v2/scheduler/posts", params={"start": start, "end": end})
