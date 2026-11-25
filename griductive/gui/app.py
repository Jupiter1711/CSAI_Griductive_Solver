import math
import re
import sys
import time
from pathlib import Path

import pygame

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.engine import GameEngine
from griductive.gui import GameUI
from griductive.gui import avatar as portraits
from griductive.gui import widgets
from griductive.gui.controller import GameController, Message, MessageKind
from griductive.gui.text import cell_label, column_letter
from griductive.gui.theme import DEFAULT_THEME, RGB, Color, Theme
from griductive.gui.widgets import Box, Painter, icon
from griductive.models import Cell, Character, Status
from griductive.puzzle_io import PuzzleLoader
from griductive.regions import RegionResolver

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLBAR_BUTTONS = ("load", "restart", "hint", "auto")
SHORTCUTS = (
    ("↑↓←→", "move"),
    ("I", "innocent"),
    ("C", "criminal"),
    ("H", "hint"),
    ("A", "auto"),
    ("R", "restart"),
)

# Feedback box: title and tone (good / bad / neutral) per controller message.
FEEDBACK = {
    MessageKind.ACCEPTED: ("PROVEN", "good"),
    MessageKind.SOLVED: ("SOLVED", "good"),
    MessageKind.CONTRADICTED: ("NOT PROVABLE THAT WAY", "bad"),
    MessageKind.NOT_PROVABLE: ("NOT PROVABLE YET", "neutral"),
    MessageKind.HINT: ("HINT", "neutral"),
    MessageKind.STUCK: ("STUCK", "neutral"),
    MessageKind.ALREADY_REVEALED: ("ALREADY KNOWN", "neutral"),
    MessageKind.INCONSISTENT: ("INCONSISTENT CLUES", "bad"),
    MessageKind.ERROR: ("ERROR", "bad"),
    MessageKind.BUSY: ("WORKING", "neutral"),
}


class PygameUI(GameUI):
    def __init__(
        self,
        puzzle_dirs: tuple[Path, ...] = (REPO_ROOT / "puzzles",),
        initial_puzzle: Path | None = None,
        theme: Theme = DEFAULT_THEME,
        step_delay: float = 0.45,
        fps: int = 60,
    ) -> None:
        self.puzzle_dirs = puzzle_dirs
        self.initial_puzzle = initial_puzzle
        self.theme = theme
        self.step_delay = step_delay
        self.fps = fps

    def run(
        self,
        engine: GameEngine,
        agent: LogicAgent,
        runner: DeductionRunner,
        loader: PuzzleLoader,
        regions: RegionResolver,
    ) -> None:
        controller = GameController(
            engine, agent, runner, loader, regions, step_delay=self.step_delay
        )
        window = GriductiveWindow(controller, self.puzzle_dirs, self.theme)
        window.loop(self.initial_puzzle, self.fps)


class GriductiveWindow:
    def __init__(
        self,
        controller: GameController,
        puzzle_dirs: tuple[Path, ...],
        theme: Theme = DEFAULT_THEME,
    ) -> None:
        self.ctl = controller
        self.puzzle_dirs = puzzle_dirs
        self.theme = theme
        self.m = theme.metrics
        self.c = theme.colors
        _enable_dpi_awareness()
        pygame.init()
        pygame.display.set_caption("Griductive")
        size = _initial_window_size(theme)
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)

        self.hits: dict[str, pygame.Rect] = {}
        self.mouse = (-1.0, -1.0)
        self.pressed: str | None = None
        self.focus_key: str | None = None
        self.focus_visible = False
        self.log_open = False
        self.clue_scroll = 0.0
        self.picker_open = False
        self.picker_files: list[Path] = []
        self.picker_scroll = 0
        self._hover: dict[Cell, float] = {}
        self._dismissed: Message | None = None
        self._last_clue_id: str | None = None
        self._last_frame = time.monotonic()
        self._list_rect = Box(0, 0, 0, 0)
        self._painter: Painter | None = None

    # Main loop

    def loop(self, initial_puzzle: Path | None = None, fps: int = 60) -> None:
        if initial_puzzle is not None:
            self.ctl.load(initial_puzzle)
        else:
            self.open_picker()
        clock = pygame.time.Clock()
        running = True
        try:
            while running:
                for event in pygame.event.get():
                    running = self.handle(event) and running
                self.ctl.poll()
                self.frame()
                pygame.display.flip()
                clock.tick(fps)
        finally:
            self.close()

    def close(self) -> None:
        self.ctl.shutdown()
        widgets.clear_caches()
        portraits.clear_caches()
        pygame.quit()

    def painter(self) -> Painter:
        surface = pygame.display.get_surface()
        width, height = surface.get_size()
        logical_w, logical_h = self.m.canvas
        scale = min(width / logical_w, height / logical_h)
        offset = ((width - logical_w * scale) / 2, (height - logical_h * scale) / 2)
        return Painter(surface, self.theme, scale, offset)

    def frame(self) -> pygame.Surface:
        now = time.monotonic()
        dt, self._last_frame = now - self._last_frame, now
        p = self._painter = self.painter()
        p.surface.fill(self.c.bg)
        self.hits = {}
        self._draw_header(p)
        self._draw_board(p, now, dt)
        self._draw_panel(p, now)
        if self.picker_open:
            self._draw_picker(p)
        self._draw_focus_ring(p)
        return p.surface

    # Input

    def handle(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.mouse = self._to_logical(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self._to_logical(event.pos)
            self.pressed = self._hit(pos)
            self.focus_visible = False
            self.click(pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.pressed = None
        elif event.type == pygame.MOUSEWHEEL:
            if self.picker_open:
                self._scroll_picker(-event.y)
            elif self._list_rect.collidepoint(self.mouse):
                self.clue_scroll = max(0.0, self.clue_scroll - event.y * 40)
        elif event.type == pygame.KEYDOWN:
            return self.key(event.key, event.mod)
        return True

    def key(self, key: int, mod: int = 0) -> bool:
        if key == pygame.K_TAB:
            self._move_focus(-1 if mod & pygame.KMOD_SHIFT else 1)
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.focus_visible and self.focus_key in self.hits:
                self._activate(self.focus_key)
            return True
        if self.picker_open:
            if key == pygame.K_ESCAPE:
                self.picker_open = False
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self._scroll_picker(1 if key == pygame.K_DOWN else -1)
            return True
        moves = {
            pygame.K_LEFT: (0, -1),
            pygame.K_RIGHT: (0, 1),
            pygame.K_UP: (-1, 0),
            pygame.K_DOWN: (1, 0),
        }
        if key in moves:
            self.ctl.move_selection(*moves[key])
            self._dismissed = self.ctl.message
        elif key == pygame.K_c:
            self._activate("criminal")
        elif key == pygame.K_i:
            self._activate("innocent")
        elif key == pygame.K_h:
            self._activate("hint")
        elif key == pygame.K_a:
            self._activate("auto")
        elif key == pygame.K_r:
            self._activate("restart")
        elif key == pygame.K_l:
            self._activate("load")
        elif key == pygame.K_ESCAPE:
            if self.ctl.selected_clue_id is not None:
                self.ctl.select_clue(None)
        return True

    def _hit(self, pos) -> str | None:
        return next((k for k, r in self.hits.items() if r.collidepoint(pos)), None)

    def click(self, pos) -> None:
        if self.picker_open:
            key = self._hit(pos)
            if key is not None and key.startswith("pick:"):
                self._activate(key)
            elif key != "picker":
                self.picker_open = False
            return
        key = self._hit(pos)
        if key is not None and key != "picker":
            self.focus_key = key
            self._activate(key)

    def _activate(self, key: str) -> None:
        if key.startswith("pick:"):
            self.picker_open = False
            self.ctl.load(self.picker_files[int(key[5:])])
        elif key in TOOLBAR_BUTTONS:
            self._press(key)
        elif key in ("innocent", "criminal"):
            if self.ctl.can_submit():
                self.ctl.submit(
                    Status.INNOCENT if key == "innocent" else Status.CRIMINAL
                )
        elif key.startswith("card:"):
            row, col = map(int, key[5:].split(","))
            self.ctl.select_cell(Cell(row, col))
            self._dismissed = self.ctl.message
        elif key.startswith("clue:"):
            self.ctl.select_clue(key[5:])
        elif key == "log":
            self.log_open = not self.log_open

    def _press(self, name: str) -> None:
        if not self._enabled(name):
            return
        if name == "load":
            self.open_picker()
        elif name == "restart":
            self.ctl.restart()
        elif name == "hint":
            self.ctl.request_hint()
        elif name == "auto":
            self.ctl.toggle_auto()

    def _enabled(self, name: str) -> bool:
        ctl = self.ctl
        loaded = ctl.state is not None
        if name == "load":
            return not ctl.busy
        if name == "restart":
            return loaded and not ctl.busy
        if name == "hint":
            return loaded and not ctl.busy and not ctl.solved
        if name == "auto":
            return ctl.auto_running or (loaded and not ctl.busy and not ctl.solved)
        return True

    def _focus_order(self) -> list[str]:
        if self.picker_open:
            return [k for k in self.hits if k.startswith("pick:")]
        keys = [k for k in TOOLBAR_BUTTONS if self._enabled(k)]
        if self.ctl.can_submit():
            keys += ["innocent", "criminal"]
        keys += [k for k in self.hits if k.startswith("clue:")]
        return keys + ["log"]

    def _move_focus(self, step: int) -> None:
        order = self._focus_order()
        if not order:
            return
        if self.focus_key in order and self.focus_visible:
            index = (order.index(self.focus_key) + step) % len(order)
        else:
            index = 0 if step > 0 else len(order) - 1
        self.focus_key = order[index]
        self.focus_visible = True

    def open_picker(self) -> None:
        files: dict[Path, None] = {}
        for folder in self.puzzle_dirs:
            if folder.is_dir():
                for path in sorted(folder.glob("*.json")):
                    files[path.resolve()] = None
        self.picker_files = list(files)
        self.picker_scroll = 0
        self.picker_open = True

    def _picker_rows(self) -> int:
        return max(1, int((self.m.canvas[1] - 2 * self.m.padding - 118) // 60))

    def _scroll_picker(self, rows: int) -> None:
        hidden = max(0, len(self.picker_files) - self._picker_rows())
        self.picker_scroll = max(0, min(hidden, self.picker_scroll + rows))

    def _to_logical(self, pos) -> tuple[float, float]:
        p = self._painter or self.painter()
        return (
            (pos[0] - p.offset[0]) / p.scale,
            (pos[1] - p.offset[1]) / p.scale,
        )

    def _hovered(self, rect) -> bool:
        return not self.picker_open and Box(rect).collidepoint(self.mouse)

    def _register(self, key: str, rect) -> pygame.Rect:
        box = pygame.Rect(
            round(rect[0]), round(rect[1]), round(rect[2]), round(rect[3])
        )
        self.hits[key] = box
        return box

    # Layout helpers

    def _content(self) -> tuple[float, float, float, float]:
        width, height = self.m.canvas
        pad = self.m.padding
        return pad, self.m.header_h + 40, width - pad, height - pad

    def _panel_x(self) -> float:
        return self._content()[2] - self.m.panel_w

    def _grid(self) -> tuple[float, float, float, float, float, float]:
        left, top, _, _ = self._content()
        n = self.ctl.state.board.size if self.ctl.state else 3
        gap = self.m.gap
        area_left = left + 40
        area_right = self._panel_x() - 56
        width = min(self.m.board_max_w, area_right - area_left)
        x = area_left + (area_right - area_left - width) / 2
        height = 3 * self.m.card_h_3x3 + 2 * gap
        y = top + 26
        card_w = (width - gap * (n - 1)) / n
        card_h = (height - gap * (n - 1)) / n
        return x, y, width, height, card_w, card_h

    def card_rect(self, cell: Cell) -> pygame.Rect:
        x, y, _, _, card_w, card_h = self._grid()
        gap = self.m.gap
        return pygame.Rect(
            round(x + cell.col * (card_w + gap)),
            round(y + cell.row * (card_h + gap)),
            round(card_w),
            round(card_h),
        )

    # Header

    def _draw_header(self, p: Painter) -> None:
        m, c = self.m, self.c
        mid = m.header_h / 2
        left = m.padding
        dot_r = m.logo_dot / 2
        p.circle((left + dot_r, mid), dot_r + m.logo_halo, c.accent_halo)
        p.circle((left + dot_r, mid), dot_r, c.accent)
        title = p.text(
            "Griductive",
            (left + m.logo_dot + 14, mid),
            m.logo,
            c.ink,
            "display",
            "midleft",
        )
        if self.ctl.state is not None:
            size = self.ctl.state.board.size
            label = f"{_pretty_name(self.ctl.puzzle_name)} · {size}×{size}"
            text_w = p.measure(label, m.mono_label, "mono")
            chip = Box(title.right + 16, mid - 14, text_w + 24, 28)
            p.stroke(chip, c.line, 1, 14)
            p.text(label, chip.center, m.mono_label, c.ink_muted, "mono", "center")

        x = m.canvas[0] - m.padding
        specs = {
            "load": ("Load", "folder"),
            "restart": ("Restart", "restart"),
            "hint": ("Hint", "hint"),
            "auto": (
                ("Stop", "stop") if self.ctl.auto_running else ("Auto solve", "play")
            ),
        }
        for name in reversed(TOOLBAR_BUTTONS):
            label, glyph = specs[name]
            width = 16 + m.icon + 8 + p.measure(label, m.button_text, "medium") + 18
            x -= width
            rect = Box(x, mid - m.button_h / 2, width, m.button_h)
            x -= 10
            self._register(name, rect)
            self._header_button(p, name, rect, label, glyph)

        clock = _clock(self.ctl.elapsed())
        p.text(clock, (x - 18, mid), m.mono_clock, c.ink_muted, "mono", "midright")
        p.fill((0, m.header_h - 1, m.canvas[0], 1), c.hairline)

    def _header_button(
        self, p: Painter, name: str, rect, label: str, glyph: str
    ) -> None:
        m, c = self.m, self.c
        enabled = self._enabled(name)
        hovered = enabled and self._hovered(rect)
        if name == "auto":
            fill, border, fg = c.accent, None, c.on_accent
        elif name == "hint":
            fill, border, fg = None, c.accent, c.accent
        else:
            fill, border, fg = None, c.line, c.ink
        if hovered and fill is None:
            fill = c.hover
        opacity = 1.0 if enabled else 0.4
        if fill is not None:
            p.fill(rect, widgets.fade(fill, c.bg, opacity), m.radius_btn)
        if border is not None:
            p.stroke(rect, widgets.fade(border, c.bg, opacity), 1, m.radius_btn)
        color = widgets.fade(fg, widgets.blend(fill or c.bg, c.bg), opacity)
        shift = 1 if self.pressed == name else 0
        icon(p, glyph, rect.x + 16, rect.centery - m.icon / 2 + shift, color, m.icon)
        p.text(
            label,
            (rect.x + 16 + m.icon + 8, rect.centery + shift),
            m.button_text,
            color,
            "medium",
            "midleft",
        )

    # Board

    def _draw_board(self, p: Painter, now: float, dt: float) -> None:
        m, c, state = self.m, self.c, self.ctl.state
        x, y, width, height, card_w, card_h = self._grid()
        if state is None:
            self._draw_empty(p, (x, y, width, height))
            return

        n = state.board.size
        for col in range(n):
            cx = x + col * (card_w + m.gap) + card_w / 2
            p.text(
                column_letter(col),
                (cx, y - 22),
                m.mono_label,
                c.ink_faint,
                "mono",
                "center",
            )
        for row in range(n):
            cy = y + row * (card_h + m.gap) + card_h / 2
            p.text(
                str(row + 1), (x - 34, cy), m.mono_label, c.ink_faint, "mono", "center"
            )

        focus = self.ctl.focus()
        for character in state.board.characters:
            cell = character.cell
            base = self.card_rect(cell)
            self._register(f"card:{cell.row},{cell.col}", base)
            rect = Box(base).move(self._shake(cell, now), -self._lift(cell, base, dt))
            selected = cell == self.ctl.selected_cell
            if selected:
                p.soft_shadow(rect, c.accent_glow, m.radius_card, 10, 28)
            self._draw_card(p, rect, character, now)
            if selected:
                ring = rect.inflate(m.selected_ring * 2, m.selected_ring * 2)
                p.stroke(
                    ring, c.accent, m.selected_ring, m.radius_card + m.selected_ring
                )
            if focus is not None and cell in focus.cells:
                pad = m.spotlight_offset
                p.dashed(
                    rect.inflate(pad * 2, pad * 2),
                    c.spotlight,
                    m.spotlight_width,
                    m.radius_card + pad,
                    m.spotlight_dash,
                )
        self._draw_progress(p, x, y + height + 22, width)

    def _draw_empty(self, p: Painter, box) -> None:
        m, c = self.m, self.c
        cx, cy = Box(box).center
        p.text("No puzzle loaded", (cx, cy - 20), 30, c.ink, "display", "center")
        p.text(
            "Load a puzzle to start. Every verdict must follow from the clues.",
            (cx, cy + 18),
            m.clue_list,
            c.ink_muted,
            "body",
            "center",
        )

    def _lift(self, cell: Cell, rect, dt: float) -> float:
        target = 1.0 if self._hovered(rect) else 0.0
        value = self._hover.get(cell, 0.0)
        step = dt / (self.m.hover_ms / 1000) if self.m.hover_ms else 1.0
        value = (
            min(target, value + step) if target > value else max(target, value - step)
        )
        self._hover[cell] = value
        return self.m.hover_lift * value

    def _shake(self, cell: Cell, now: float) -> float:
        rejection = self.ctl.rejection
        if rejection is None or rejection[0] != cell:
            return 0.0
        age = now - rejection[1]
        span = self.m.shake_ms / 1000
        if age >= span:
            return 0.0
        return math.sin(age * 55) * 5 * (1 - age / span)

    def _verdict_style(self, status: Status) -> tuple[RGB, Color, RGB, Color, str]:
        c = self.c
        if status is Status.INNOCENT:
            return (
                c.innocent_bg,
                c.innocent_line,
                c.innocent_text,
                c.innocent_chip,
                "Innocent",
            )
        return (
            c.criminal_bg,
            c.criminal_line,
            c.criminal_text,
            c.criminal_chip,
            "Criminal",
        )

    def _draw_card(self, p: Painter, rect, character: Character, now: float) -> None:
        status = self.ctl.verdict_of(character.cell)
        started = self.ctl.reveal_times.get(character.cell)
        span = self.m.flip_ms / 1000
        progress = 1.0 if started is None else min(1.0, (now - started) / span)
        if progress >= 1.0:
            self._card_face(p, rect, character, status)
            return
        # Flip: render onto a layer, squeeze it horizontally (rotateY look).
        device = p.device(rect)
        layer = pygame.Surface(device.size, pygame.SRCALPHA)
        sub = Painter(
            layer, self.theme, p.scale, (-rect.x * p.scale, -rect.y * p.scale)
        )
        front = progress >= 0.5
        self._card_face(sub, rect, character, status if front else None)
        squeeze = abs(1 - 2 * progress)
        width = max(1, round(device.w * squeeze))
        layer = pygame.transform.smoothscale(layer, (width, device.h))
        p.surface.blit(layer, (device.centerx - width // 2, device.y))

    def _card_face(self, p: Painter, rect, character: Character, status) -> None:
        m, c = self.m, self.c
        pad = m.card_pad
        rect = Box(rect)
        if status is None:
            p.fill(rect, c.card, m.radius_card)
            p.stroke(rect, c.hairline, 1, m.radius_card)
            self._unknown_body(p, rect, character)
            return

        bg, border, chip_fg, chip_bg, chip_label = self._verdict_style(status)
        p.fill(rect, bg, m.radius_card)
        p.stroke(rect, border, 1, m.radius_card)
        size = m.avatar_revealed
        p.blit(
            portraits.avatar(self.theme, character.name, p.px(size)),
            (rect.x + pad, rect.y + pad),
        )
        text_x = rect.x + pad + size + 10
        chip = self._chip_rect(p, chip_label, rect.right - pad, rect.y + pad + 2)
        # Narrow cards (4x4, 5x5): the chip sits on the second line after the
        # cell label (the profession is still shown in the side panel), so the
        # clue keeps the room below the header.
        name_w = p.measure(character.name, m.card_name, "semibold")
        compact = chip.x - 8 - text_x < max(name_w, 64)
        role_y = rect.y + pad + 20
        if compact:
            text_w = rect.right - pad - text_x
            role = cell_label(character.cell)
            role_w = p.measure(role, m.mono_small, "mono")
            chip_top = role_y + m.mono_small * 0.6 - chip.h / 2
            chip = Box(text_x + role_w + 8, chip_top, chip.w, chip.h)
        else:
            text_w = chip.x - 8 - text_x
            role = p.ellipsize(
                f"{cell_label(character.cell)} · {character.profession}",
                m.mono_small,
                text_w,
                "mono",
            )
        p.fill(chip, widgets.blend(chip_bg, bg), chip.h / 2)
        p.text(chip_label, chip.center, m.mono_small, chip_fg, "mono", "center")
        name = p.ellipsize(character.name, m.card_name, text_w, "semibold")
        p.text(name, (text_x, rect.y + pad - 2), m.card_name, c.ink, "semibold")
        p.text(role, (text_x, role_y), m.mono_small, c.ink_muted, "mono")
        header_bottom = max(chip.bottom, rect.y + pad + size)

        clue = self.ctl.clue_of_owner(character.cell)
        if clue is not None:
            top = header_bottom + 12
            body = (rect.x + pad, top, rect.w - 2 * pad, rect.bottom - pad - top)
            text = self.ctl.describe(clue)
            size_px = self._clue_size(p, text, body, rect.h)
            p.paragraph(
                text,
                body,
                size_px,
                c.ink_body,
                "body",
                1.45,
                "center",
            )

    def _clue_size(self, p: Painter, text: str, body, card_h: float) -> float:
        m = self.m
        size = m.clue_card if card_h >= 180 else m.clue_card_small
        _, _, w, h = body
        while size > m.clue_card_min:
            if len(p.wrap(text, size, w, "body")) * size * 1.45 <= h:
                break
            size -= 1
        return size

    def _unknown_body(self, p: Painter, rect, character: Character) -> None:
        m, c = self.m, self.c
        pad = m.card_pad
        p.text(
            cell_label(character.cell),
            (rect.x + pad, rect.y + pad - 2),
            m.mono_label,
            c.ink_faint,
            "mono",
        )
        size = max(28, min(m.avatar_unknown, rect.h - 92, rect.w - 2 * pad))
        block = size + 12 + 20 + 16
        top = rect.y + max(pad + 16, (rect.h - block) / 2 + 6)
        p.blit(
            portraits.avatar(self.theme, character.name, p.px(size)),
            (rect.centerx, top),
            "midtop",
        )
        name = p.ellipsize(character.name, m.card_name, rect.w - 2 * pad, "semibold")
        name_rect = p.text(
            name,
            (rect.centerx, top + size + 10),
            m.card_name,
            c.ink,
            "semibold",
            "midtop",
        )
        role = p.ellipsize(character.profession, m.mono_small, rect.w - 2 * pad, "mono")
        p.text(
            role,
            (rect.centerx, name_rect.bottom + 1),
            m.mono_small,
            c.ink_muted,
            "mono",
            "midtop",
        )

    def _chip_rect(self, p: Painter, label: str, right: float, top: float):
        width = p.measure(label, self.m.mono_small, "mono") + 16
        return Box(right - width, top, width, self.m.mono_small + 10)

    def _draw_progress(self, p: Painter, x: float, y: float, width: float) -> None:
        m, c, state = self.m, self.c, self.ctl.state
        assert state is not None
        known = len({v.cell for v in state.verdicts})
        total = state.board.size**2
        label = f"{known} / {total} proven"
        label_w = p.measure(label, m.mono_label, "mono")
        track = Box(x, y, width - label_w - 20, m.progress_h)
        p.fill(track, c.progress_track, m.progress_h / 2)
        done = track.copy()
        done.w = track.w * known / total
        if done.w > 0:
            p.fill(done, c.accent, m.progress_h / 2)
        p.text(
            label,
            (x + width, track.centery),
            m.mono_label,
            c.ink_muted,
            "mono",
            "midright",
        )

        cursor = x
        for keys, action in SHORTCUTS:
            if not widgets.has_glyphs(self.theme, "mono", keys):
                keys = "arrows"
            item = p.text(keys, (cursor, y + 26), m.mono_small, c.ink_muted, "mono")
            item = p.text(
                f" {action}", (item.right, y + 26), m.mono_small, c.ink_faint, "mono"
            )
            cursor = item.right + 18

    # Right panel

    def _draw_panel(self, p: Painter, now: float) -> None:
        m = self.m
        x = self._panel_x()
        _, top, _, bottom = self._content()
        suspect = self._draw_suspect(p, x, top, now)
        log = self._draw_log(p, x, bottom)
        clues_top = suspect.bottom + m.panel_gap
        self._draw_clues(
            p, Box(x, clues_top, m.panel_w, log.y - m.panel_gap - clues_top)
        )

    def _draw_suspect(self, p: Painter, x: float, top: float, now: float) -> Box:
        m, c, ctl = self.m, self.c, self.ctl
        pad = m.panel_pad
        inner_w = m.panel_w - 2 * pad
        feedback = self._feedback()
        lines: list[str] = []
        if feedback is not None:
            lines = p.wrap(feedback[1], m.feedback_text, inner_w - 32, "body")[:4]
        feedback_h = 0 if feedback is None else 46 + len(lines) * m.feedback_text * 1.45
        height = pad + m.avatar_panel + 20 + m.verdict_button_h + pad
        if feedback is not None:
            height += 16 + feedback_h
        card = Box(x, top, m.panel_w, height)
        p.fill(card, c.surface, m.radius_panel)
        p.stroke(card, c.hairline, 1, m.radius_panel)

        state, cell = ctl.state, ctl.selected_cell
        character = None
        if state is not None and cell is not None:
            character = next(
                (ch for ch in state.board.characters if ch.cell == cell), None
            )
        ax, ay = x + pad, top + pad
        tx = ax + m.avatar_panel + 16
        if character is None:
            p.circle(
                (ax + m.avatar_panel / 2, ay + m.avatar_panel / 2),
                m.avatar_panel / 2,
                c.card,
            )
            p.stroke(
                (ax, ay, m.avatar_panel, m.avatar_panel),
                c.hairline,
                1,
                m.avatar_panel / 2,
            )
            p.text("SELECT A CARD", (tx, ay + 6), m.mono_label, c.ink_muted, "mono")
            p.text("No suspect", (tx, ay + 22), m.panel_name, c.ink, "display")
        else:
            p.blit(
                portraits.avatar(self.theme, character.name, p.px(m.avatar_panel)),
                (ax, ay),
            )
            status = ctl.verdict_of(character.cell)
            if status is None:
                chip_label, chip_fg, chip_bg, under = (
                    "Unknown",
                    c.ink_muted,
                    c.neutral_chip,
                    c.surface,
                )
            else:
                _, _, chip_fg, chip_bg, chip_label = self._verdict_style(status)
                under = c.surface
            chip = self._chip_rect(p, chip_label, card.right - pad, ay + 4)
            p.fill(chip, widgets.blend(chip_bg, under), chip.h / 2)
            p.text(chip_label, chip.center, m.mono_small, chip_fg, "mono", "center")
            meta = p.ellipsize(
                f"{cell_label(character.cell)} · {character.profession}",
                m.mono_label,
                chip.x - 12 - tx,
                "mono",
            )
            p.text(meta, (tx, ay + 4), m.mono_label, c.ink_muted, "mono")
            name = p.ellipsize(
                character.name, m.panel_name, card.right - pad - tx, "display"
            )
            p.text(name, (tx, ay + 20), m.panel_name, c.ink, "display")

        by = ay + m.avatar_panel + 20
        width = (inner_w - 12) / 2
        enabled = ctl.can_submit()
        for i, (key, label, status_) in enumerate(
            (
                ("innocent", "Innocent", Status.INNOCENT),
                ("criminal", "Criminal", Status.CRIMINAL),
            )
        ):
            rect = Box(ax + i * (width + 12), by, width, m.verdict_button_h)
            self._register(key, rect)
            self._verdict_button(p, rect, key, label, status_, enabled)

        if feedback is not None:
            box = Box(ax, by + m.verdict_button_h + 16, inner_w, feedback_h)
            self._draw_feedback(p, box, feedback, lines, now)
        return card

    def _verdict_button(self, p: Painter, rect, key: str, label: str, status, enabled):
        m, c = self.m, self.c
        bg, border, fg, chip_bg, _ = self._verdict_style(status)
        opacity = 1.0 if enabled else 0.4
        hovered = enabled and self._hovered(rect)
        fill = widgets.blend(chip_bg, bg) if hovered else bg
        p.fill(rect, widgets.fade(fill, c.surface, opacity), m.radius_btn)
        p.stroke(rect, widgets.fade(border, c.surface, opacity), 1, m.radius_btn)
        color = widgets.fade(fg, fill, opacity)
        shift = 1 if self.pressed == key and enabled else 0
        text_w = p.measure(label, m.button_text, "semibold")
        badge_w = 20
        start = rect.centerx - (text_w + 10 + badge_w) / 2
        p.text(
            label,
            (start, rect.centery + shift),
            m.button_text,
            color,
            "semibold",
            "midleft",
        )
        badge = Box(start + text_w + 10, rect.centery - 10 + shift, badge_w, 20)
        p.fill(badge, widgets.fade(widgets.blend(chip_bg, fill), c.surface, opacity), 5)
        p.text(
            key[0].upper(), badge.center, m.mono_small, color, "mono_medium", "center"
        )

    def _feedback(self) -> tuple[str, str, str] | None:
        ctl = self.ctl
        if ctl.busy and not ctl.auto_running:
            return "WORKING", f"{ctl.job_name}…", "neutral"
        message = ctl.message
        if message is self._dismissed or message.kind is MessageKind.INFO:
            return None
        title, tone = FEEDBACK.get(message.kind, ("NOTE", "neutral"))
        return title, message.text, tone

    def _draw_feedback(self, p: Painter, box, feedback, lines: list[str], now: float):
        m, c = self.m, self.c
        title, _, tone = feedback
        if tone == "bad":
            bg, border, title_c = (
                c.criminal_feedback_bg,
                c.criminal_feedback_line,
                c.criminal_text,
            )
        elif tone == "good":
            bg, border, title_c = (
                c.innocent_feedback_bg,
                c.innocent_feedback_line,
                c.innocent_text,
            )
        else:
            bg, border, title_c = c.surface_2, c.line, c.ink_muted
        p.fill(box, widgets.blend(bg, c.surface), m.radius_btn + 2)
        p.stroke(box, border, 1, m.radius_btn + 2)
        p.text(title, (box.x + 16, box.y + 14), m.mono_small, title_c, "mono_medium")
        step = m.feedback_text * 1.45
        for i, line in enumerate(lines):
            p.text(
                line,
                (box.x + 16, box.y + 36 + i * step),
                m.feedback_text,
                c.ink_body,
                "body",
            )

    def _draw_clues(self, p: Painter, panel: Box) -> None:
        m, c, ctl, state = self.m, self.c, self.ctl, self.ctl.state
        p.fill(panel, c.surface, m.radius_panel)
        p.stroke(panel, c.hairline, 1, m.radius_panel)
        pad = 24
        title = p.text(
            "Clues", (panel.x + pad, panel.y + pad), m.section_title, c.ink, "display"
        )
        count = 0 if state is None else len(state.clues)
        p.text(
            f"{count} revealed · tap to spotlight",
            (panel.right - pad, title.centery),
            m.mono_small,
            c.ink_muted,
            "mono",
            "midright",
        )
        area = Box(
            panel.x + 12,
            title.bottom + 14,
            panel.w - 24,
            panel.bottom - title.bottom - 26,
        )
        self._list_rect = area
        if state is None or not state.clues:
            p.text(
                "No clues revealed yet.",
                (area.x + 12, area.y + 8),
                m.clue_list,
                c.ink_muted,
            )
            return

        text_x = 12 + m.avatar_clue + 12
        text_w = area.w - text_x - 12
        step = m.clue_list * 1.45
        rows = []
        for clue in state.clues:
            lines = p.wrap(ctl.describe(clue), m.clue_list, text_w, "body")
            rows.append((clue, lines, 12 + 22 + len(lines) * step + 12))
        total = sum(height for *_, height in rows)
        self._scroll_into_view(rows, area)
        self.clue_scroll = max(0.0, min(self.clue_scroll, max(0.0, total - area.h)))

        board = state.board
        with p.clip(area):
            y = area.y - self.clue_scroll
            for clue, lines, height in rows:
                row = Box(area.x, y, area.w, height)
                y += height
                if row.bottom < area.y or row.y > area.bottom:
                    continue
                self._register(f"clue:{clue.id}", row.clip(area))
                if clue.id == ctl.selected_clue_id:
                    p.fill(row, widgets.blend(c.spotlight_bg, c.surface), 12)
                    p.stroke(row, c.spotlight_line, 1, 12)
                elif self._hovered(row):
                    p.fill(row, widgets.blend(c.hover, c.surface), 12)
                owner = next(ch for ch in board.characters if ch.cell == clue.owner)
                p.blit(
                    portraits.avatar(self.theme, owner.name, p.px(m.avatar_clue)),
                    (row.x + 12, row.y + 12),
                )
                name = p.text(
                    owner.name,
                    (row.x + text_x, row.y + 10),
                    m.clue_list + 1,
                    c.ink,
                    "semibold",
                )
                p.text(
                    cell_label(clue.owner),
                    (name.right + 6, name.centery + 1),
                    m.mono_small,
                    c.ink_muted,
                    "mono",
                    "midleft",
                )
                for i, line in enumerate(lines):
                    p.text(
                        line,
                        (row.x + text_x, row.y + 32 + i * step),
                        m.clue_list,
                        c.ink_body,
                    )

        if total > area.h:
            track = Box(area.right + 4, area.y + 4, 2, area.h - 8)
            p.fill(track, c.hairline, 1)
            thumb_h = max(24, track.h * area.h / total)
            thumb_y = track.y + (track.h - thumb_h) * self.clue_scroll / max(
                1, total - area.h
            )
            p.fill((track.x, thumb_y, 2, thumb_h), c.line, 1)

    def _scroll_into_view(self, rows: list, area) -> None:
        selected = self.ctl.selected_clue_id
        if selected == self._last_clue_id:
            return
        self._last_clue_id = selected
        offset = 0.0
        for clue, _, height in rows:
            if clue.id == selected:
                if offset < self.clue_scroll:
                    self.clue_scroll = offset
                elif offset + height > self.clue_scroll + area.h:
                    self.clue_scroll = offset + height - area.h
                return
            offset += height

    def _draw_log(self, p: Painter, x: float, bottom: float) -> Box:
        m, c, info = self.m, self.c, self.ctl.info
        rows = (
            ("SAT calls", str(info.sat_calls)),
            ("Decisions", str(info.decisions)),
            ("Propagations", str(info.propagations)),
            ("Backtracks", str(info.backtracks)),
            ("Primary vars", str(info.primary)),
            ("Auxiliary vars", str(info.auxiliary)),
            ("Clauses", str(info.clauses)),
            ("SAT time", f"{info.runtime_s:.3f} s"),
        )
        header_h = 48
        height = header_h + (len(rows) * 24 + 12 if self.log_open else 0)
        box = Box(x, bottom - height, m.panel_w, height)
        p.fill(box, c.surface_2, m.radius_panel)
        p.stroke(box, c.hairline, 1, m.radius_panel)
        header = Box(box.x, box.y, box.w, header_h)
        self._register("log", header)
        if self._hovered(header):
            p.fill(
                header.inflate(-4, -4),
                widgets.blend(c.hover, c.surface_2),
                m.radius_panel - 2,
            )
        glyph = "chevron-down" if self.log_open else "chevron-right"
        icon(p, glyph, box.x + 20, header.centery - 7, c.ink_muted, 14)
        p.text(
            "Solver log",
            (box.x + 42, header.centery),
            13,
            c.ink_muted,
            "mono",
            "midleft",
        )
        if self.log_open:
            for i, (label, value) in enumerate(rows):
                ry = box.y + header_h + i * 24
                p.text(label, (box.x + 24, ry), m.mono_label, c.ink_muted, "mono")
                p.text(value, (box.x + 200, ry), m.mono_label, c.ink, "mono")
        return box

    # Picker and focus

    def _draw_picker(self, p: Painter) -> None:
        m, c = self.m, self.c
        width, height = m.canvas
        p.fill((-width, -height, width * 3, height * 3), c.scrim)
        first = self.picker_scroll
        shown = self.picker_files[first : first + self._picker_rows()]
        box = Box(0, 0, 520, 118 + max(1, len(shown)) * 60)
        box.center = (width / 2, height / 2)
        self._register("picker", box)
        p.fill(box, c.surface, m.radius_panel)
        p.stroke(box, c.line, 1, m.radius_panel)
        p.text(
            "Load a puzzle",
            (box.x + 28, box.y + 26),
            m.section_title + 4,
            c.ink,
            "display",
        )
        more = len(self.picker_files) > len(shown)
        p.text(
            "scroll for more · esc to close" if more else "esc to close",
            (box.right - 28, box.y + 34),
            m.mono_small,
            c.ink_faint,
            "mono",
            "topright",
        )
        if not shown:
            folders = ", ".join(str(folder) for folder in self.puzzle_dirs)
            p.paragraph(
                f"No .json puzzles found in {folders}",
                (box.x + 28, box.y + 76, box.w - 56, 60),
                m.clue_list,
                c.ink_muted,
            )
        for i, path in enumerate(shown):
            row = Box(box.x + 20, box.y + 76 + i * 60, box.w - 40, 52)
            self._register(f"pick:{first + i}", row)
            hovered = row.collidepoint(self.mouse)
            p.fill(
                row,
                widgets.blend(c.hover, c.surface) if hovered else c.card,
                m.radius_btn + 2,
            )
            p.stroke(row, c.line if hovered else c.hairline, 1, m.radius_btn + 2)
            match = re.match(r"(\d+)x(\d+)-", path.stem)
            size = f"{match.group(1)}×{match.group(2)}" if match else ""
            p.text(
                _pretty_name(path.stem),
                (row.x + 18, row.centery),
                m.button_text,
                c.ink,
                "semibold",
                "midleft",
            )
            p.text(
                size,
                (row.right - 18, row.centery),
                m.mono_label,
                c.ink_muted,
                "mono",
                "midright",
            )

    def _draw_focus_ring(self, p: Painter) -> None:
        if not self.focus_visible or self.focus_key not in self.hits:
            return
        m = self.m
        rect = Box(self.hits[self.focus_key])
        gap = m.focus_offset
        radius = m.radius_btn if not self.focus_key.startswith("clue:") else 12
        p.stroke(
            rect.inflate(gap * 2, gap * 2), self.c.accent, m.focus_width, radius + gap
        )


# Helpers


def _pretty_name(name: str | None) -> str:
    if not name:
        return "No puzzle"
    name = re.sub(r"^\d+x\d+-", "", name)
    if name.isdigit():
        return f"Puzzle {name}"
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", name) if part)


def _clock(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def _initial_window_size(theme: Theme) -> tuple[int, int]:
    logical_w, logical_h = theme.metrics.canvas
    try:
        desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return logical_w, logical_h
    scale = min(desktop_w * 0.94 / logical_w, desktop_h * 0.88 / logical_h)
    return int(logical_w * scale), int(logical_h * scale)
