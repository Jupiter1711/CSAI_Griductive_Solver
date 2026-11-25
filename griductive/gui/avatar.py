"""Round character portraits from assets/avatars/<size>/<slug>.png.

Each portrait exists at 192, 128 and 72 px (the @2x sizes for 96, 64 and
36/28 px on screen). The smallest file at least as large as the on-screen size
is scaled down to the exact device size, masked to a circle and given a faint
inner ring. Names without a file get an initials disc.
"""

import re
from functools import lru_cache
from pathlib import Path

import pygame

from griductive.gui import widgets
from griductive.gui.theme import Theme

AVATAR_DIR = Path(__file__).resolve().parents[2] / "assets" / "avatars"
SIZES = (72, 128, 192)

# Alternate character names -> portrait file slug.
ALIASES = {
    "freezer": "frieza",
    "freeza": "frieza",
    "celula": "cell",
    "tenshinhan": "tien",
    "tien-shinhan": "tien",
    "master-roshi": "roshi",
    "kame-sennin": "roshi",
    "bills": "beerus",
    "hercule": "mr-satan",
    "dr-gero": "android-20",
    "vegetto": "vegito",
    "kaio": "king-kai",
    "buu": "majin-buu",
}


def slug(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return ALIASES.get(key, key)


def portrait_path(name: str, wanted: int = 192) -> Path | None:
    """Smallest exported size >= ``wanted`` px, else the largest that exists."""
    found = [
        AVATAR_DIR / str(size) / f"{slug(name)}.png"
        for size in SIZES
        if (AVATAR_DIR / str(size) / f"{slug(name)}.png").is_file()
    ]
    for path in found:
        if int(path.parent.name) >= wanted:
            return path
    return found[-1] if found else None


@lru_cache(maxsize=128)
def _load(path: Path) -> pygame.Surface | None:
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except pygame.error:
        return None


def initials(name: str) -> str:
    parts = [part for part in re.split(r"[\s\-]+", name) if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:1].upper() or "?"


@lru_cache(maxsize=512)
def avatar(theme: Theme, name: str, size_px: int) -> pygame.Surface:
    """Circular portrait exactly ``size_px`` device pixels wide."""
    colors = theme.colors
    size_px = max(4, size_px)
    disc = pygame.Surface((size_px, size_px), pygame.SRCALPHA)
    centre, radius = (size_px / 2, size_px / 2), size_px / 2

    path = portrait_path(name, size_px)
    source = None if path is None else _load(path)
    if source is None:
        palette = colors.monogram
        color = palette[sum(map(ord, name)) % len(palette)]
        pygame.draw.circle(disc, color, centre, radius)
        label = widgets.render_text(
            theme, "semibold", max(6, round(size_px * 0.36)), initials(name), colors.ink
        )
        disc.blit(label, label.get_rect(center=centre))
    else:
        pygame.draw.circle(disc, colors.card, centre, radius)
        face = pygame.transform.smoothscale(source, (size_px, size_px))
        mask = pygame.Surface((size_px, size_px), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), centre, radius)
        face.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        disc.blit(face, (0, 0))

    ring = pygame.Surface((size_px, size_px), pygame.SRCALPHA)
    pygame.draw.circle(ring, colors.avatar_ring, centre, radius, max(1, size_px // 64))
    disc.blit(ring, (0, 0))
    return disc


def clear_caches() -> None:
    """Drop cached surfaces; they become invalid after pygame.quit()."""
    _load.cache_clear()
    avatar.cache_clear()
