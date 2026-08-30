"""Visual identity for the ADHD carousel.

Brand 5333281 has no design system in Metricool — its "logo" is a profile photo —
so this palette and layout were authored for this pipeline and reviewed against
real rendered slides.

APPROVED by Alex on 2026-08-30. Treat it the way the real-estate carousel treats
its own approved design: do not restyle, re-space, or "improve" it as a side
effect of another change. Design changes need Alex to ask for them.
"""

HANDLE = "the.alexmaldonado"

# 4:5 — the tallest aspect Instagram renders in-feed without cropping.
W, H = 1080, 1350

COLORS = {
    "ink":     "#0E0E12",  # near-black page ground
    "surface": "#17171F",  # raised card
    "line":    "#2A2A36",
    "text":    "#F4F3F0",
    "muted":   "#9B99A8",
    "accent":  "#FF6B4A",  # warm coral — rank numerals, key figures
    "accent2": "#7C6BFF",  # violet — secondary accent, cover gradient
}

# Loaded from Google Fonts by render.py; the stack degrades to the runner's
# DejaVu if the CDN is unreachable, which shifts metrics but never blanks text.
FONT_CSS = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400;600;800;900&family=Space+Grotesk:wght@700&display=swap"
)
SANS = "'Inter', system-ui, 'DejaVu Sans', sans-serif"
DISPLAY = "'Space Grotesk', 'Inter', system-ui, 'DejaVu Sans', sans-serif"

EYEBROWS = ["TOP POST", "RUNNER-UP", "THIRD", "FOURTH", "FIFTH", "SIXTH"]
