"""Coordinate/region contract. Owner: Hồ Trần Quốc Thắng."""

from abc import ABC, abstractmethod

from griductive.models import Board, Cell, Region


class RegionResolver(ABC):
    @abstractmethod
    def resolve(self, region: Region, board: Board) -> tuple[Cell, ...]:
        """Return distinct cells in row-major order; ValueError for invalid input.

        Neighbors include diagonals but exclude self. Reject out-of-board
        references and duplicates in explicit lists. Empty explicit lists are
        valid; no wrapping across board boundaries.
        """
        raise NotImplementedError
