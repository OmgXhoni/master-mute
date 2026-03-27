"""Generate MasterMute icon.ico and logo.png from scratch using Pillow.

Reproduces the SVG design: black circle, white speaker silhouette, red X.
"""

import os
import math

from PIL import Image, ImageDraw

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICO_PATH = os.path.join(SCRIPT_DIR, "icon.ico")
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")


def draw_icon(size: int) -> Image.Image:
    """Draw the MasterMute icon at the given size.

    Design: black circle background, white speaker (body + cone + crossbar),
    red X overlay on the right side.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size
    cx, cy = s / 2, s / 2
    r = s * 0.489  # circle radius (391.52/800)

    # Black circle background
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#000000")

    # --- Speaker body (left side) ---
    # Rectangle part of speaker
    rect_left = s * 0.148
    rect_right = s * 0.245
    rect_top = cy - s * 0.113
    rect_bottom = cy + s * 0.113
    draw.rectangle([rect_left, rect_top, rect_right, rect_bottom], fill="#ffffff")

    # Cone (trapezoid from rectangle to wider opening)
    cone_left = rect_right
    cone_right = s * 0.48
    cone_half_narrow = s * 0.113
    cone_half_wide = s * 0.185
    draw.polygon([
        (cone_left, cy - cone_half_narrow),
        (cone_left, cy + cone_half_narrow),
        (cone_right, cy + cone_half_wide),
        (cone_right, cy - cone_half_wide),
    ], fill="#ffffff")

    # --- White crossbar (horizontal bar across the X area) ---
    bar_left = s * 0.517
    bar_right = s * 0.852
    bar_h = s * 0.047
    bar_r = bar_h / 2  # rounded ends
    draw.rounded_rectangle(
        [bar_left, cy - bar_h / 2, bar_right, cy + bar_h / 2],
        radius=bar_r, fill="#ffffff"
    )

    # --- White vertical bar ---
    draw.rounded_rectangle(
        [cx + s * 0.185 - bar_h / 2, cy - (bar_right - bar_left) / 2,
         cx + s * 0.185 + bar_h / 2, cy + (bar_right - bar_left) / 2],
        radius=bar_r, fill="#ffffff"
    )

    # --- Red X overlay ---
    x_cx = cx + s * 0.185  # center of the X area
    x_cy = cy
    arm_len = s * 0.145
    line_w = max(2, int(s * 0.047))

    # Top-left to bottom-right
    draw.line(
        [x_cx - arm_len, x_cy - arm_len, x_cx + arm_len, x_cy + arm_len],
        fill="#ed1c24", width=line_w
    )
    # Top-right to bottom-left
    draw.line(
        [x_cx + arm_len, x_cy - arm_len, x_cx - arm_len, x_cy + arm_len],
        fill="#ed1c24", width=line_w
    )

    # Round line caps by drawing circles at the endpoints
    cap_r = line_w / 2
    for dx, dy in [(-1, -1), (1, 1), (1, -1), (-1, 1)]:
        ex, ey = x_cx + dx * arm_len, x_cy + dy * arm_len
        draw.ellipse([ex - cap_r, ey - cap_r, ex + cap_r, ey + cap_r], fill="#ed1c24")

    return img


def main():
    sizes = [16, 32, 48, 256]
    images = [draw_icon(s) for s in sizes]

    # Save .ico
    images[-1].save(ICO_PATH, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
    print(f"Saved {ICO_PATH} with sizes {sizes}")

    # Save 48px PNG for tray/setup logo, and 256px for preview
    images[2].save(LOGO_PATH)
    print(f"Saved {LOGO_PATH} (48px)")

    images[-1].save(os.path.join(SCRIPT_DIR, "icon_preview.png"))
    print("Saved icon_preview.png (256px)")


if __name__ == "__main__":
    main()
