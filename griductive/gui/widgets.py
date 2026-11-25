import math
from contextlib import contextmanager
from functools import lru_cache

import pygame
import pygame.freetype

from griductive.gui.theme import RGB, Color, Theme


class Box:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, *args) -> None:
        if len(args) == 1:
            args = tuple(args[0])
        self.x, self.y, self.w, self.h = (float(v) for v in args)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def __len__(self) -> int:
        return 4

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.w, self.h)[index]

    def __repr__(self) -> str:
        return f"Box({self.x:g}, {self.y:g}, {self.w:g}, {self.h:g})"

    @property
    def left(self) -> float:
        return self.x

    @property
    def top(self) -> float:
        return self.y

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def centerx(self) -> float:
        return self.x + self.w / 2

    @property
    def centery(self) -> float:
        return self.y + self.h / 2

    @property
    def center(self) -> tuple[float, float]:
        return self.centerx, self.centery

    @center.setter
    def center(self, value: tuple[float, float]) -> None:
        self.x = value[0] - self.w / 2
        self.y = value[1] - self.h / 2

    @property
    def topleft(self) -> tuple[float, float]:
        return self.x, self.y

    def copy(self) -> "Box":
        return Box(self.x, self.y, self.w, self.h)

    def move(self, dx: float, dy: float) -> "Box":
        return Box(self.x + dx, self.y + dy, self.w, self.h)

    def inflate(self, dx: float, dy: float) -> "Box":
        return Box(self.x - dx / 2, self.y - dy / 2, self.w + dx, self.h + dy)

    def clip(self, other) -> "Box":
        o = Box(other)
        left, top = max(self.x, o.x), max(self.y, o.y)
        right, bottom = min(self.right, o.right), min(self.bottom, o.bottom)
        if right <= left or bottom <= top:
            return Box(left, top, 0, 0)
        return Box(left, top, right - left, bottom - top)

    def collidepoint(self, point) -> bool:
        return self.x <= point[0] < self.right and self.y <= point[1] < self.bottom


@lru_cache(maxsize=16)
def face(theme: Theme, role: str) -> pygame.freetype.Font:
    if not pygame.freetype.get_init():
        pygame.freetype.init()
    fonts = theme.fonts
    path = {
        "display": fonts.display,
        "body": fonts.body,
        "medium": fonts.body_medium,
        "semibold": fonts.body_semibold,
        "mono": fonts.mono,
        "mono_medium": fonts.mono_medium,
    }[role]
    if path.is_file():
        result = pygame.freetype.Font(str(path), 16)
    else:
        fallback = (
            fonts.fallback_mono if role.startswith("mono") else fonts.fallback_sans
        )
        result = pygame.freetype.SysFont(fallback, 16, bold=role == "display")
    result.kerning = True
    result.antialiased = True
    result.pad = False
    return result


@lru_cache(maxsize=8)
def _gamma_table(gamma: float) -> bytes:
    return bytes(round(255 * (a / 255) ** (1 / gamma)) for a in range(256))


@lru_cache(maxsize=4096)
def _render(
    theme: Theme, role: str, size: int, content: str, color: RGB
) -> pygame.Surface:
    font = face(theme, role)
    ascender = font.get_sized_ascender(size)
    height = ascender - font.get_sized_descender(size)
    if not content.strip():
        width = max(1, round(font.get_rect(" ", size=size).w or size * 0.3))
        return pygame.Surface((width * max(1, len(content)), height), pygame.SRCALPHA)
    bounds = font.get_rect(content, size=size)
    raw, (w, h) = font.render_raw(content, size=size)
    alpha = raw.translate(_gamma_table(theme.metrics.text_gamma))
    pixels = bytearray(w * h * 4)
    for channel, value in enumerate(color):
        pixels[channel::4] = bytes((value,)) * (w * h)
    pixels[3::4] = alpha
    glyphs = pygame.image.frombytes(bytes(pixels), (w, h), "RGBA")
    left = max(0, bounds.x)
    advance = _advance(theme, role, size, content)
    image = pygame.Surface((max(left + w, advance), height), pygame.SRCALPHA)
    image.blit(glyphs, (left, ascender - bounds.y))
    return image


@lru_cache(maxsize=4096)
def _advance(theme: Theme, role: str, size: int, content: str) -> int:
    metrics = face(theme, role).get_metrics(content, size=size)
    return round(sum(item[4] for item in metrics if item is not None))


def render_text(
    theme: Theme, role: str, size: int, content: str, color: RGB
) -> pygame.Surface:
    return _render(theme, role, size, content, color)


def has_glyphs(theme: Theme, role: str, content: str) -> bool:
    metrics = face(theme, role).get_metrics(content, size=16)
    return all(item is not None for item in metrics)


def blend(color: Color, under: RGB) -> RGB:
    if len(color) == 3:
        return color[:3]
    alpha = color[3] / 255
    return tuple(round(c * alpha + u * (1 - alpha)) for c, u in zip(color[:3], under))


def fade(color: Color, under: RGB, opacity: float) -> RGB:
    flat = blend(color, under)
    return tuple(round(c * opacity + u * (1 - opacity)) for c, u in zip(flat, under))


def clear_caches() -> None:
    _render.cache_clear()
    _advance.cache_clear()
    face.cache_clear()


# Painter


class Painter:
    def __init__(
        self,
        surface: pygame.Surface,
        theme: Theme,
        scale: float,
        offset: tuple[float, float] = (0, 0),
    ) -> None:
        self.surface = surface
        self.theme = theme
        self.scale = scale
        self.offset = offset

    # Geometry

    def px(self, value: float) -> int:
        return int(round(value * self.scale))

    def width(self, value: float) -> int:
        return max(1, int(round(value * self.scale)))

    def point(self, x: float, y: float) -> tuple[int, int]:
        return (
            int(round(self.offset[0] + x * self.scale)),
            int(round(self.offset[1] + y * self.scale)),
        )

    def device(self, rect) -> pygame.Rect:
        x, y, w, h = rect
        left, top = self.point(x, y)
        right, bottom = self.point(x + w, y + h)
        return pygame.Rect(left, top, right - left, bottom - top)

    def logical(self, rect: pygame.Rect) -> Box:
        return Box(
            (rect.x - self.offset[0]) / self.scale,
            (rect.y - self.offset[1]) / self.scale,
            rect.w / self.scale,
            rect.h / self.scale,
        )

    @contextmanager
    def clip(self, rect):
        previous = self.surface.get_clip()
        self.surface.set_clip(self.device(rect).clip(previous))
        try:
            yield
        finally:
            self.surface.set_clip(previous)

    # Shapes

    def _shape(self, color: Color, draw, area: pygame.Rect) -> None:
        if len(color) == 3 or color[3] == 255:
            draw(self.surface, color[:3], (0, 0))
            return
        if area.w <= 0 or area.h <= 0:
            return
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        draw(layer, color, (-area.x, -area.y))
        self.surface.blit(layer, area.topleft)

    def fill(self, rect, color: Color, radius: float = 0) -> None:
        box = self.device(rect)
        r = self.px(radius)

        def draw(target, colour, shift):
            pygame.draw.rect(target, colour, box.move(shift), 0, r)

        self._shape(color, draw, box)

    def stroke(self, rect, color: Color, width: float = 1, radius: float = 0) -> None:
        box = self.device(rect)
        r = self.px(radius)
        w = self.width(width)

        def draw(target, colour, shift):
            pygame.draw.rect(target, colour, box.move(shift), w, r)

        self._shape(color, draw, box)

    def circle(
        self, center: tuple[float, float], radius: float, color: Color, width=0
    ) -> None:
        c = self.point(*center)
        r = max(1, self.px(radius))
        w = 0 if not width else self.width(width)
        area = pygame.Rect(c[0] - r - 1, c[1] - r - 1, 2 * r + 2, 2 * r + 2)

        def draw(target, colour, shift):
            pygame.draw.circle(target, colour, (c[0] + shift[0], c[1] + shift[1]), r, w)

        self._shape(color, draw, area)

    def polyline(
        self, points, color: Color, width: float = 1.5, closed: bool = False
    ) -> None:
        pts = [self.point(*p) for p in points]
        w = self.width(width)
        for a, b in zip(pts, pts[1:] + (pts[:1] if closed else [])):
            pygame.draw.line(self.surface, color[:3], a, b, w)
            if w > 2:
                pygame.draw.circle(self.surface, color[:3], b, w // 2)

    def dashed(
        self,
        rect,
        color: Color,
        width: float,
        radius: float,
        dash: tuple[int, int],
    ) -> None:
        x, y, w, h = rect
        r = min(radius, w / 2, h / 2)
        path: list[tuple[float, float]] = []
        corners = (
            (x + w - r, y + r, -90),
            (x + w - r, y + h - r, 0),
            (x + r, y + h - r, 90),
            (x + r, y + r, 180),
        )
        for cx, cy, start in corners:
            for k in range(9):
                angle = math.radians(start + k * 90 / 8)
                path.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        path.append(path[0])
        on, off = dash
        line_w = self.width(width)
        drawing, left = True, float(on)
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            seg = math.hypot(bx - ax, by - ay)
            pos = 0.0
            while pos < seg:
                step = min(left, seg - pos)
                if drawing:
                    t0, t1 = pos / seg, (pos + step) / seg
                    p0 = self.point(ax + (bx - ax) * t0, ay + (by - ay) * t0)
                    p1 = self.point(ax + (bx - ax) * t1, ay + (by - ay) * t1)
                    pygame.draw.line(self.surface, color[:3], p0, p1, line_w)
                pos += step
                left -= step
                if left <= 1e-6:
                    drawing = not drawing
                    left = float(on if drawing else off)

    def soft_shadow(self, rect, color: Color, radius: float, dy: float, blur: float):
        alpha = color[3] if len(color) == 4 else 255
        steps = 5
        for i in range(steps):
            grow = blur * (1 - i / steps) - blur / 2
            layer_alpha = round(alpha / steps * (0.6 + 0.4 * i / steps))
            box = Box(rect).inflate(grow * 2, grow * 2).move(0, dy)
            self.fill(box, (*color[:3], layer_alpha), radius + max(0, grow))

    # Text

    def _font_px(self, size: float) -> int:
        return max(1, int(round(size * self.scale)))

    def _role(self, role: str, size: float) -> str:
        if role == "mono" and size <= self.theme.metrics.mono_medium_max:
            return "mono_medium"
        return role

    def measure(self, content: str, size: float, role: str = "body") -> float:
        role = self._role(role, size)
        return _advance(self.theme, role, self._font_px(size), content) / self.scale

    def text(
        self,
        content: str,
        pos: tuple[float, float],
        size: float,
        color: Color,
        role: str = "body",
        anchor: str = "topleft",
    ) -> Box:
        role = self._role(role, size)
        image = _render(self.theme, role, self._font_px(size), content, color[:3])
        rect = image.get_rect(**{anchor: self.point(*pos)})
        self.surface.blit(image, rect)
        return self.logical(rect)

    def ellipsize(self, content: str, size: float, width: float, role="body") -> str:
        if self.measure(content, size, role) <= width:
            return content
        while content and self.measure(content + "…", size, role) > width:
            content = content[:-1]
        return content.rstrip() + "…"

    def wrap(self, content: str, size: float, width: float, role="body") -> list:
        lines: list[str] = []
        line = ""
        for word in content.split():
            candidate = f"{line} {word}".strip()
            if self.measure(candidate, size, role) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        self._avoid_orphan(lines, size, width, role)
        return [self.ellipsize(item, size, width, role) for item in lines]

    def _avoid_orphan(self, lines: list, size: float, width: float, role: str):
        if len(lines) < 2 or " " in lines[-1] or len(lines[-1]) > 3:
            return
        head, _, moved = lines[-2].rpartition(" ")
        if not head:
            return
        candidate = f"{moved} {lines[-1]}"
        if self.measure(candidate, size, role) <= width:
            lines[-2], lines[-1] = head, candidate

    def paragraph(
        self,
        content: str,
        box,
        size: float,
        color: Color,
        role: str = "body",
        leading: float = 1.45,
        valign: str = "top",
        max_lines: int | None = None,
    ) -> float:
        x, y, w, h = box
        step = size * leading
        lines = self.wrap(content, size, w, role)
        limit = max(1, int(h // step)) if h else len(lines)
        if max_lines is not None:
            limit = min(limit, max_lines)
        if len(lines) > limit:
            lines = lines[:limit]
            lines[-1] = self.ellipsize(lines[-1] + " …", size, w, role)
        top = y + (h - len(lines) * step) / 2 if valign == "center" else y
        for i, line in enumerate(lines):
            baseline_pad = (step - size * 1.2) / 2
            self.text(line, (x, top + i * step + baseline_pad), size, color, role)
        return top + len(lines) * step

    def blit(self, image: pygame.Surface, pos: tuple[float, float], anchor="topleft"):
        rect = image.get_rect(**{anchor: self.point(*pos)})
        self.surface.blit(image, rect)
        return self.logical(rect)


# 16px stroke icons (drawn, so they scale cleanly)


def icon(p: Painter, name: str, x: float, y: float, color: Color, size: float = 16):
    s = size / 16
    w = 1.6

    def pt(u: float, v: float) -> tuple[float, float]:
        return x + u * s, y + v * s

    if name == "folder":
        p.polyline(
            [pt(2, 4), pt(6.5, 4), pt(8, 5.8), pt(14, 5.8), pt(14, 13), pt(2, 13)],
            color,
            w,
            closed=True,
        )
    elif name == "restart":
        arc = [
            pt(
                8 + 5.2 * math.cos(math.radians(a)),
                8.6 + 5.2 * math.sin(math.radians(a)),
            )
            for a in range(-120, 181, 20)
        ]
        p.polyline(arc, color, w)
        p.polyline([pt(2.2, 3.6), pt(2.8, 8.0), pt(6.8, 6.6)], color, w)
    elif name == "hint":
        bulb = [
            pt(
                8 + 4.4 * math.cos(math.radians(a)),
                6.4 + 4.4 * math.sin(math.radians(a)),
            )
            for a in range(130, 411, 20)
        ]
        p.polyline(bulb, color, w)
        p.polyline([pt(6, 13.2), pt(10, 13.2)], color, w)
        p.polyline([pt(6.4, 11), pt(9.6, 11)], color, w)
    elif name == "play":
        p.polyline([pt(4.5, 2.5), pt(13, 8), pt(4.5, 13.5)], color, w, closed=True)
    elif name == "stop":
        p.polyline([pt(4, 4), pt(12, 4), pt(12, 12), pt(4, 12)], color, w, closed=True)
    elif name == "chevron-right":
        p.polyline([pt(6, 3.5), pt(10.5, 8), pt(6, 12.5)], color, w)
    elif name == "chevron-down":
        p.polyline([pt(3.5, 6), pt(8, 10.5), pt(12.5, 6)], color, w)
