"""Night theme: every colour, font and size the GUI uses lives here.

Source: data/REDESIGN_BRIEF.md section 3-5 and the two reference images
in data/. Colour rules:

* accent (orange) only marks the selected cell, keyboard focus, the primary
  button, the progress bar and the Hint button;
* innocent (teal) only means innocent, criminal (red) only means criminal,
  spotlight (blue) only marks cells a selected clue talks about;
* no gradients, no layered glows, no one-sided coloured borders.

A theme is plain data; the engine and agent never see it. Colours with an
alpha channel are RGBA tuples and are blended over their background by the
drawing helpers.
"""

from dataclasses import dataclass, field
from pathlib import Path

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Color = RGB | RGBA

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _alpha(rgb: RGB, opacity: float) -> RGBA:
    return (*rgb, round(opacity * 255))


WHITE = (255, 255, 255)
ACCENT = (245, 165, 36)  # #F5A524
INNOCENT = (92, 200, 160)  # #5CC8A0
CRIMINAL = (240, 96, 93)  # #F0605D
SPOTLIGHT = (110, 168, 255)  # #6EA8FF


@dataclass(frozen=True)
class Colors:
    bg: RGB = (13, 14, 18)  # #0D0E12
    surface: RGB = (21, 23, 29)  # #15171D
    surface_2: RGB = (18, 20, 25)  # #121419
    card: RGB = (22, 24, 31)  # #16181F
    hairline: RGBA = _alpha(WHITE, 0.08)
    line: RGBA = _alpha(WHITE, 0.14)

    ink: RGB = (236, 234, 228)  # #ECEAE4
    ink_body: RGB = (218, 216, 209)  # #DAD8D1
    ink_muted: RGB = (154, 154, 163)  # #9A9AA3
    ink_faint: RGB = (138, 139, 148)  # #8A8B94

    accent: RGB = ACCENT
    on_accent: RGB = (26, 18, 5)  # #1A1205
    accent_halo: RGBA = _alpha(ACCENT, 0.14)
    accent_glow: RGBA = _alpha(ACCENT, 0.45)

    innocent: RGB = INNOCENT
    innocent_text: RGB = (127, 216, 182)  # #7FD8B6
    innocent_bg: RGB = (21, 34, 29)  # #15221D
    innocent_line: RGBA = _alpha(INNOCENT, 0.42)
    innocent_chip: RGBA = _alpha(INNOCENT, 0.12)

    criminal: RGB = CRIMINAL
    criminal_text: RGB = (244, 145, 142)  # #F4918E
    criminal_bg: RGB = (36, 23, 26)  # #24171A
    criminal_line: RGBA = _alpha(CRIMINAL, 0.48)
    criminal_chip: RGBA = _alpha(CRIMINAL, 0.12)
    criminal_feedback_bg: RGBA = _alpha(CRIMINAL, 0.08)
    criminal_feedback_line: RGBA = _alpha(CRIMINAL, 0.30)
    innocent_feedback_bg: RGBA = _alpha(INNOCENT, 0.08)
    innocent_feedback_line: RGBA = _alpha(INNOCENT, 0.30)

    spotlight: RGB = SPOTLIGHT
    spotlight_bg: RGBA = _alpha(SPOTLIGHT, 0.10)
    spotlight_line: RGBA = _alpha(SPOTLIGHT, 0.45)

    neutral_chip: RGBA = _alpha(WHITE, 0.07)
    hover: RGBA = _alpha(WHITE, 0.04)
    progress_track: RGBA = _alpha(WHITE, 0.07)
    avatar_ring: RGBA = _alpha(WHITE, 0.12)
    scrim: RGBA = (0, 0, 0, 160)
    # Muted discs behind initials when a character has no portrait file.
    monogram: tuple[RGB, ...] = (
        (40, 70, 100),
        (100, 46, 46),
        (72, 74, 82),
        (40, 82, 60),
        (98, 64, 40),
        (70, 54, 110),
        (40, 52, 96),
    )


@dataclass(frozen=True)
class Fonts:
    display: Path = FONT_DIR / "BricolageGrotesque-Bold.ttf"  # 700
    body: Path = FONT_DIR / "Inter-Regular.ttf"  # 400
    body_medium: Path = FONT_DIR / "Inter-Medium.ttf"  # 500
    body_semibold: Path = FONT_DIR / "Inter-SemiBold.ttf"  # 600
    mono: Path = FONT_DIR / "JetBrainsMono-Regular.ttf"  # 400
    mono_medium: Path = FONT_DIR / "JetBrainsMono-Medium.ttf"  # 500
    fallback_sans: str = "segoeui,arial"
    fallback_mono: str = "consolas,couriernew"


@dataclass(frozen=True)
class Metrics:
    """Logical pixels (the design is 1440 wide); the window scales them."""

    canvas: tuple[int, int] = (1440, 920)
    padding: int = 32
    header_h: int = 76
    gap: int = 12
    board_max_w: int = 780
    panel_w: int = 420
    panel_gap: int = 16
    panel_pad: int = 20
    card_pad: int = 14
    card_h_3x3: int = 212
    radius_card: int = 16
    radius_panel: int = 18
    radius_btn: int = 10
    button_h: int = 44
    verdict_button_h: int = 48
    icon: int = 16
    hit_min: int = 44
    progress_h: int = 4
    avatar_unknown: int = 96
    avatar_revealed: int = 36
    avatar_panel: int = 64
    avatar_clue: int = 28
    logo_dot: int = 20
    logo_halo: int = 5
    focus_width: int = 2
    focus_offset: int = 3
    selected_ring: int = 2
    spotlight_width: float = 1.5
    spotlight_offset: int = 4
    spotlight_dash: tuple[int, int] = (6, 4)
    hover_lift: int = 2
    hover_ms: int = 180
    flip_ms: int = 300
    shake_ms: int = 300
    # Type scale (px) per role.
    logo: int = 24
    panel_name: int = 30
    section_title: int = 20
    clue_card: int = 17
    clue_card_small: int = 15  # 4x4 and larger boards
    clue_card_min: int = 12  # long clues shrink to fit, never below this
    feedback_text: int = 15
    clue_list: int = 14
    card_name: int = 16
    button_text: int = 15
    mono_small: int = 11
    mono_label: int = 12
    mono_clock: int = 14
    # Mono text at or below this size uses the 500 weight (legibility).
    mono_medium_max: int = 12
    # Glyph coverage gamma: browsers thicken light-on-dark text this way.
    text_gamma: float = 1.3


@dataclass(frozen=True)
class Theme:
    colors: Colors = field(default_factory=Colors)
    fonts: Fonts = field(default_factory=Fonts)
    metrics: Metrics = field(default_factory=Metrics)


NIGHT = Theme()
DEFAULT_THEME = NIGHT
