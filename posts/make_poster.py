"""Render Instagram posters from post JSON files.

  python posts/make_poster.py posts/queue/2026-10-16-aditya-l1.json     # one post
  python posts/make_poster.py posts/queue/*.json                         # many
  python posts/make_poster.py --date 2026-10-16                          # every post in queue for that date

A post JSON looks like:
  {"date": "2026-10-16", "lane": "space", "slug": "aditya-l1-solar",
   "headline": "ISRO's Aditya-L1 just decoded how the Sun hurls plasma at Earth",
   "facts": ["Fact one, short.", "Fact two.", "Fact three."],
   "source": "The Hindu", "url": "https://...",
   "caption": "Optional: full caption text; if absent one is built from headline + facts + hashtags."}

For each post two images are made in posts/out/<date>/: <slug>-feed.png (1080x1350) and <slug>-story.png
(1080x1920), plus <slug>-caption.txt ready to paste into Instagram. Needs Pillow. Fonts and logo ship in
posts/fonts and posts/brand. Nothing is fetched from the internet."""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import random
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = json.load(open(os.path.join(HERE, "brand.json"), encoding="utf-8"))
C = BRAND["colors"]


def font(weight, size):
    return ImageFont.truetype(os.path.join(HERE, "fonts", f"Poppins-{weight}.ttf"), size)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def background(w, h, seed):
    """Navy to purple gradient, a violet glow top-right, a blue glow bottom-left, and a thin starfield."""
    top, bot = hexrgb(C["bg_top"]), hexrgb(C["bg_bottom"])
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    img = grad.resize((w, h))
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([w * 0.45, -h * 0.25, w * 1.35, h * 0.45], fill=hexrgb(C["glow"]))
    g.ellipse([-w * 0.5, h * 0.65, w * 0.45, h * 1.3], fill=hexrgb(C["glow2"]))
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.22))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 2))), 0.55)
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(int(w * h / 9000)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.choice([1, 1, 1, 2, 2, 3])
        a = rnd.randint(90, 230)
        d.ellipse([x - r / 2, y - r / 2, x + r / 2, y + r / 2], fill=(a, a, min(255, a + 20)))
    return img


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_headline(draw, text, max_w, max_lines, sizes):
    for s in sizes:
        f = font("Bold", s)
        lines = wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
    f = font("Bold", sizes[-1])
    return f, wrap(draw, text, f, max_w)[:max_lines]


def rounded_logo(size):
    logo = Image.open(os.path.join(HERE, "brand", "logo.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    logo.putalpha(mask.resize((size, size), Image.LANCZOS))
    return logo


def render(post, w, h, out):
    img = background(w, h, seed=post["slug"])
    d = ImageDraw.Draw(img)
    m = int(w * 0.075)                      # side margin
    story = h > w * 1.4
    y = int(h * (0.14 if story else 0.075))

    # lane badge + date
    lane = BRAND["lanes"].get(post["lane"], post["lane"].upper())
    bf = font("Bold", 30)
    bw = d.textlength(lane, font=bf) + 52
    d.rounded_rectangle([m, y, m + bw, y + 58], radius=29, fill=hexrgb(C["badge_bg"]))
    d.text((m + 26, y + 11), lane, font=bf, fill=hexrgb(C["badge_text"]))
    date = dt.date.fromisoformat(post["date"]).strftime("%d %b %Y").upper()
    df = font("Medium", 28)
    d.text((w - m - d.textlength(date, font=df), y + 14), date, font=df, fill=hexrgb(C["muted"]))
    y += 58 + int(h * 0.045)

    # headline
    hf, lines = fit_headline(d, post["headline"], w - 2 * m, 4 if story else 3, [84, 76, 70, 64, 58, 52, 48])
    lh = int(hf.size * 1.18)
    for ln in lines:
        d.text((m, y), ln, font=hf, fill=hexrgb(C["headline"]))
        y += lh
    y += int(h * 0.03)
    d.rounded_rectangle([m, y, m + 140, y + 8], radius=4, fill=hexrgb(C["accent"]))
    y += int(h * 0.045)

    # facts: shrink the font until everything fits above the footer, then drop the last fact if it still won't
    footer_top = h - int(h * (0.16 if story else 0.145))
    avail = footer_top - y - int(h * 0.03)
    facts = list(post.get("facts", [])[:4])
    gap_h = int(h * 0.018)

    def layout(fs, items):
        ff = font("Regular", fs)
        blocks, total = [], 0
        for fact in items:
            fl = wrap(d, fact, ff, w - 2 * m - 54)
            blocks.append(fl)
            total += len(fl) * int(fs * 1.35) + gap_h
        return ff, blocks, total

    sizes = [46, 44, 42, 40, 38, 36, 34, 32, 30] if story else [38, 36, 34, 32, 30]
    while True:
        chosen = None
        for fs in sizes:
            ff, blocks, total = layout(fs, facts)
            if total <= avail:
                chosen = (ff, blocks)
                break
        if chosen or len(facts) <= 1:
            break
        facts = facts[:-1]
    if not chosen:
        ff, blocks, _ = layout(sizes[-1], facts)
        chosen = (ff, blocks)
    ff, blocks = chosen
    for fl in blocks:
        d.ellipse([m, y + 18, m + 16, y + 34], fill=hexrgb(C["accent"]))
        for ln in fl:
            d.text((m + 54, y), ln, font=ff, fill=hexrgb(C["body"]))
            y += int(ff.size * 1.35)
        y += gap_h

    # footer
    fy = h - int(h * (0.16 if story else 0.145))
    d.line([m, fy, w - m, fy], fill=hexrgb(C["line"]), width=2)
    fy += int(h * 0.028)
    size = 104 if story else 96
    img.paste(rounded_logo(size), (m, fy), rounded_logo(size))
    nf, cf = font("Bold", 34), font("Regular", 28)
    d.text((m + size + 26, fy + 6), BRAND["name"], font=nf, fill=hexrgb(C["headline"]))
    d.text((m + size + 26, fy + 52), f'{BRAND["handle"]}  ·  {BRAND["cta"]}', font=cf, fill=hexrgb(C["accent"]))
    if post.get("source"):
        sf = font("Regular", 22)
        s = "Source: " + post["source"]
        while d.textlength(s, font=sf) > w * 0.38 and len(s) > 20:
            s = s[:-4].rstrip() + "…"
        d.text((w - m - d.textlength(s, font=sf), fy + size + 10), s, font=sf, fill=hexrgb(C["muted"]))
    img.save(out, "PNG", optimize=True)


def caption(post):
    if post.get("caption"):
        return post["caption"]
    parts = [post["headline"], ""]
    parts += [f"• {f}" for f in post.get("facts", [])]
    parts += ["", f"Source: {post.get('source', '')}".strip(),
              "", f"{BRAND['cta']}: {BRAND['youtube']}", ""]
    tags = BRAND["hashtags"]["common"] + BRAND["hashtags"].get(post["lane"], [])
    parts.append(" ".join(tags))
    return "\n".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="*")
    p.add_argument("--date", help="render every posts/queue/<date>-*.json")
    p.add_argument("--out", default=os.path.join(HERE, "out"))
    a = p.parse_args(argv)
    files = list(a.files)
    if a.date:
        files += glob.glob(os.path.join(HERE, "queue", f"{a.date}-*.json"))
    if not files:
        print("no post files given", file=sys.stderr)
        return 1
    for f in files:
        post = json.load(open(f, encoding="utf-8"))
        outdir = os.path.join(a.out, post["date"])
        os.makedirs(outdir, exist_ok=True)
        base = os.path.join(outdir, post["slug"])
        render(post, 1080, 1350, base + "-feed.png")
        render(post, 1080, 1920, base + "-story.png")
        with open(base + "-caption.txt", "w", encoding="utf-8") as c:
            c.write(caption(post))
        print(f"made {base}-feed.png, -story.png, -caption.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
