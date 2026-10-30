"""MainWindow: a persistent Home button + a dynamic, per-tool nav row, above a card-like
content panel holding every page of the current tool's wizard, in order."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QFrame, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from .calm.pages.advanced_window import AdvancedWindow
from .calm.pages.lipid_species_page import LipidSpeciesPage
from .calm.pages.parameters_page import ParametersPage
from .calm.pages.results_page import ResultsPage
from .calm.pages.run_page import RunPage
from .calm.pages.run_selection_page import RunSelectionPage
from .calm.pages.structure_page import StructurePage
from .calm.pages.surface_page import SurfacePage
from .calm.pages.trajectory_page import TrajectoryPage
from .calm.state import WizardState
from .pages.home_page import HomePage
from .pages.working_dir_page import WorkingDirPage
from .theme import apply_drop_shadow
from .widgets.wizard_nav_bar import NavStep, WizardNavBar

# CALM's own step sequence for the second nav row - "Home" isn't part of it
# (it's the separate, persistent, tool-agnostic button above this row); a
# sibling tool would define its own equivalent list and swap it in via
# WizardNavBar.set_tool_steps the same way _on_tool_selected does below.
_CALM_STEPS = [
    NavStep("working_dir", "Working Directory"),
    NavStep("structure", "Structure"),
    NavStep("trajectory", "Trajectory"),
    NavStep("surface", "Surface"),
    NavStep("run_selection", "Run Selection"),
    NavStep("lipid_species", "Lipid Species", visible_by_default=False),
    NavStep("parameters", "Parameters"),
    NavStep("run", "Run"),
    NavStep("results", "Results"),
]
_CALM_STEP_ORDER = [step.key for step in _CALM_STEPS]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("COMMIC Overlay")
        self.resize(820, 640)

        self._advanced_window: AdvancedWindow | None = None
        self._furthest_key = "working_dir"
        self._entered_tool = False

        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(16, 8, 16, 16)
        outer_layout.setSpacing(12)

        self._nav_bar = WizardNavBar()
        self._nav_bar.home_clicked.connect(self._on_home_clicked)
        self._nav_bar.step_clicked.connect(self._go_to)
        outer_layout.addWidget(self._nav_bar)

        content_card = QFrame()
        content_card.setObjectName("contentCard")
        content_card.setStyleSheet("#contentCard { background-color: #ffffff; border-radius: 10px; }")
        apply_drop_shadow(content_card)
        card_layout = QVBoxLayout(content_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        card_layout.addWidget(self._stack)
        outer_layout.addWidget(content_card, stretch=1)

        self._pages: dict[str, QWidget] = {}
        self._home_page = HomePage()
        self._home_page.tool_selected.connect(self._on_tool_selected)
        self._add_page("home", self._home_page)

        self._build_calm_tool_pages()
        self._go_to_home()

    # ---- page construction ----

    def _add_page(self, key: str, widget: QWidget) -> None:
        self._pages[key] = widget
        self._stack.addWidget(widget)

    def _build_calm_tool_pages(self) -> None:
        """(Re)builds every CALM-specific page from a fresh WizardState.

        Used at startup, and again whenever the user restarts via Home
        after already entering the CALM flow - a full rebuild, not just
        resetting the shared WizardState, so no stale widget state (a
        previously picked file's path label, a ticked checkbox) survives
        a restart either.
        """
        for key in _CALM_STEP_ORDER:
            old = self._pages.pop(key, None)
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()

        self._state = WizardState()
        self._furthest_key = "working_dir"

        self._working_dir_page = WorkingDirPage()
        self._working_dir_page.continue_requested.connect(self._on_working_dir_continue)
        self._add_page("working_dir", self._working_dir_page)

        structure = StructurePage(self._state)
        structure.continue_requested.connect(lambda: self._continue_to("trajectory"))
        self._add_page("structure", structure)

        trajectory = TrajectoryPage(self._state)
        trajectory.continue_requested.connect(lambda: self._continue_to("surface"))
        self._add_page("trajectory", trajectory)

        surface = SurfacePage(self._state)
        surface.continue_requested.connect(lambda: self._continue_to("run_selection"))
        self._add_page("surface", surface)

        run_selection = RunSelectionPage(self._state)
        run_selection.continue_requested.connect(self._on_run_selection_continue)
        self._add_page("run_selection", run_selection)

        lipid_species = LipidSpeciesPage(self._state)
        lipid_species.continue_requested.connect(lambda: self._continue_to("parameters"))
        self._add_page("lipid_species", lipid_species)

        parameters = ParametersPage(self._state)
        parameters.run_requested.connect(self._on_parameters_run_requested)
        parameters.advanced_requested.connect(self._on_advanced_requested)
        self._add_page("parameters", parameters)

        run_page = RunPage()
        run_page.continue_requested.connect(lambda: self._continue_to("results"))
        self._add_page("run", run_page)

        results = ResultsPage(self._state)
        self._add_page("results", results)

    # ---- navigation ----

    def _go_to_home(self) -> None:
        self._nav_bar.clear_tool_steps()
        self._stack.setCurrentWidget(self._pages["home"])
        self._pages["home"].refresh()
        self._nav_bar.set_current_home()

    def _go_to(self, key: str) -> None:
        page = self._pages[key]
        page.refresh()
        self._stack.setCurrentWidget(page)
        self._nav_bar.unlock(key)
        self._nav_bar.set_current(key)
        if _CALM_STEP_ORDER.index(key) > _CALM_STEP_ORDER.index(self._furthest_key):
            self._furthest_key = key

    def _continue_to(self, next_key: str) -> None:
        """Advances to `next_key` - or, if the user had already gotten further than that
        before (revisiting an earlier step via the nav bar, changing something, and
        confirming it again), returns to the furthest point already reached instead.

        Without this, going back to fix e.g. the working directory and hitting Continue
        would reset progress all the way back to Structure even if Parameters (or
        Results) had already been reached - "go back and change something" shouldn't
        mean "redo every step after it".
        """
        target = next_key
        if _CALM_STEP_ORDER.index(self._furthest_key) > _CALM_STEP_ORDER.index(next_key):
            target = self._furthest_key
        self._go_to(target)

    def _on_tool_selected(self, tool: str) -> None:
        # Only "calm" exists for now; a sibling tool would branch on `tool`
        # here, setting a DIFFERENT step list via set_tool_steps.
        self._entered_tool = True
        self._nav_bar.set_tool_steps(_CALM_STEPS)
        self._go_to("working_dir")

    def _on_home_clicked(self) -> None:
        if self._entered_tool:
            answer = QMessageBox.question(
                self,
                "Return to Home?",
                "This restarts the process - any input you've entered might be lost.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        self._entered_tool = False
        self._build_calm_tool_pages()
        self._go_to_home()

    def _on_working_dir_continue(self) -> None:
        self._state.working_directory = self._working_dir_page.working_directory()
        self._continue_to("structure")

    def _on_run_selection_continue(self) -> None:
        natural_next = "parameters"
        if self._state.run_lipids:
            self._nav_bar.show_step("lipid_species")
            natural_next = "lipid_species"
        self._continue_to(natural_next)

    def _on_parameters_run_requested(self, commands: list) -> None:
        # Always actually navigates to and (re)starts the Run page -
        # deliberately _go_to, not _continue_to: revisiting Parameters
        # and clicking Continue again means "run it again" (parameters
        # may well have changed), never "take me back to where I already
        # was", the way every other page's Continue behaves.
        #
        # A fresh run_id (microsecond-resolution, so two runs started
        # back to back never collide) tags whatever the Results page
        # renders next as belonging to THIS run, and clearing
        # rendered_plots means nothing rendered by an earlier run is ever
        # mistaken for already-current (see state.py's own docstring).
        self._state.run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self._state.rendered_plots = {}
        self._go_to("run")
        self._pages["run"].start(commands)

    def _on_advanced_requested(self) -> None:
        self._advanced_window = AdvancedWindow(self._state, self)
        self._advanced_window.exec()
