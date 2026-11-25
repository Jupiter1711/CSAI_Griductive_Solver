"""English wording for coordinates, clues and game outcomes. No pygame here.

Clues stay structured in the engine and agent; this module only renders them
for people, as the assignment allows ("the GUI may display natural-language
versions").
"""

from griductive.models import (
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Clue,
    ColumnRegion,
    CountClue,
    CountKind,
    ExplicitRegion,
    FactClue,
    NeighborRegion,
    Region,
    RowRegion,
    RunStatus,
    Status,
    SubmitResult,
    SubmitStatus,
)


def column_letter(col: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (spreadsheet style, as in the JSON format)."""
    label, number = "", col + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def cell_label(cell: Cell) -> str:
    """Cell(1, 2) -> "C2": column letter, then 1-based row."""
    return f"{column_letter(cell.col)}{cell.row + 1}"


def character_name(board: Board, cell: Cell) -> str:
    for character in board.characters:
        if character.cell == cell:
            return character.name
    return cell_label(cell)


def join_words(words: list[str]) -> str:
    if not words:
        return "nobody"
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def describe_region(region: Region, board: Board) -> str:
    """Prepositional phrase: "in row 2", "among Goku's neighbors", ..."""
    if isinstance(region, RowRegion):
        return f"in row {region.row + 1}"
    if isinstance(region, ColumnRegion):
        return f"in column {column_letter(region.col)}"
    if isinstance(region, NeighborRegion):
        return f"among {character_name(board, region.cell)}'s neighbors"
    if isinstance(region, ExplicitRegion):
        if not region.cells:
            return "in an empty group"
        return "among " + join_words([cell_label(cell) for cell in region.cells])
    return f"in {type(region).__name__}"


def describe_clue(clue: Clue, board: Board) -> str:
    """One English sentence for a structured clue."""
    if isinstance(clue, FactClue):
        name = character_name(board, clue.target)
        if clue.status is Status.CRIMINAL:
            return f"{name} is a criminal."
        return f"{name} is innocent."

    if isinstance(clue, BinaryClue):
        left = character_name(board, clue.left)
        right = character_name(board, clue.right)
        if clue.kind is BinaryKind.SAME:
            return f"{left} and {right} are both criminals or both innocent."
        return f"Exactly one of {left} and {right} is a criminal."

    if isinstance(clue, CountClue):
        where = describe_region(clue.region, board)
        noun = "criminal" if clue.k == 1 else "criminals"
        if clue.kind is CountKind.EXACTLY and clue.k == 0:
            return f"There are no criminals {where}."
        quantity = {
            CountKind.EXACTLY: "exactly",
            CountKind.AT_LEAST: "at least",
            CountKind.AT_MOST: "at most",
        }[clue.kind]
        verb = "is" if clue.k == 1 else "are"
        return f"There {verb} {quantity} {clue.k} {noun} {where}."

    # Extension clue types get a readable fallback until they add wording here.
    return f"{type(clue).__name__} clue {getattr(clue, 'id', '')}".strip()


def status_word(status: Status) -> str:
    return "a criminal" if status is Status.CRIMINAL else "innocent"


def opposite(status: Status) -> Status:
    return Status.INNOCENT if status is Status.CRIMINAL else Status.CRIMINAL


def submit_message(
    result: SubmitResult, board: Board, cell: Cell, status: Status
) -> str:
    """Explain a judge result in one line. Never mentions hidden information."""
    who = f"{character_name(board, cell)} ({cell_label(cell)})"
    kind = result.status
    if kind is SubmitStatus.ACCEPTED:
        return f"Proved! {who} is {status_word(status)}. A new clue is revealed."
    if kind is SubmitStatus.NOT_PROVABLE:
        return (
            f"{who} could be either right now. "
            "Find more evidence instead of guessing."
        )
    if kind is SubmitStatus.CONTRADICTED:
        return (
            f"The revealed clues prove {who} is {status_word(opposite(status))}, "
            f"not {status_word(status)}."
        )
    if kind is SubmitStatus.ALREADY_REVEALED:
        return f"{who} is already revealed."
    if kind is SubmitStatus.INCONSISTENT:
        return "The public clues contradict each other. Nothing can be judged."
    return f"Unexpected judge result: {kind}"


def run_status_message(status: RunStatus) -> str:
    return {
        RunStatus.RUNNING: "Deduction in progress.",
        RunStatus.SOLVED: "Every card is revealed. Puzzle solved!",
        RunStatus.STUCK: (
            "Stuck: no character is forced by the public clues, "
            "and the agent never guesses."
        ),
        RunStatus.INCONSISTENT: "The public clues are contradictory (KB is UNSAT).",
    }[status]
