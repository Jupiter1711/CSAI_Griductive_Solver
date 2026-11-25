from dataclasses import dataclass, field
from pathlib import Path

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Color = RGB | RGBA

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _alpha(rgb: RGB, opacity: float) -> RGBA:
    return (*rgb, round(opacity * 255))


WHITE = (255, 255, 255)
ACCENT = (245, 165, 36)
INNOCENT = (92, 200, 160)
CRIMINAL = (240, 96, 93)
SPOTLIGHT = (110, 168, 255)


@dataclass(frozen=True)
class Colors:
    bg: RGB = (13, 14, 18)
    surface: RGB = (21, 23, 29)
    surface_2: RGB = (18, 20, 25)
    card: RGB = (22, 24, 31)
    hairline: RGBA = _alpha(WHITE, 0.08)
    line: RGBA = _alpha(WHITE, 0.14)

    ink: RGB = (236, 234, 228)
    ink_body: RGB = (218, 216, 209)
    ink_muted: RGB = (154, 154, 163)
    ink_faint: RGB = (138, 139, 148)

    accent: RGB = ACCENT
    on_accent: RGB = (26, 18, 5)
    accent_halo: RGBA = _alpha(ACCENT, 0.14)
    accent_glow: RGBA = _alpha(ACCENT, 0.45)

    innocent_text: RGB = (127, 216, 182)
    innocent_bg: RGB = (21, 34, 29)
    innocent_line: RGBA = _alpha(INNOCENT, 0.42)
    innocent_chip: RGBA = _alpha(INNOCENT, 0.12)
    innocent_feedback_bg: RGBA = _alpha(INNOCENT, 0.08)
    innocent_feedback_line: RGBA = _alpha(INNOCENT, 0.30)

    criminal_text: RGB = (244, 145, 142)
    criminal_bg: RGB = (36, 23, 26)
    criminal_line: RGBA = _alpha(CRIMINAL, 0.48)
    criminal_chip: RGBA = _alpha(CRIMINAL, 0.12)
    criminal_feedback_bg: RGBA = _alpha(CRIMINAL, 0.08)
    criminal_feedback_line: RGBA = _alpha(CRIMINAL, 0.30)

    spotlight: RGB = SPOTLIGHT
    spotlight_bg: RGBA = _alpha(SPOTLIGHT, 0.10)
    spotlight_line: RGBA = _alpha(SPOTLIGHT, 0.45)

    neutral_chip: RGBA = _alpha(WHITE, 0.07)
    hover: RGBA = _alpha(WHITE, 0.04)
    progress_track: RGBA = _alpha(WHITE, 0.07)
    avatar_ring: RGBA = _alpha(WHITE, 0.12)
    scrim: RGBA = (0, 0, 0, 160)
    # Discs behind initials when a character has no portrait file.
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
    display: Path = FONT_DIR / "BricolageGrotesque-Bold.ttf"
    body: Path = FONT_DIR / "Inter-Regular.ttf"
    body_medium: Path = FONT_DIR / "Inter-Medium.ttf"
    body_semibold: Path = FONT_DIR / "Inter-SemiBold.ttf"
    mono: Path = FONT_DIR / "JetBrainsMono-Regular.ttf"
    mono_medium: Path = FONT_DIR / "JetBrainsMono-Medium.ttf"
    fallback_sans: str = "segoeui,arial"
    fallback_mono: str = "consolas,couriernew"


@dataclass(frozen=True)
class Metrics:
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
    mono_medium_max: int = 12  # mono text up to this size uses the 500 weight
    text_gamma: float = 1.3  # glyph coverage gamma, thickens light-on-dark text


@dataclass(frozen=True)
class Theme:
    colors: Colors = field(default_factory=Colors)
    fonts: Fonts = field(default_factory=Fonts)
    metrics: Metrics = field(default_factory=Metrics)


DEFAULT_THEME = Theme()
