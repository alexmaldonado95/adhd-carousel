"""Render carousel slides to 1080x1350 JPG via headless Chromium.

HTML/CSS is the layout engine; Playwright is only a camera. Fonts are awaited
(document.fonts.ready) before the shutter so a slow CDN can't capture a
half-laid-out slide.
"""

import html
import pathlib

from brand import COLORS, DISPLAY, EYEBROWS, FONT_CSS, H, HANDLE, SANS, W

BASE_CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{W}px; height:{H}px; overflow:hidden; }}
body {{
  position:relative;
  background:{COLORS['ink']}; color:{COLORS['text']};
  font-family:{SANS}; -webkit-font-smoothing:antialiased;
  display:flex; flex-direction:column;
  padding:86px 80px 72px;
}}
.eyebrow {{
  font-size:26px; font-weight:800; letter-spacing:.22em; text-transform:uppercase;
  color:{COLORS['accent']};
}}
.handle {{ font-size:26px; font-weight:600; color:{COLORS['muted']}; letter-spacing:.02em; }}
.head {{ display:flex; justify-content:space-between; align-items:baseline; }}
.spacer {{ flex:1; }}
.rule {{ height:2px; background:{COLORS['line']}; margin:34px 0; }}
.foot {{ display:flex; justify-content:space-between; align-items:center;
         font-size:24px; color:{COLORS['muted']}; font-weight:600; }}
.dots {{ display:flex; gap:9px; }}
.dot {{ width:9px; height:9px; border-radius:50%; background:{COLORS['line']}; }}
.dot.on {{ background:{COLORS['accent']}; }}
"""


def _dots(i, n):
    return '<div class="dots">' + "".join(
        f'<div class="dot{" on" if k == i else ""}"></div>' for k in range(n)
    ) + "</div>"


def _page(body_html, extra_css=""):
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{FONT_CSS}">
<style>{BASE_CSS}{extra_css}</style></head><body>{body_html}</body></html>"""


def cover_slide(day_label, total_posts, top_views, i, n):
    css = f"""
.k {{ font-family:{DISPLAY}; font-size:132px; line-height:.94; font-weight:700;
      letter-spacing:-.03em; }}
.k em {{ font-style:normal; color:{COLORS['accent']}; }}
.sub {{ margin-top:40px; font-size:34px; line-height:1.45; color:{COLORS['muted']};
        max-width:820px; }}
.stat {{ margin-top:56px; display:flex; gap:64px; }}
.stat b {{ display:block; font-family:{DISPLAY}; font-size:76px; color:{COLORS['text']};
           letter-spacing:-.02em; }}
.stat span {{ font-size:23px; color:{COLORS['muted']}; font-weight:600;
              letter-spacing:.12em; text-transform:uppercase; }}
.glow {{ position:absolute; top:-220px; right:-200px; width:720px; height:720px;
         border-radius:50%; filter:blur(120px); opacity:.30;
         background:radial-gradient(circle,{COLORS['accent2']},transparent 68%); }}
"""
    body = f"""<div class="glow"></div>
<div class="head"><div class="eyebrow">Threads recap</div>
<div class="handle">@{HANDLE}</div></div>
<div class="spacer"></div>
<div class="k">Yesterday<br>on <em>Threads</em></div>
<div class="sub">{html.escape(day_label)} — every post I published, ranked by views.</div>
<div class="stat">
  <div><b>{total_posts}</b><span>Posts</span></div>
  <div><b>{top_views:,}</b><span>Top post views</span></div>
</div>
<div class="spacer"></div>
<div class="foot"><div>Swipe →</div>{_dots(i, n)}</div>"""
    return _page(body, css)


def post_slide(rank, post, i, n):
    text = post["text"]
    # Long posts get smaller type rather than an overflowing card.
    size = 62 if len(text) <= 90 else 54 if len(text) <= 150 else 46 if len(text) <= 240 else 39
    eyebrow = EYEBROWS[rank - 1] if rank <= len(EYEBROWS) else f"#{rank}"
    when = post["pacific"].strftime("%-I:%M %p").lower()

    css = f"""
.rank {{ font-family:{DISPLAY}; font-size:112px; font-weight:700; color:{COLORS['accent']};
         line-height:1; letter-spacing:-.04em; }}
.card {{ background:{COLORS['surface']}; border:2px solid {COLORS['line']};
         border-radius:34px; padding:56px 52px; margin-top:26px; }}
.quote {{ font-size:{size}px; line-height:1.32; font-weight:600; letter-spacing:-.015em; }}
.mrow {{ display:flex; gap:52px; margin-top:52px; align-items:baseline; }}
.m b {{ font-family:{DISPLAY}; font-size:52px; color:{COLORS['text']}; }}
.m span {{ font-size:21px; color:{COLORS['muted']}; font-weight:600;
           letter-spacing:.1em; text-transform:uppercase; margin-left:10px; }}
"""
    body = f"""<div class="head"><div class="eyebrow">{eyebrow}</div>
<div class="handle">{when} PT</div></div>
<div class="rule"></div>
<div class="spacer"></div>
<div class="rank">{rank:02d}</div>
<div class="card">
  <div class="quote">{html.escape(text)}</div>
  <div class="mrow">
    <div class="m"><b>{post['views']:,}</b><span>views</span></div>
    <div class="m"><b>{post['likes']}</b><span>likes</span></div>
    <div class="m"><b>{post['replies']}</b><span>replies</span></div>
  </div>
</div>
<div class="spacer"></div>
<div class="foot"><div>@{HANDLE}</div>{_dots(i, n)}</div>"""
    return _page(body, css)


def cta_slide(i, n):
    css = f"""
.k {{ font-family:{DISPLAY}; font-size:104px; line-height:1.0; font-weight:700;
      letter-spacing:-.03em; }}
.k em {{ font-style:normal; color:{COLORS['accent']}; }}
.sub {{ margin-top:38px; font-size:33px; line-height:1.5; color:{COLORS['muted']};
        max-width:800px; }}
.pill {{ margin-top:56px; align-self:flex-start; padding:26px 46px; border-radius:999px;
         background:{COLORS['accent']}; color:{COLORS['ink']}; font-size:34px;
         font-weight:800; letter-spacing:-.01em; }}
.glow {{ position:absolute; bottom:-260px; left:-180px; width:700px; height:700px;
         border-radius:50%; filter:blur(120px); opacity:.28;
         background:radial-gradient(circle,{COLORS['accent']},transparent 68%); }}
"""
    body = f"""<div class="glow"></div>
<div class="head"><div class="eyebrow">Every single day</div>
<div class="handle">@{HANDLE}</div></div>
<div class="spacer"></div>
<div class="k">I post this<br><em>daily.</em></div>
<div class="sub">ADHD, unmasked — the systems, the spirals, and what actually works.
Come argue with me in the replies.</div>
<div class="pill">@{HANDLE}</div>
<div class="spacer"></div>
<div class="foot"><div>Threads · Instagram · TikTok</div>{_dots(i, n)}</div>"""
    return _page(body, css)


def render_all(pages, outdir):
    """pages: list of HTML strings -> outdir/slide-01.jpg ... Returns paths."""
    from playwright.sync_api import sync_playwright

    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--font-render-hinting=none"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for idx, doc in enumerate(pages, 1):
            page.set_content(doc, wait_until="load")
            try:
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(350)
            except Exception:
                page.wait_for_timeout(700)
            out = outdir / f"slide-{idx:02d}.jpg"
            page.screenshot(path=str(out), type="jpeg", quality=92)
            written.append(out)
        browser.close()
    return written
