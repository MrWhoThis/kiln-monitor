#!/usr/bin/env python3
"""Generate Kiln Monitor brand assets for home-assistant/brands.

Draws a front-loading kiln (steel body, glowing arched door with a flame inside)
and a "Kiln Monitor" wordmark logo. Everything is rendered at a high supersample
and downscaled with LANCZOS for clean edges, then trimmed so the output satisfies
the brands size + whitespace requirements.

Outputs (into the directory given as argv[1], default "."):
    icon.png / icon@2x.png            256 / 512 square
    logo.png / logo@2x.png            wordmark, max side 512 / 1024
    dark_logo.png / dark_logo@2x.png  wordmark for dark backgrounds
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFont

SS = 4  # supersample factor
FONT_BOLD = "/usr/local/lib/python3.14/site-packages/aioslimproto/font/DejaVu-Sans-Bold.ttf"

# --- palette -----------------------------------------------------------------
BODY_T, BODY_B = (113, 125, 137), (72, 81, 90)     # steel body gradient
LID_T, LID_B = (88, 97, 106), (64, 72, 80)         # lid cap
FEET = (58, 66, 74)
FRAME = (44, 50, 56)                               # door frame
GLOW = [(0.0, (255, 247, 198)), (0.5, (255, 140, 28)), (1.0, (198, 28, 0))]
FLAME_OUT = ((255, 198, 64), (255, 112, 0))
FLAME_IN = ((255, 250, 206), (255, 172, 44))
TEXT_LIGHT = (62, 70, 78)      # wordmark on light backgrounds
TEXT_DARK = (236, 240, 244)    # wordmark on dark backgrounds

# Flame silhouettes in unit coordinates (x right, y down), traced clockwise.
OUTER = [
    (0.50, 0.04), (0.605, 0.20), (0.67, 0.37), (0.74, 0.56), (0.71, 0.73),
    (0.60, 0.86), (0.50, 0.91), (0.40, 0.86), (0.29, 0.73), (0.26, 0.56),
    (0.33, 0.37), (0.395, 0.20),
]
INNER = [
    (0.50, 0.40), (0.565, 0.52), (0.605, 0.65), (0.55, 0.79), (0.50, 0.845),
    (0.45, 0.79), (0.395, 0.65), (0.435, 0.52),
]


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def clamp01(t):
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def catmull(points, samples=48):
    """Closed Catmull-Rom spline through the control points."""
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (points[(i + k) % n] for k in (-1, 0, 1, 2))
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    return out


def vgrad_fill(W, mask, ctop, cbot, y0, y1):
    """RGBA layer: vertical gradient ctop->cbot (over pixel rows y0..y1) under mask."""
    col = Image.new("RGB", (1, W))
    for yy in range(W):
        col.putpixel((0, yy), lerp(ctop, cbot, clamp01((yy - y0) / (y1 - y0))))
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    layer.paste(col.resize((W, W)), (0, 0), mask)
    return layer


def rrect_mask(W, box, radius, corners=(True, True, True, True)):
    m = Image.new("L", (W, W), 0)
    x0, y0, x1, y1 = (v * W for v in box)
    ImageDraw.Draw(m).rounded_rectangle(
        [x0, y0, x1, y1], radius=radius * W, fill=255, corners=corners
    )
    return m


def glow_color(r):
    for (r0, c0), (r1, c1) in zip(GLOW, GLOW[1:]):
        if r <= r1:
            return lerp(c0, c1, (r - r0) / (r1 - r0) if r1 > r0 else 0)
    return GLOW[-1][1]


def radial_layer(W, box, mask):
    """Radial heat glow inside the door box, brightest just below center."""
    R = 220
    cx, cy = 0.5, 0.6
    maxd = max(math.hypot(cx, cy), math.hypot(1 - cx, cy),
               math.hypot(cx, 1 - cy), math.hypot(1 - cx, 1 - cy))
    grid = Image.new("RGB", (R, R))
    gp = grid.load()
    for yy in range(R):
        for xx in range(R):
            gp[xx, yy] = glow_color(math.hypot(xx / R - cx, yy / R - cy) / maxd)
    x0, y0, x1, y1 = (int(v * W) for v in box)
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    layer.paste(grid.resize((x1 - x0, y1 - y0)), (x0, y0), mask.crop((x0, y0, x1, y1)))
    return layer


def flame_layer(W, box):
    """A small flame mapped into the unit box (bx0,by0,bx1,by1)."""
    bx0, by0, bx1, by1 = box
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    for loop, (ct, cb) in ((OUTER, FLAME_OUT), (INNER, FLAME_IN)):
        mapped = [(bx0 + ox * (bx1 - bx0), by0 + oy * (by1 - by0)) for ox, oy in loop]
        pts = [(x * W, y * W) for x, y in catmull(mapped)]
        ys = [p[1] for p in pts]
        m = Image.new("L", (W, W), 0)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        layer.alpha_composite(vgrad_fill(W, m, ct, cb, min(ys), max(ys)))
    return layer


def kiln_artwork(W):
    """Draw the kiln onto a WxW transparent canvas (untrimmed)."""
    c = Image.new("RGBA", (W, W), (0, 0, 0, 0))

    def part(box, ctop, cbot, radius, corners=(True, True, True, True)):
        c.alpha_composite(
            vgrad_fill(W, rrect_mask(W, box, radius, corners), ctop, cbot,
                       box[1] * W, box[3] * W)
        )

    # feet (behind body)
    for fb in ((0.235, 0.815, 0.350, 0.880), (0.650, 0.815, 0.765, 0.880)):
        part(fb, FEET, FEET, 0.018)
    # body, then lid cap on top
    part((0.175, 0.255, 0.825, 0.820), BODY_T, BODY_B, 0.05)
    part((0.130, 0.150, 0.870, 0.272), LID_T, LID_B, 0.045)
    # door: dark frame, glowing interior, flame
    part((0.305, 0.335, 0.695, 0.756), FRAME, FRAME, 0.17, (True, True, False, False))
    dg = (0.325, 0.355, 0.675, 0.756)
    c.alpha_composite(radial_layer(W, dg, rrect_mask(W, dg, 0.15, (True, True, False, False))))
    c.alpha_composite(flame_layer(W, (0.405, 0.45, 0.595, 0.735)))
    return c


def trim_pad(img, maxdim, margin):
    """Trim to content, then scale so the largest side fills maxdim*(1-2*margin)."""
    content = img.crop(img.getbbox())
    scale = (maxdim * (1 - 2 * margin)) / max(content.size)
    content = content.resize(
        (max(1, round(content.width * scale)), max(1, round(content.height * scale))),
        Image.LANCZOS,
    )
    return content


def render_icon(size, margin=0.06):
    art = kiln_artwork(size * SS)
    content = trim_pad(art, size, margin)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(content, ((size - content.width) // 2, (size - content.height) // 2))
    return out


def render_logo(maxdim, dark=False):
    H = 1024  # internal working height
    icon = render_icon(int(H * 0.96), margin=0.02)
    font = ImageFont.truetype(FONT_BOLD, int(H * 0.46))
    text = "Kiln Monitor"
    bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    gap, pad = int(H * 0.05), int(H * 0.03)

    canvas = Image.new("RGBA", (pad + icon.width + gap + tw + pad, H), (0, 0, 0, 0))
    canvas.alpha_composite(icon, (pad, (H - icon.height) // 2))
    tx = pad + icon.width + gap
    ImageDraw.Draw(canvas).text(
        (tx - bbox[0], (H - th) // 2 - bbox[1]), text, font=font,
        fill=(TEXT_DARK if dark else TEXT_LIGHT) + (255,),
    )
    return trim_pad(canvas, maxdim, margin=0.01)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    render_icon(512).save(f"{out}/icon@2x.png", optimize=True, compress_level=9)
    render_icon(256).save(f"{out}/icon.png", optimize=True, compress_level=9)
    render_logo(1024).save(f"{out}/logo@2x.png", optimize=True, compress_level=9)
    render_logo(512).save(f"{out}/logo.png", optimize=True, compress_level=9)
    render_logo(1024, dark=True).save(f"{out}/dark_logo@2x.png", optimize=True, compress_level=9)
    render_logo(512, dark=True).save(f"{out}/dark_logo.png", optimize=True, compress_level=9)
    print("wrote icon/logo/dark_logo (+@2x) to", out)


if __name__ == "__main__":
    main()
