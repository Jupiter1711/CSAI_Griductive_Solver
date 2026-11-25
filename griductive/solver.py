"""DPLL contract. Owner: Hồ Trần Quốc Thắng."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from griductive.models import (
    CNF,
    Literal,
    SATResult,
    SATStatus,
    SolverStats,
    VarMap,
)


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


class DPLLSolver(SATSolver):
    """Iterative DPLL: two-watched-literal unit propagation, chronological
    backtracking, no clause learning and no pure-literal elimination.

    Branching is deterministic: the lowest unassigned variable id that occurs
    in a clause, trying False (Innocent) before True (Criminal). Variables that
    occur in no clause are reported as False without branching on them.

    Stats follow docs/architecture.md:
    - decisions: every value chosen for a trial branch, flipped branches included;
    - propagations: variables newly assigned by unit propagation (unit clauses
      included); assumptions are not counted;
    - backtracks: every failed branch that is abandoned and undone.

    The agent queries one KB many times with different assumptions, so the
    validated, preprocessed form of the last CNF is reused when the very same
    immutable tuple object is passed again. Search state, assumptions and stats
    are always fresh per call.
    """

    def __init__(self) -> None:
        self._cached: tuple[CNF, _Prepared] | None = None

    def solve(
        self, cnf: CNF, variables: VarMap, assumptions: tuple[Literal, ...] = ()
    ) -> SATResult:
        start = time.perf_counter()
        num_vars = _declared_count(variables)
        prepared = self._prepare(cnf, num_vars)
        assumed = _checked_literals(assumptions, num_vars, "assumption")

        search = _Search(num_vars)
        satisfiable = search.run(prepared, assumed)


        stats = SolverStats(
            decisions=search.decisions,
            propagations=search.propagations,
            backtracks=search.backtracks,
            runtime_s=time.perf_counter() - start,
        )
        if not satisfiable:
            return SATResult(SATStatus.UNSAT, None, stats)
        return SATResult(SATStatus.SAT, search.model(), stats)

    def _prepare(self, cnf: CNF, num_vars: int) -> "_Prepared":
        cached = self._cached
        if cached is not None and cached[0] is cnf and cached[1].num_vars == num_vars:
            return cached[1]
        prepared = _prepare(cnf, num_vars)
        if type(cnf) is tuple and all(type(clause) is tuple for clause in cnf):
            self._cached = (cnf, prepared)
        return prepared


@dataclass(frozen=True)
class _Prepared:
    """Validated CNF: duplicate literals removed, tautologies dropped."""
    num_vars: int
    has_empty_clause: bool
    units: tuple[int, ...]
    clauses: tuple[tuple[int, ...], ...] 
    order: tuple[int, ...]  #ascending id


def _prepare(cnf: CNF, num_vars: int) -> _Prepared:
    if not isinstance(cnf, (tuple, list)):
        raise ValueError(f"CNF must be a tuple of clauses, got {cnf!r}")
    units: list[int] = []
    clauses: list[tuple[int, ...]] = []
    occurring: set[int] = set()
    has_empty = False
    for clause in cnf:
        literals = _checked_literals(clause, num_vars, "clause")
        unique = tuple(dict.fromkeys(literals))
        present = set(unique)
        if any(-lit in present for lit in unique):
            continue
        if not unique:
            has_empty = True
        elif len(unique) == 1:
            units.append(unique[0])
        else:
            clauses.append(unique)
            occurring.update(abs(lit) for lit in unique)
    return _Prepared(
        num_vars, has_empty, tuple(units), tuple(clauses), tuple(sorted(occurring))
    )


class _Search:
    """State of one solve call; never shared between calls."""

    def __init__(self, num_vars: int):
        self.num_vars = num_vars
        self.value = [0] * (num_vars + 1)  # 0 unassigned, 1 True, -1 False
        self.trail: list[int] = []  # literals made true -> order
        self.head = 0  # next trail position to propagate
        self.clauses: list[list[int]] = []
        self.watches: list[list[int]] = [[] for _ in range(2 * num_vars + 1)]
        self.order: tuple[int, ...] = ()  # branchable variables, ascending id
        self.next_pick = 0
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0

    def run(self, prepared: _Prepared, assumptions: list[int]) -> bool:
        if prepared.has_empty_clause:
            return False
        offset = self.num_vars
        self.clauses = [list(clause) for clause in prepared.clauses]
        for index, clause in enumerate(self.clauses):
            self.watches[clause[0] + offset].append(index)
            self.watches[clause[1] + offset].append(index)
        self.order = prepared.order

        for lit in assumptions:
            if not self._assign(lit):
                return False
        for lit in prepared.units:
            if not self._assign(lit, propagated=True):
                return False
        return self._search()

    def _search(self) -> bool:
        branches: list[tuple[int, int, bool]] = []
        while True:
            if self._propagate():
                var = self._pick()
                if var is None:
                    return True
                branches.append((len(self.trail), -var, False))
                self.decisions += 1
                self._assign(-var)
                continue

            while True:
                if not branches:
                    return False
                trail_pos, lit, flipped = branches.pop()
                self.backtracks += 1
                self._undo(trail_pos)
                if not flipped:
                    branches.append((trail_pos, -lit, True))
                    self.decisions += 1
                    self._assign(-lit)
                    break

    def _lit_value(self, lit: int) -> int:
        value = self.value[abs(lit)]
        return value if lit > 0 else -value

    def _assign(self, lit: int, propagated: bool = False) -> bool:
        """Make lit true; False if it is already false (conflict)."""
        current = self._lit_value(lit)
        if current:
            return current == 1
        self.value[abs(lit)] = 1 if lit > 0 else -1
        self.trail.append(lit)
        if propagated:
            self.propagations += 1
        return True

    def _propagate(self) -> bool:
        """Unit-propagate every pending trail literal; False on conflict."""
        offset = self.num_vars
        value, trail, clauses, watches = (
            self.value,
            self.trail,
            self.clauses,
            self.watches,
        )
        while self.head < len(trail):
            false_lit = -trail[self.head]
            self.head += 1
            watching = watches[false_lit + offset]
            kept = 0
            i = 0
            while i < len(watching):
                index = watching[i]
                i += 1
                clause = clauses[index]
                if clause[0] == false_lit:
                    clause[0], clause[1] = clause[1], clause[0]
                other = clause[0]
                other_value = value[other] if other > 0 else -value[-other]
                if other_value == 1:
                    watching[kept] = index
                    kept += 1
                    continue
                for k in range(2, len(clause)):
                    lit = clause[k]
                    if (value[lit] if lit > 0 else -value[-lit]) != -1:
                        clause[1], clause[k] = lit, clause[1]
                        watches[lit + offset].append(index)
                        break
                else:
                    watching[kept] = index
                    kept += 1
                    if not self._assign(other, propagated=True):
                        watching[kept:] = watching[i:]
                        return False
            del watching[kept:]
        return True

    def _undo(self, trail_pos: int) -> None:
        for lit in self.trail[trail_pos:]:
            self.value[abs(lit)] = 0
        del self.trail[trail_pos:]
        self.head = trail_pos
        self.next_pick = 0

    def _pick(self) -> int | None:
        while self.next_pick < len(self.order):
            var = self.order[self.next_pick]
            if not self.value[var]:
                return var
            self.next_pick += 1
        return None

    def model(self) -> tuple[tuple[int, bool], ...]:
        return tuple((var, self.value[var] == 1) for var in range(1, self.num_vars + 1))


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _declared_count(variables: VarMap) -> int:
    if not isinstance(variables, VarMap):
        raise ValueError(f"variables must be a VarMap, got {type(variables).__name__}")
    if not isinstance(variables.primary, tuple):
        raise ValueError("VarMap.primary must be a tuple")
    aux = variables.auxiliary_count
    if not _is_int(aux) or aux < 0:
        raise ValueError(f"auxiliary_count must be a non-negative integer, got {aux!r}")
    return len(variables.primary) + aux


def _checked_literals(literals: object, num_vars: int, what: str) -> list[int]:
    if not isinstance(literals, (tuple, list)):
        raise ValueError(f"{what}s must be a tuple of literals, got {literals!r}")
    for lit in literals:
        if not _is_int(lit) or lit == 0:
            raise ValueError(f"{what} literal must be a nonzero integer, got {lit!r}")
        if abs(lit) > num_vars:
            raise ValueError(
                f"{what} literal {lit} uses an undeclared variable (1..{num_vars})"
            )
    return list(literals)
