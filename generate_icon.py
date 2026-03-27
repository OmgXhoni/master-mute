"""Generate MasterMute icon.ico from the source PNG."""

import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PNG = os.path.join(SCRIPT_DIR, "mastermute.png")
ICO_PATH = os.path.join(SCRIPT_DIR, "icon.ico")


def main():
    src = Image.open(SRC_PNG).convert("RGBA")
    sizes = [16, 32, 48, 256]
    images = [src.resize((s, s), Image.LANCZOS) for s in sizes]

    images[-1].save(ICO_PATH, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
    print(f"Saved {ICO_PATH} with sizes {sizes}")


if __name__ == "__main__":
    main()
