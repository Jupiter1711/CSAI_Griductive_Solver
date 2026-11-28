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
    IntersectionClue,
    NeighborRegion,
    ParityClue,
    ParityKind,
    Region,
    RowRegion,
    RunStatus,
    Status,
    SubmitResult,
    SubmitStatus,
)
from griductive.regions import column_label as column_letter
from griductive.regions import format_cell as cell_label

__all__ = [
    "cell_label",
    "character_name",
    "column_letter",
    "describe_clue",
    "describe_region",
    "run_status_message",
    "submit_message",
]

_QUANTITY = {
    CountKind.EXACTLY: "exactly",
    CountKind.AT_LEAST: "at least",
    CountKind.AT_MOST: "at most",
}


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


def _criminals(k: int) -> str:
    return "criminal" if k == 1 else "criminals"


def describe_clue(clue: Clue, board: Board) -> str:
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
        if clue.kind is CountKind.EXACTLY and clue.k == 0:
            return f"There are no criminals {where}."
        verb = "is" if clue.k == 1 else "are"
        quantity = _QUANTITY[clue.kind]
        return f"There {verb} {quantity} {clue.k} {_criminals(clue.k)} {where}."

    if isinstance(clue, ParityClue):
        where = describe_region(clue.region, board)
        parity = "even" if clue.kind is ParityKind.EVEN else "odd"
        return f"There is an {parity} number of criminals {where}."

    if isinstance(clue, IntersectionClue):
        # "who is both in X and in Y" reads as one person in every region
        # (intersection); "in X and in Y" alone is easily read as a union.
        where = join_words([describe_region(r, board) for r in clue.regions])
        if len(clue.regions) == 2:
            where = f"both {where}"
        if clue.k == 0:
            return f"No one who is {where} is a criminal."
        if clue.k == 1:
            return f"Exactly 1 person who is {where} is a criminal."
        return f"Exactly {clue.k} people who are {where} are criminals."

    return f"{type(clue).__name__} clue {getattr(clue, 'id', '')}".strip()


def status_word(status: Status) -> str:
    return "a criminal" if status is Status.CRIMINAL else "innocent"


def opposite(status: Status) -> Status:
    return Status.INNOCENT if status is Status.CRIMINAL else Status.CRIMINAL


def submit_message(
    result: SubmitResult, board: Board, cell: Cell, status: Status
) -> str:
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
