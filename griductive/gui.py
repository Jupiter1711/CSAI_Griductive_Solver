"""Pygame GUI contract. Owner: Hồ Trần Quốc Thắng."""

from abc import ABC, abstractmethod

from griductive.agent.inference import LogicAgent
from griductive.agent.runner import DeductionRunner
from griductive.engine import GameEngine
from griductive.puzzle_io import PuzzleLoader
from griductive.regions import RegionResolver


class GameUI(ABC):
    @abstractmethod
    def run(
        self,
        engine: GameEngine,
        agent: LogicAgent,
        runner: DeductionRunner,
        loader: PuzzleLoader,
        regions: RegionResolver,
    ) -> None:
        """Run GUI events; render PublicState only, with no hidden clue previews.

        Provide Load/Restart/Hint/Auto Solve, verdict submission, coordinates,
        names/professions, public statuses/clues and clue highlighting. Hint
        uses classify without submission; auto solve uses runner.step. Keep the
        event loop responsive even during a slow step (step alone cannot ensure
        this). Show rejected/terminal outcomes distinctly.
        Importing this module must not import pygame or open a window.
        """
        raise NotImplementedError
