"""Design tokens — single source of truth matching the HTML/Tailwind prototypes.

All colors, sizes, and radii are extracted from docs/ux/screens/*.html
so Flet screens stay consistent with the prototypes.
"""

# ---------- Color Palette (Tailwind) ----------
# Primary brand
BLUE_400 = "#60a5fa"
BLUE_500 = "#3b82f6"
BLUE_600 = "#2563eb"
BLUE_700 = "#1d4ed8"

# Greens
GREEN_400 = "#22c55e"
GREEN_500 = "#22c55e"
GREEN_600 = "#16a34a"

# Reds
RED_500 = "#ef4444"
RED_600 = "#dc2626"
RED_700 = "#b91c1c"

# Amber / Orange
AMBER_500 = "#f59e0b"
AMBER_600 = "#d97706"

# Neutrals
WHITE = "#ffffff"
GRAY_50 = "#f9fafb"
GRAY_100 = "#f3f4f6"
GRAY_200 = "#e5e7eb"
GRAY_300 = "#d1d5db"
GRAY_400 = "#9ca3af"
GRAY_700 = "#374151"
BLACK = "#000000"

# Object card colors (from prototype)
PINK_400 = "#f472b6"
BLUE_OBJ = "#60a5fa"
EMERALD_400 = "#34d399"
ORANGE_400 = "#fb923c"
PURPLE_400 = "#c084fc"
CYAN_400 = "#22d3ee"

CARD_COLORS = [
    PINK_400,
    BLUE_OBJ,
    EMERALD_400,
    ORANGE_400,
    PURPLE_400,
    CYAN_400,
    "#f87171",  # red-400
    "#818cf8",  # indigo-400
    "#a3e635",  # lime-400
    "#fb7185",  # rose-400
]


def _hex_to_bgr(hex_color: str) -> tuple:
    """Convert hex color string to BGR tuple for OpenCV."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


# CARD_COLORS in BGR format for OpenCV drawing (masks, contours, labels)
CARD_COLORS_BGR = [_hex_to_bgr(c) for c in CARD_COLORS]

# ---------- Opacity helpers ----------
# Flet uses ft.Colors.with_opacity(opacity, hex) — these are the prototype values
OVERLAY_DARK_60 = 0.60   # status pill, back buttons
OVERLAY_DARK_70 = 0.70   # info cards, step indicators
OVERLAY_DARK_80 = 0.80   # action bars
OVERLAY_LIGHT_10 = 0.10  # secondary buttons (white)
OVERLAY_LIGHT_20 = 0.20  # secondary hover

# Edge zones (screen 4)
EDGE_ZONE_DEFAULT = 0.30
EDGE_ZONE_HOVER = 0.60

# ---------- Border Radii ----------
RADIUS_FULL = 999   # pill / circle
RADIUS_3XL = 24     # edge zone inner curves
RADIUS_2XL = 16     # panels, cards, action buttons
RADIUS_XL = 12      # inputs, small buttons
RADIUS_LG = 8       # default

# ---------- Font Sizes ----------
TEXT_XS = 12
TEXT_SM = 14
TEXT_BASE = 16
TEXT_LG = 18
TEXT_XL = 20
TEXT_2XL = 24

# ---------- Touch Target Sizes ----------
# From prototype measurements
GEAR_SIZE = 48             # settings gear w/h
CTA_WIDTH = None           # auto (px-10 = 40px padding each side)
CTA_HEIGHT = None          # auto (py-5 = 20px padding each side)
CTA_PADDING_H = 40        # horizontal padding on primary CTA
CTA_PADDING_V = 20        # vertical padding on primary CTA

CARD_MIN_W = 160           # object selection card min-width
CARD_MIN_H = 100           # object selection card min-height
CARD_PADDING = 16          # p-4

EDGE_ZONE_LR_W = 96       # left/right edge zone width
EDGE_ZONE_LR_H = 192      # left/right edge zone height
EDGE_ZONE_TB_W = 192      # top/bottom edge zone width
EDGE_ZONE_TB_H = 80       # top/bottom edge zone height

BOTTOM_BTN_W = 90          # height/gripper button width
BOTTOM_BTN_H = 60          # height/gripper button height

# Settings panel
SETTINGS_WIDTH_PCT = 0.45  # 45% of container
CLOSE_BTN_SIZE = 40        # close button w/h
