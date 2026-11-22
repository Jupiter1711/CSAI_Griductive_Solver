"""CNF encoding contract. Owner: Nguyễn Huỳnh Hải Long."""

from abc import ABC, abstractmethod

from griductive.models import Board, Clue, EncodedKB, Verdict


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
