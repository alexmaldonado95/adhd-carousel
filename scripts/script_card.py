"""Daily script card: the ADHD pipeline's long-form script as an IG + TikTok image post.

The script pipeline (private repo adhd-twin) schedules one long-form script to
Threads every day around midday Pacific. Threads takes it as text; Instagram
and TikTok require an image. This job closes that gap without needing read
access to the private repo: it finds today's long-form post in the Metricool
scheduler (the only Threads post over LONG_FORM_MIN chars — the autolists post
one-liners), renders it as a single quote card in the approved brand style,
and schedules the card to Instagram and TikTok.

    python scripts/script_card.py                 find, render, schedule (draft)
    python scripts/script_card.py --render-only   find + render, schedule nothing
    python scripts/script_card.py --draft false   schedule for real

The workflow commits the rendered card before scheduling, exactly like the
carousel: Metricool fetches media over public raw.githubusercontent.com URLs.
"""

import argparse
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import metricool
import render
from brand import COLORS, DISPLAY, HANDLE

LONG_FORM_MIN = 350          # autolist one-liners are far below this
POST_AT_DEFAULT = "16:00"    # free slot: recap posts 9am, TikTok recycler 6pm
HASHTAGS = ("#ADHD #ADHDawareness #Neurodivergent #ADHDinAdults "
            "#ADHDbrain #adhdtiktok #ActuallyADHD")

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/slides/{day}/{name}"

# Never mistake this job's own output (or the recap carousel) for the script.
SELF_MARKERS = ("yesterday on threads", "swipe for the full countdown")


# ---------------------------------------------------------------- find script
def _texts_from_scheduler(day):
    """Threads texts scheduled for the given Pacific day, longest first."""
    st, data = metricool.scheduled_posts(f"{day}T00:00:00", f"{day}T23:59:59")
    if st != 200:
        print(f"[find] scheduler list -> HTTP {st}; falling back to analytics")
        return []
    rows = data if isinstance(data, list) else (data or {}).get("data") or []
    out = []
    for p in rows:
        nets = {pr.get("network") for pr in p.get("providers") or []}
        if "threads" not in nets or p.get("draft"):
            continue
        text = (p.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def _texts_from_analytics(day):
    """Already-published Threads texts for the day (late runs)."""
    try:
        from datetime import date as _date
        _, posts = metricool.top_threads_posts(
            day=_date.fromisoformat(day), limit=50, min_views=0)
        return [p["text"] for p in posts]
    except SystemExit as e:
        print(f"[find] analytics fallback failed: {e}")
        return []


def find_script(day):
    """Today's long-form pipeline script, or None with a printed reason."""
    candidates = _texts_from_scheduler(day) + _texts_from_analytics(day)
    seen, keep = set(), []
    for t in candidates:
        key = t[:80]
        if key in seen:
            continue
        seen.add(key)
        low = t.lower()
        if len(t) < LONG_FORM_MIN or any(m in low for m in SELF_MARKERS):
            continue
        keep.append(t)
    if not keep:
        print(f"[find] no long-form (>= {LONG_FORM_MIN} chars) Threads post for "
              f"{day} — the pipeline may not have scheduled one yet.")
        return None
    keep.sort(key=len, reverse=True)
    return keep[0]


# ---------------------------------------------------------------- render card
def script_slide(text):
    """One 1080x1350 card in the approved brand tokens: hook up top, the full
    script in the raised card. No metrics row — this is the day's message, not
    a recap."""
    size = 46 if len(text) <= 300 else 42 if len(text) <= 420 else 36
    first, _, rest = text.partition(". ")
    hook, body = (first + ".", rest) if rest else (None, text)

    css = f"""
.k {{ font-family:{DISPLAY}; font-size:64px; line-height:1.08; font-weight:700;
      letter-spacing:-.025em; margin-top:10px; }}
.card {{ background:{COLORS['surface']}; border:2px solid {COLORS['line']};
         border-radius:34px; padding:56px 52px; margin-top:40px; }}
.quote {{ font-size:{size}px; line-height:1.38; font-weight:600; letter-spacing:-.012em;
          color:{COLORS['text']}; }}
.glow {{ position:absolute; top:-220px; right:-200px; width:700px; height:700px;
         border-radius:50%; filter:blur(120px); opacity:.26;
         background:radial-gradient(circle,{COLORS['accent2']},transparent 68%); }}
"""
    hook_html = f'<div class="k">{html.escape(hook)}</div>' if hook else ""
    body_html = html.escape(body)
    body_doc = f"""<div class="glow"></div>
<div class="head"><div class="eyebrow">Today's post</div>
<div class="handle">@{HANDLE}</div></div>
{hook_html}
<div class="spacer"></div>
<div class="card"><div class="quote">{body_html}</div></div>
<div class="spacer"></div>
<div class="foot"><div>@{HANDLE}</div><div>Threads &middot; Instagram &middot; TikTok</div></div>"""
    return render._page(body_doc, css)


def caption_for(text):
    first = text.split(". ")[0].strip()
    if not first.endswith((".", "?", "!")):
        first += "."
    return "\n".join([first, "",
                      f"Full post on my Threads — @{HANDLE}. I write one of "
                      "these every day.", "", HASHTAGS])


# ---------------------------------------------------------------- publish
def wait_for_200(url, attempts=10, delay=6):
    last = None
    for n in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200 and int(r.headers.get("Content-Length") or 1) > 0:
                    return True
                last = r.status
        except urllib.error.HTTPError as e:
            last = e.code
        except Exception as e:  # noqa: BLE001 — DNS/TLS/transient
            last = repr(e)[:60]
        if n < attempts:
            print(f"  [wait] {last} — retry {n}/{attempts} in {delay}s")
            time.sleep(delay)
    print(f"[publish] {url} never returned 200 (last: {last})")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None, help="Pacific date YYYY-MM-DD (default today)")
    ap.add_argument("--at", default=POST_AT_DEFAULT, help="Pacific HH:MM to publish")
    ap.add_argument("--repo", default=None, help="owner/name hosting the slides")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--networks", default="instagram,tiktok")
    ap.add_argument("--draft", default="true", choices=("true", "false"))
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--outdir", default="slides")
    args = ap.parse_args()

    day = args.day or datetime.now(metricool.PACIFIC).date().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        sys.exit(f"bad --day {day!r}")

    text = find_script(day)
    if text is None:
        sys.exit(2)   # loud, distinct: nothing to post today
    print(f"[find] script ({len(text)} chars): {text[:90]!r}...")

    outdir = pathlib.Path(args.outdir) / f"script-{day}"
    written = render.render_all([script_slide(text)], outdir)
    print(f"[render] {written[0]}")
    print("SCRIPT_DAY=script-" + day)

    if args.render_only:
        return
    if not args.repo:
        sys.exit("--repo owner/name is required to schedule (media must be public)")

    url = RAW.format(repo=args.repo, ref=args.ref, day=f"script-{day}",
                     name=written[0].name)
    if not wait_for_200(url):
        sys.exit(1)

    networks = tuple(n.strip() for n in args.networks.split(",") if n.strip())
    body = metricool.build_carousel_post(
        caption_for(text), [url], f"{day}T{args.at}:00",
        networks=networks, draft=(args.draft == "true"))
    st, resp = metricool.schedule(body)
    if st not in (200, 201):
        sys.exit(f"[schedule] HTTP {st}: {json.dumps(resp)[:400]}")
    print(f"[schedule] {'draft' if args.draft == 'true' else 'LIVE'} "
          f"{'+'.join(networks)} at {day} {args.at} PT")


if __name__ == "__main__":
    main()
