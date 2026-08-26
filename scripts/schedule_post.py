"""Verify the slide URLs are publicly live, then schedule the carousel.

The ordering here is the whole point of the GitHub Actions design: Metricool has
no media-upload endpoint, so it fetches the images over anonymous HTTPS. If we
schedule before the push has propagated to raw.githubusercontent.com, Metricool
silently gets 404s. So every URL is polled to a real HTTP 200 first, and the run
fails loudly rather than scheduling a post with broken media.

    python scripts/schedule_post.py --day 2026-08-25 --repo owner/name \
        [--ref main] [--draft true] [--at 09:00]
"""

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import metricool

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/slides/{day}/{name}"


def wait_for_200(url, attempts=10, delay=6):
    """Poll until the CDN serves the file. Returns (ok, status, elapsed)."""
    start = time.time()
    last = None
    for n in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200 and int(r.headers.get("Content-Length") or 1) > 0:
                    return True, 200, round(time.time() - start, 1)
                last = r.status
        except urllib.error.HTTPError as e:
            last = e.code
        except Exception as e:                      # DNS/TLS/transient
            last = repr(e)[:60]
        if n < attempts:
            print(f"  [wait] {last} — retry {n}/{attempts} in {delay}s")
            time.sleep(delay)
    return False, last, round(time.time() - start, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--draft", default="true")
    ap.add_argument("--at", default="09:00", help="Pacific HH:MM")
    ap.add_argument("--networks", default="instagram")
    args = ap.parse_args()

    draft = str(args.draft).lower() not in ("false", "0", "no")
    day = date.fromisoformat(args.day)
    outdir = pathlib.Path("slides") / day.isoformat()
    manifest = json.loads((outdir / "manifest.json").read_text())

    slides = manifest["slides"]
    if len(slides) > 10:
        # Instagram carousels cap at 10; trim rather than let Metricool reject it.
        print(f"[schedule] trimming {len(slides)} slides to Instagram's max of 10")
        slides = slides[:10]

    urls = [RAW.format(repo=args.repo, ref=args.ref, day=day.isoformat(), name=nm)
            for nm in slides]

    print(f"[schedule] verifying {len(urls)} public URL(s) before scheduling")
    bad = []
    for u in urls:
        ok, status, secs = wait_for_200(u)
        print(f"  {'OK  ' if ok else 'FAIL'} {status} ({secs}s) {u}")
        if not ok:
            bad.append((u, status))
    if bad:
        print("\n[schedule] ABORTING — Metricool would fetch 404s and the post "
              "would publish with missing images.")
        for u, s in bad:
            print(f"  {s}  {u}")
        sys.exit(1)

    # Target 9am Pacific. If that has already passed today, use tomorrow.
    hh, mm = (int(x) for x in args.at.split(":"))
    now = datetime.now(metricool.PACIFIC)
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when <= now + timedelta(minutes=5):
        when = when + timedelta(days=1)
    publish_at = when.strftime("%Y-%m-%dT%H:%M:%S")

    networks = tuple(n.strip() for n in args.networks.split(",") if n.strip())
    body = metricool.build_carousel_post(
        text=manifest["caption"], media_urls=urls,
        publish_at=publish_at, networks=networks, draft=draft,
    )
    print(f"[schedule] {'DRAFT' if draft else 'LIVE AUTO-PUBLISH'} "
          f"-> {networks} at {publish_at} Pacific, {len(urls)} images")

    st, resp = metricool.schedule(body)
    print(f"[schedule] HTTP {st}")
    print(json.dumps(resp, indent=2)[:1200])
    if st not in (200, 201):
        sys.exit(f"[schedule] Metricool rejected the post: HTTP {st}")

    pid = ((resp or {}).get("data") or {}).get("id")
    print(f"SCHEDULED_ID={pid}")
    print(f"SCHEDULED_AT={publish_at}")


if __name__ == "__main__":
    main()
