from dataclasses import dataclass

from griductive.models import (
    BinaryClue,
    Board,
    Cell,
    Clue,
    CountClue,
    FactClue,
    IntersectionClue,
    NeighborRegion,
    ParityClue,
    Region,
)
from griductive.regions import RegionResolver


@dataclass(frozen=True)
class ClueFocus:
    counted: tuple[Cell, ...]
    anchors: tuple[Cell, ...] = ()

    @property
    def cells(self) -> frozenset[Cell]:
        return frozenset(self.counted) | frozenset(self.anchors)


def _anchors(regions: tuple[Region, ...]) -> tuple[Cell, ...]:
    return tuple(sorted({r.cell for r in regions if isinstance(r, NeighborRegion)}))


def clue_focus(clue: Clue, board: Board, regions: RegionResolver) -> ClueFocus:
    if isinstance(clue, FactClue):
        return ClueFocus((clue.target,))
    if isinstance(clue, BinaryClue):
        return ClueFocus(tuple(sorted({clue.left, clue.right})))
    if isinstance(clue, (CountClue, ParityClue)):
        counted = regions.resolve(clue.region, board)
        return ClueFocus(tuple(counted), _anchors((clue.region,)))
    if isinstance(clue, IntersectionClue):
        if not clue.regions:
            return ClueFocus(())
        shared = set(regions.resolve(clue.regions[0], board))
        for region in clue.regions[1:]:
            shared &= set(regions.resolve(region, board))
        return ClueFocus(tuple(sorted(shared)), _anchors(clue.regions))
    return ClueFocus(())


def related_clue(
    cell: Cell, clues: tuple[Clue, ...], board: Board, regions: RegionResolver
) -> Clue | None:
    for clue in clues:
        try:
            if cell in clue_focus(clue, board, regions).cells:
                return clue
        except ValueError:
            continue
    return None
