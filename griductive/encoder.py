"""CNF encoding contract. Owner: Nguyễn Huỳnh Hải Long."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from griductive.models import (
    CNF,
    BinaryClue,
    BinaryKind,
    Board,
    Cell,
    Clue,
    CountClue,
    CountKind,
    EncodedKB,
    FactClue,
    IntersectionClue,
    Literal,
    ParityClue,
    ParityKind,
    Region,
    Status,
    VarMap,
    Verdict,
)
from griductive.regions import GridRegionResolver


class CNFEncoder(ABC):
    @abstractmethod
    def encode(
        self, board: Board, clues: tuple[Clue, ...], verdicts: tuple[Verdict, ...]
    ) -> EncodedKB:
        """Encode exactly the supplied clues and verdicts; no puzzle access.

        Primary variable ids are row-major, starting at 1. Allocate auxiliary
        ids once across all clues, after N*N primary ids. Encode verdicts as
        unit clauses. Validate regions, references and 0 <= k <= region size;
        raise ValueError for malformed data. Logical contradiction is valid CNF,
        not a parse error. Counts come from VarMap and len(cnf).
        """
        raise NotImplementedError


class BasicCNFEncoder(CNFEncoder):
    def encode(
        self, board: Board, clues: tuple[Clue, ...], verdicts: tuple[Verdict, ...]
    ) -> EncodedKB:

        var_map = _create_var_map(board)
        auxiliary_count = 0

        def allocate_aux():
            nonlocal auxiliary_count
            auxiliary_count += 1
            return len(var_map.primary) + auxiliary_count

        clauses = []

        for clue in clues:
            if isinstance(clue, FactClue):
                encoded = _fact_encode(clue, var_map)

            elif isinstance(clue, BinaryClue):
                encoded = _binary_encode(clue, var_map)

            elif isinstance(clue, CountClue):
                encoded = _count_encode(
                    clue,
                    board,
                    var_map,
                    allocate_aux,
                )

            elif isinstance(clue, ParityClue):
                encoded = _parity_encode(clue, board, var_map, allocate_aux)

            elif isinstance(clue, IntersectionClue):
                encoded = _intersection_encode(
                    clue,
                    board,
                    var_map,
                    allocate_aux,
                )

            else:
                raise ValueError(f"Unsupported clue type: {type(clue)}")

            clauses.extend(encoded)

        for verdict in verdicts:
            literal = _get_literal(
                verdict.cell,
                verdict.status,
                var_map,
            )

            clauses.append((literal,))

        final_var_map = VarMap(
            primary=var_map.primary,
            auxiliary_count=auxiliary_count,
        )

        return EncodedKB(
            cnf=tuple(clauses),
            variables=final_var_map,
        )


def _get_var_id(cell: Cell, var_map: VarMap) -> int:
    return var_map.primary.index(cell) + 1


def _get_literal(cell: Cell, status: Status, var_map: VarMap) -> Literal:
    var_id = _get_var_id(cell, var_map)
    if status == Status.CRIMINAL:
        return var_id
    else:
        return -var_id


def _create_var_map(board: Board) -> VarMap:
    primary = tuple(sorted(character.cell for character in board.characters))
    return VarMap(primary)


def _fact_encode(clue: FactClue, var_map: VarMap) -> CNF:
    literal = _get_literal(clue.target, clue.status, var_map)
    return ((literal,),)


def _binary_encode(clue: BinaryClue, var_map: VarMap) -> CNF:
    left_literal = _get_literal(clue.left, Status.CRIMINAL, var_map)
    right_literal = _get_literal(clue.right, Status.CRIMINAL, var_map)

    if clue.kind == BinaryKind.SAME:
        return ((-left_literal, right_literal), (left_literal, -right_literal))
    elif clue.kind == BinaryKind.DIFFERENT:
        return ((left_literal, right_literal), (-left_literal, -right_literal))
    else:
        raise ValueError(f"Unsupported binary kind: {clue.kind}")


def _get_region_cell(region: Region, board: Board) -> tuple[Cell, ...]:
    resolver = GridRegionResolver()
    return resolver.resolve(region, board)


def at_most_encode(
    literals: tuple[Literal, ...], k: int, allocate_aux: Callable[[], int]
) -> CNF:

    if k < 0:
        raise ValueError("Number of Criminals must be a non-negative number.")

    n = len(literals)

    # Không có điều kiện nào cần ràng buộc
    if k >= n:
        return ()

    # AT_MOST 0: tất cả literal đều phải False
    if k == 0:
        return tuple((-literal,) for literal in literals)

    clauses = []
    s = {}

    # Cấp auxiliary variables cho các trạng thái đếm
    for i in range(1, n):
        for j in range(1, min(i, k) + 1):
            s[(i, j)] = allocate_aux()

    # Encode các trạng thái đếm
    for i in range(1, n):
        x = literals[i - 1]

        for j in range(1, min(i, k) + 1):
            z = s[(i, j)]

            # Base case: s[1, 1] <-> x1
            if i == 1 and j == 1:
                clauses.append((-z, x))
                clauses.append((z, -x))

            # s[i, 1] <-> s[i-1, 1] OR xi
            elif j == 1:
                prev = s[(i - 1, 1)]

                clauses.append((-z, prev, x))
                clauses.append((z, -prev))
                clauses.append((z, -x))

            # s[i, j] <-> s[i-1, j] OR (xi AND s[i-1, j-1])
            else:
                prev_lower = s[(i - 1, j - 1)]

                # s[i-1, j] chưa tồn tại nếu j == i
                if j == i:
                    clauses.append((-z, x))
                    clauses.append((-z, prev_lower))
                    clauses.append((z, -x, -prev_lower))

                else:
                    prev_same = s[(i - 1, j)]

                    clauses.append((-z, prev_same, x))
                    clauses.append((-z, prev_same, prev_lower))
                    clauses.append((z, -prev_same))
                    clauses.append((z, -x, -prev_lower))

    # Cấm vượt quá k Criminal
    for i in range(k + 1, n + 1):
        x = literals[i - 1]
        previous_count = s[(i - 1, k)]

        clauses.append((-x, -previous_count))

    return tuple(clauses)


def _encode_count_literals(
    literals: tuple[Literal, ...],
    kind: CountKind,
    k: int,
    allocate_aux: Callable[[], int],
) -> CNF:

    n = len(literals)

    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and the region size.")

    if kind == CountKind.AT_MOST:
        return at_most_encode(
            literals,
            k,
            allocate_aux,
        )

    elif kind == CountKind.AT_LEAST:
        return at_most_encode(
            tuple(-literal for literal in literals),
            n - k,
            allocate_aux,
        )

    elif kind == CountKind.EXACTLY:
        at_most_k = at_most_encode(
            literals,
            k,
            allocate_aux,
        )

        at_least_k = at_most_encode(
            tuple(-literal for literal in literals),
            n - k,
            allocate_aux,
        )

        return at_most_k + at_least_k

    raise ValueError(f"Unsupported count kind: {kind}")


def _count_encode(
    clue: CountClue,
    board: Board,
    var_map: VarMap,
    allocate_aux: Callable[[], int],
) -> CNF:

    cells = _get_region_cell(clue.region, board)

    literals = tuple(_get_literal(cell, Status.CRIMINAL, var_map) for cell in cells)

    return _encode_count_literals(
        literals,
        clue.kind,
        clue.k,
        allocate_aux,
    )


def _get_intersection_cells(
    regions: tuple[Region, ...],
    board: Board,
) -> tuple[Cell, ...]:

    if not regions:
        raise ValueError("Intersection requires at least one region.")

    cells = set(_get_region_cell(regions[0], board))

    for region in regions[1:]:
        region_cells = set(_get_region_cell(region, board))
        cells.intersection_update(region_cells)

    return tuple(sorted(cells))


def _intersection_encode(
    clue: IntersectionClue,
    board: Board,
    var_map: VarMap,
    allocate_aux: Callable[[], int],
) -> CNF:

    regions, k = clue.regions, clue.k
    cells = _get_intersection_cells(regions, board)

    literals = tuple(_get_literal(cell, Status.CRIMINAL, var_map) for cell in cells)

    return _encode_count_literals(
        literals,
        CountKind.EXACTLY,
        k,
        allocate_aux,
    )


def _xor_encode(
    left: Literal,
    right: Literal,
    result: Literal,
) -> CNF:
    return (
        (-left, -right, -result),
        (left, right, -result),
        (left, -right, result),
        (-left, right, result),
    )


def _parity_encode(
    clue: ParityClue, board: Board, var_map: VarMap, allocate_aux: Callable[[], int]
) -> CNF:

    if clue.kind not in (ParityKind.EVEN, ParityKind.ODD):
        raise ValueError(f"Unsupported parity kind: {clue.kind}")

    cells = _get_region_cell(clue.region, board)

    literals = tuple(_get_literal(cell, Status.CRIMINAL, var_map) for cell in cells)

    clauses = []

    if not literals:
        if clue.kind == ParityKind.EVEN:
            return ()
        else:
            return ((),)

    if len(literals) == 1:
        literal = literals[0]

        if clue.kind == ParityKind.ODD:
            return ((literal,),)

        return ((-literal,),)

    # XOR chain for all literals except the last one
    current = literals[0]

    for literal in literals[1:-1]:
        auxiliary = allocate_aux()

        clauses.extend(_xor_encode(current, literal, auxiliary))

        current = auxiliary

    last = literals[-1]

    if clue.kind == ParityKind.EVEN:
        clauses.extend(
            (
                (-current, last),
                (current, -last),
            )
        )
    else:
        clauses.extend(
            (
                (current, last),
                (-current, -last),
            )
        )

    return tuple(clauses)
