"""Cells a revealed clue talks about, for highlighting. No pygame here."""

from dataclasses import dataclass

from griductive.models import (
    BinaryClue,
    Board,
    Cell,
    Clue,
    CountClue,
    FactClue,
    NeighborRegion,
)
from griductive.regions import RegionResolver


@dataclass(frozen=True)
class ClueFocus:
    """counted: cells the clue constrains; anchors: cells it only names.

    For "2 criminals among Goku's neighbors", the neighbors are counted and
    Goku is an anchor (named, but not counted). Both are row-major.
    """

    counted: tuple[Cell, ...]
    anchors: tuple[Cell, ...] = ()

    @property
    def cells(self) -> frozenset[Cell]:
        return frozenset(self.counted) | frozenset(self.anchors)


def clue_focus(clue: Clue, board: Board, regions: RegionResolver) -> ClueFocus:
    """Resolve the cells referenced by a clue; ValueError for a bad region."""
    if isinstance(clue, FactClue):
        return ClueFocus((clue.target,))
    if isinstance(clue, BinaryClue):
        return ClueFocus(tuple(sorted({clue.left, clue.right})))
    if isinstance(clue, CountClue):
        counted = regions.resolve(clue.region, board)
        anchors: tuple[Cell, ...] = ()
        if isinstance(clue.region, NeighborRegion):
            anchors = (clue.region.cell,)
        return ClueFocus(tuple(counted), anchors)
    # Extension clues highlight nothing until they declare their cells.
    return ClueFocus(())


def related_clue(
    cell: Cell, clues: tuple[Clue, ...], board: Board, regions: RegionResolver
) -> Clue | None:
    """First revealed clue (in the given order) that mentions ``cell``.

    Used by Hint to point at relevant public evidence. It only looks at
    revealed clues, so it never leaks hidden information.
    """
    for clue in clues:
        try:
            if cell in clue_focus(clue, board, regions).cells:
                return clue
        except ValueError:
            continue
    return None
