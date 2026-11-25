"""Shared immutable records. Validation belongs to loaders and service boundaries."""

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"


@dataclass(frozen=True, order=True)
class Cell:
    """Zero-based (row, col); sorting gives row-major order."""

    row: int
    col: int


@dataclass(frozen=True)
class Character:
    cell: Cell
    name: str
    profession: str


@dataclass(frozen=True)
class Board:
    """Public metadata only; characters occur in row-major order."""

    size: int
    characters: tuple[Character, ...]


@dataclass(frozen=True)
class RowRegion:
    row: int


@dataclass(frozen=True)
class ColumnRegion:
    col: int


@dataclass(frozen=True)
class NeighborRegion:
    cell: Cell


@dataclass(frozen=True)
class ExplicitRegion:
    cells: tuple[Cell, ...]


Region: TypeAlias = RowRegion | ColumnRegion | NeighborRegion | ExplicitRegion


class BinaryKind(str, Enum):
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"


class CountKind(str, Enum):
    EXACTLY = "EXACTLY"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"


class ParityKind(str, Enum):
    EVEN = "EVEN"
    ODD = "ODD"


@dataclass(frozen=True)
class FactClue:
    id: str
    owner: Cell
    target: Cell
    status: Status


@dataclass(frozen=True)
class BinaryClue:
    id: str
    owner: Cell
    kind: BinaryKind
    left: Cell
    right: Cell


@dataclass(frozen=True)
class CountClue:
    id: str
    owner: Cell
    kind: CountKind
    k: int
    region: Region


@dataclass(frozen=True)
class ParityClue:
    id: str
    owner: Cell
    kind: ParityKind
    region: Region


@dataclass(frozen=True)
class IntersectionClue:
    id: str
    owner: Cell
    k: int
    regions: tuple[Region, ...]


Clue: TypeAlias = FactClue | BinaryClue | CountClue | ParityClue | IntersectionClue


@dataclass(frozen=True)
class Verdict:
    cell: Cell
    status: Status


@dataclass(frozen=True)
class Puzzle:
    """Private payload: never pass this record to inference or the GUI renderer."""

    id: str
    board: Board
    clues: tuple[Clue, ...]
    solution: tuple[Verdict, ...]
    initially_revealed: tuple[Cell, ...]


@dataclass(frozen=True)
class PublicState:
    board: Board
    verdicts: tuple[Verdict, ...]
    clues: tuple[Clue, ...]


Literal: TypeAlias = int
Clause: TypeAlias = tuple[Literal, ...]
CNF: TypeAlias = tuple[Clause, ...]
Assignment: TypeAlias = tuple[tuple[int, bool], ...]


@dataclass(frozen=True)
class VarMap:
    """primary[i] has SAT id i+1; auxiliaries follow all primary ids."""

    primary: tuple[Cell, ...]
    auxiliary_count: int = 0


@dataclass(frozen=True)
class EncodedKB:
    cnf: CNF
    variables: VarMap


class SATStatus(str, Enum):
    SAT = "SAT"
    UNSAT = "UNSAT"


@dataclass(frozen=True)
class SolverStats:
    decisions: int
    propagations: int
    backtracks: int
    runtime_s: float


@dataclass(frozen=True)
class SATResult:
    status: SATStatus
    model: Assignment | None
    stats: SolverStats


@dataclass(frozen=True)
class SATQuery:
    """The CNF is recorded once on the owning analysis/trace step."""

    assumptions: tuple[Literal, ...]
    result: SATResult


class Classification(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CellClassification:
    cell: Cell
    classification: Classification


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"


@dataclass(frozen=True)
class ClassificationResult:
    status: RunStatus
    kb: EncodedKB
    cells: tuple[CellClassification, ...]
    queries: tuple[SATQuery, ...]


class SubmitStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    ALREADY_REVEALED = "ALREADY_REVEALED"


@dataclass(frozen=True)
class SubmitResult:
    status: SubmitStatus
    state: PublicState
    revealed_clue: Clue | None
    kb: EncodedKB
    queries: tuple[SATQuery, ...]


class Uniqueness(str, Enum):
    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    UNSAT = "UNSAT"


@dataclass(frozen=True)
class ValidationResult:
    """Errors include malformed input or a supplied solution violating clues."""

    errors: tuple[str, ...]
    uniqueness: Uniqueness | None
