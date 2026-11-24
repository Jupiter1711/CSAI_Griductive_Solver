"""P1/P2 contract. Owner: Nguyễn Lê Khánh Toàn."""

from abc import ABC, abstractmethod

from griductive.encoder import CNFEncoder
from griductive.solver import SATSolver
from griductive.models import (
    CellClassification,
    Classification,
    ClassificationResult,
    EncodedKB,
    PublicState,
    RunStatus,
    SATQuery,
    SATStatus,
)


class LogicAgent(ABC):
    @abstractmethod
    def build_kb(self, state: PublicState) -> EncodedKB:
        """Use CNFEncoder on exactly state.clues and state.verdicts.

        No access to Puzzle, GameEngine, hidden solution or unrevealed clues.
        Malformed public input raises ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def classify(self, state: PublicState) -> ClassificationResult:
        """Build KB; check SAT before testing both signs of each unresolved cell.

        Return INCONSISTENT with no classifications if KB is UNSAT. Otherwise
        return every unresolved cell in row-major order, with UNKNOWN if both
        assumptions are SAT. Status is SOLVED if no cells remain, STUCK if all
        are unknown, otherwise RUNNING. Include every SAT query and its stats.
        This read-only operation also supplies hints without revealing a card.
        """
        raise NotImplementedError


class GriductiveLogicAgent(LogicAgent):
    def __init__(self, encoder: CNFEncoder, solver: SATSolver):
        self.encoder = encoder
        self.solver = solver

    def build_kb(self, state: PublicState) -> EncodedKB:
        try:
            return self.encoder.encode(board=state.board, clues=state.clues, verdicts=state.verdicts)
        except ValueError as e:
            raise ValueError(f"Dữ liệu công khai không hợp lệ: {e}") from e

    def classify(self, state: PublicState) -> ClassificationResult:
        kb = self.build_kb(state)
        queries = []

        base_result = self.solver.solve(kb.cnf, kb.variables, assumptions=())
        queries.append(SATQuery(assumptions=(), result=base_result))

        if base_result.status == SATStatus.UNSAT:
            return ClassificationResult(
                status=RunStatus.INCONSISTENT,
                kb=kb,
                cells=(),
                queries=tuple(queries)
            )

        revealed_cells = {v.cell for v in state.verdicts}
        unresolved = []
        for cell in kb.variables.primary:
            if cell not in revealed_cells:
                unresolved.append(cell)

        if not unresolved:
            return ClassificationResult(
                status=RunStatus.SOLVED,
                kb=kb,
                cells=(),
                queries=tuple(queries)
            )

        classifications = []
        has_forced_cell = False

        for cell in unresolved:
            var_id = kb.variables.primary.index(cell) + 1

            assume_crim = (var_id,)
            res_crim = self.solver.solve(kb.cnf, kb.variables, assumptions=assume_crim)
            queries.append(SATQuery(assumptions=assume_crim, result=res_crim))

            assume_inn = (-var_id,)
            res_inn = self.solver.solve(kb.cnf, kb.variables, assumptions=assume_inn)
            queries.append(SATQuery(assumptions=assume_inn, result=res_inn))

            is_crim_sat = res_crim.status == SATStatus.SAT
            is_inn_sat = res_inn.status == SATStatus.SAT

            if is_crim_sat and not is_inn_sat:
                c_class = Classification.CRIMINAL
                has_forced_cell = True
            elif not is_crim_sat and is_inn_sat:
                c_class = Classification.INNOCENT
                has_forced_cell = True
            else:
                c_class = Classification.UNKNOWN

            classifications.append(CellClassification(cell=cell, classification=c_class))

        final_status = RunStatus.RUNNING if has_forced_cell else RunStatus.STUCK

        return ClassificationResult(
            status=final_status,
            kb=kb,
            cells=tuple(classifications),
            queries=tuple(queries)
        )
