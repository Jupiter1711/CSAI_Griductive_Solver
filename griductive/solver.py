"""DPLL contract. Owner: Hồ Trần Quốc Thắng."""

from abc import ABC, abstractmethod

from griductive.models import CNF, Literal, SATResult, VarMap


class SATSolver(ABC):
    @abstractmethod
    def solve(
        self, cnf: CNF, variables: VarMap, assumptions: tuple[Literal, ...] = ()
    ) -> SATResult:
        """Solve without mutating CNF or retaining assumptions across calls.

        Validate nonzero literals and declared variable ids (ValueError).
        SAT returns all declared variables, including unconstrained variables;
        UNSAT returns model=None. Empty CNF is SAT; an empty clause is UNSAT.
        Implement propagation, conflict detection, deterministic branching and
        backtracking. Stats describe this call only. Never use hidden puzzle data.
        """
        raise NotImplementedError
