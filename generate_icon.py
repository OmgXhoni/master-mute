"""Generate MasterMute app icon — speaker-with-slash mute symbol.

Run once to create icon.ico in the project directory.
"""

from PIL import Image, ImageDraw


def draw_speaker_muted(size: int, bg_color: str = "#1a1a2e",
                       speaker_color: str = "#e0e0e0",
                       slash_color: str = "#ff2244") -> Image.Image:
    """Draw a speaker icon with a diagonal red slash (mute symbol)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = int(size * 0.04)
    draw.ellipse([margin, margin, size - margin, size - margin], fill=bg_color)

    s = size
    cx, cy = s // 2, s // 2

    # Speaker rectangle (left part)
    rect_w = int(s * 0.12)
    rect_h = int(s * 0.22)
    rect_left = cx - int(s * 0.18)
    rect_top = cy - rect_h // 2
    draw.rectangle([rect_left, rect_top, rect_left + rect_w, rect_top + rect_h],
                   fill=speaker_color)

    # Speaker cone (triangle from rectangle to wider opening)
    cone_tip_x = rect_left + rect_w
    cone_end_x = cx + int(s * 0.08)
    cone_half_h = int(s * 0.28)
    draw.polygon([
        (cone_tip_x, rect_top),
        (cone_tip_x, rect_top + rect_h),
        (cone_end_x, cy + cone_half_h),
        (cone_end_x, cy - cone_half_h),
    ], fill=speaker_color)

    # Sound waves (arcs)
    wave_x = cone_end_x + int(s * 0.06)
    for radius in [int(s * 0.10), int(s * 0.18)]:
        arc_bbox = [wave_x - radius, cy - radius, wave_x + radius, cy + radius]
        width = max(2, int(s * 0.035))
        draw.arc(arc_bbox, start=-45, end=45, fill=speaker_color, width=width)

    # Diagonal red slash
    slash_w = max(3, int(s * 0.06))
    pad = int(size * 0.16)
    draw.line([pad, pad, s - pad, s - pad], fill=slash_color, width=slash_w)

    return img


def main():
    sizes = [16, 32, 48, 256]
    images = [draw_speaker_muted(s) for s in sizes]

    out_path = "icon.ico"
    images[-1].save(out_path, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
    print(f"Saved {out_path} with sizes {sizes}")


if __name__ == "__main__":
    main()
