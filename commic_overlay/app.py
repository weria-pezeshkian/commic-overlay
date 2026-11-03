"""MainWindow: a persistent Home button + a dynamic, per-tool nav row, above a card-like
content panel holding every page of the current tool's wizard, in order."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
from .calm.state import WizardState as CalmWizardState
from .pages.home_page import HomePage
from .pages.working_dir_page import WorkingDirPage
from .theme import apply_drop_shadow
from .ts2cg.pages.add_protein_page import AddProteinPage
from .ts2cg.pages.analytical_shape_page import AnalyticalShapePage
from .ts2cg.pages.distribute_domains_page import DistributeDomainsPage
from .ts2cg.pages.domain_count_page import DomainCountPage
from .ts2cg.pages.mesh_file_page import MeshFilePage
from .ts2cg.pages.path_choice_page import PathChoicePage
from .ts2cg.pages.place_domains_page import PlaceDomainsPage
from .ts2cg.pages.results_page import ResultsPage as Ts2cgResultsPage
from .ts2cg.pages.run_page import RunPage as Ts2cgRunPage
from .ts2cg.pages.select_lipids_page import SelectLipidsPage
from .ts2cg.pages.sort_lipids_page import SortLipidsPage
from .ts2cg.pages.summary_page import SummaryPage
from .ts2cg.state import WizardState as Ts2cgWizardState
from .ts2cg.ts2cg_bridge.pipeline import build_pipeline
from .widgets.wizard_nav_bar import NavStep, WizardNavBar

# Each tool's own step sequence for the second nav row - "Home" isn't part of
# either (it's the separate, persistent, tool-agnostic button above this
# row). A step with visible_by_default=False is a conditional branch,
# revealed only once that branch is actually taken (see each tool's own
# _on_..._requested handler below).
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

_TS2CG_STEPS = [
    NavStep("working_dir", "Working Directory"),
    NavStep("path_choice", "Choose Path"),
    NavStep("analytical_shape", "Shape", visible_by_default=False),
    NavStep("mesh_file", "Mesh File", visible_by_default=False),
    NavStep("select_lipids", "Select Lipids"),
    NavStep("domain_count", "Domains"),
    NavStep("add_protein", "Add Proteins"),
    NavStep("distribute_domains", "Distribute Domains"),
    NavStep("place_domains", "Place Domains", visible_by_default=False),
    NavStep("sort_lipids", "Sort Lipids"),
    NavStep("summary", "Summary"),
    NavStep("run", "Run"),
    NavStep("results", "Results"),
]
_TS2CG_STEP_ORDER = [step.key for step in _TS2CG_STEPS]


class MainWindow(QMainWindow):
    def __init__(self, launch_directory: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("COMMIC Overlay")
        self.resize(820, 640)

        self._advanced_window: AdvancedWindow | None = None
        self._active_tool = ""  # "" | "calm" | "ts2cg"
        self._step_order: list[str] = []
        self._furthest_key = ""
        self._entered_tool = False
        # Offered on the Working Directory page until a working directory is confirmed.
        self._launch_directory = launch_directory

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

        self._go_to_home()

    # ---- page construction ----

    def _add_page(self, key: str, widget: QWidget) -> None:
        self._pages[key] = widget
        self._stack.addWidget(widget)

    def _teardown_tool_pages(self, step_order: list[str]) -> None:
        for key in step_order:
            old = self._pages.pop(key, None)
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()

    def _build_calm_tool_pages(self) -> None:
        """(Re)builds every CALM-specific page from a fresh WizardState.

        Used whenever CALM is (re-)entered from Home - a full rebuild, not
        just resetting the shared WizardState, so no stale widget state (a
        previously picked file's path label, a ticked checkbox) survives a
        restart either.
        """
        self._teardown_tool_pages(_CALM_STEP_ORDER)

        self._state = CalmWizardState()
        self._step_order = _CALM_STEP_ORDER
        self._furthest_key = "working_dir"

        working_dir_page = WorkingDirPage(self._launch_directory)
        working_dir_page.continue_requested.connect(self._on_calm_working_dir_continue)
        self._add_page("working_dir", working_dir_page)

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

    def _build_ts2cg_tool_pages(self) -> None:
        """(Re)builds every TS2CG-specific page from a fresh WizardState - same full-rebuild
        discipline as `_build_calm_tool_pages`."""
        self._teardown_tool_pages(_TS2CG_STEP_ORDER)

        self._state = Ts2cgWizardState()
        self._step_order = _TS2CG_STEP_ORDER
        self._furthest_key = "working_dir"

        working_dir_page = WorkingDirPage(self._launch_directory)
        working_dir_page.continue_requested.connect(self._on_ts2cg_working_dir_continue)
        self._add_page("working_dir", working_dir_page)

        path_choice = PathChoicePage(self._state)
        path_choice.path_chosen.connect(self._on_ts2cg_path_chosen)
        self._add_page("path_choice", path_choice)

        analytical_shape = AnalyticalShapePage(self._state)
        analytical_shape.continue_requested.connect(lambda: self._continue_to("select_lipids"))
        self._add_page("analytical_shape", analytical_shape)

        mesh_file = MeshFilePage(self._state)
        mesh_file.continue_requested.connect(lambda: self._continue_to("select_lipids"))
        self._add_page("mesh_file", mesh_file)

        select_lipids = SelectLipidsPage(self._state)
        select_lipids.continue_requested.connect(lambda: self._continue_to("domain_count"))
        self._add_page("select_lipids", select_lipids)

        domain_count = DomainCountPage(self._state)
        # _go_to from here through Sort Lipids: a changed domain count or new proteins change
        # the place_domains gate in _on_ts2cg_distribute_domains_continue and which domains
        # Sort Lipids shows.
        domain_count.continue_requested.connect(lambda: self._go_to("add_protein"))
        self._add_page("domain_count", domain_count)

        add_protein = AddProteinPage(self._state)
        add_protein.continue_requested.connect(lambda: self._go_to("distribute_domains"))
        self._add_page("add_protein", add_protein)

        distribute_domains = DistributeDomainsPage(self._state)
        distribute_domains.continue_requested.connect(self._on_ts2cg_distribute_domains_continue)
        self._add_page("distribute_domains", distribute_domains)

        place_domains = PlaceDomainsPage(self._state)
        place_domains.continue_requested.connect(lambda: self._go_to("sort_lipids"))
        self._add_page("place_domains", place_domains)

        sort_lipids = SortLipidsPage(self._state)
        sort_lipids.continue_requested.connect(lambda: self._continue_to("summary"))
        self._add_page("sort_lipids", sort_lipids)

        summary = SummaryPage(self._state)
        summary.run_requested.connect(self._on_ts2cg_run_requested)
        self._add_page("summary", summary)

        run_page = Ts2cgRunPage()
        run_page.continue_requested.connect(lambda: self._continue_to("results"))
        self._add_page("run", run_page)

        results = Ts2cgResultsPage(self._state)
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
        if self._step_order.index(key) > self._step_order.index(self._furthest_key):
            self._furthest_key = key

    def _continue_to(self, next_key: str) -> None:
        """Advances to `next_key` - or, if the user had already gotten further than that
        before (revisiting an earlier step via the nav bar, changing something, and
        confirming it again), returns to the furthest point already reached instead.

        Without this, going back to fix e.g. the working directory and hitting Continue
        would reset progress all the way back to the second step even if a much later
        one had already been reached - "go back and change something" shouldn't mean
        "redo every step after it".
        """
        target = next_key
        if self._step_order.index(self._furthest_key) > self._step_order.index(next_key):
            target = self._furthest_key
        self._go_to(target)

    def _on_tool_selected(self, tool: str) -> None:
        self._entered_tool = True
        self._active_tool = tool
        if tool == "calm":
            self._build_calm_tool_pages()
            self._nav_bar.set_tool_steps(_CALM_STEPS)
        elif tool == "ts2cg":
            self._build_ts2cg_tool_pages()
            self._nav_bar.set_tool_steps(_TS2CG_STEPS)
        else:
            raise ValueError(f"Unknown tool: {tool!r}")
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
        if self._active_tool == "calm":
            self._teardown_tool_pages(_CALM_STEP_ORDER)
        elif self._active_tool == "ts2cg":
            self._teardown_tool_pages(_TS2CG_STEP_ORDER)
        self._active_tool = ""
        self._go_to_home()

    # ---- CALM ----

    def _on_calm_working_dir_continue(self) -> None:
        self._state.working_directory = self._pages["working_dir"].working_directory()
        self._launch_directory = None
        self._continue_to("structure")

    def _on_run_selection_continue(self) -> None:
        # Deliberately _go_to, not _continue_to: which step is actually next here
        # depends on the lipids toggle's CURRENT value, which can change on a
        # return visit - the furthest-key shortcut would otherwise skip straight
        # past lipid_species to wherever was furthest reached before, even if
        # lipids was only just turned on this time (same reasoning as
        # _on_parameters_run_requested's own _go_to, and
        # _on_ts2cg_distribute_domains_continue's below).
        natural_next = "parameters"
        if self._state.run_lipids:
            self._nav_bar.show_step("lipid_species")
            natural_next = "lipid_species"
        self._go_to(natural_next)

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
        # mistaken for already-current (see calm/state.py's own docstring).
        self._state.run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self._state.rendered_plots = {}
        self._go_to("run")
        self._pages["run"].start(commands)

    def _on_advanced_requested(self) -> None:
        self._advanced_window = AdvancedWindow(self._state, self)
        self._advanced_window.exec()

    # ---- TS2CG ----

    def _on_ts2cg_working_dir_continue(self) -> None:
        self._state.working_directory = self._pages["working_dir"].working_directory()
        self._launch_directory = None
        self._continue_to("path_choice")

    def _on_ts2cg_path_chosen(self, key: str) -> None:
        # Deliberately _go_to, not _continue_to - same reasoning as
        # _on_run_selection_continue's own note: a return visit could switch
        # from one path branch to the other, so the furthest-key shortcut
        # can't safely apply here either.
        other = "mesh_file" if key == "analytical_shape" else "analytical_shape"
        self._nav_bar.show_step(key)
        self._nav_bar.hide_step(other)
        self._go_to(key)

    def _on_ts2cg_distribute_domains_continue(self) -> None:
        # Deliberately _go_to, not _continue_to - same reasoning as
        # _on_run_selection_continue's own note: whether place_domains is next
        # depends on domain_count's CURRENT value, which can change on a return
        # visit, so the furthest-key shortcut can't safely apply here.
        next_key = "place_domains" if self._state.domain_count > 1 else "sort_lipids"
        if self._state.domain_count > 1:
            self._nav_bar.show_step("place_domains")
        else:
            self._nav_bar.hide_step("place_domains")
        self._go_to(next_key)

    def _on_ts2cg_run_requested(self) -> None:
        # Same "always a genuinely fresh run" semantics as CALM's own
        # _on_parameters_run_requested - see its own comment for why
        # run_id is stamped fresh here, right before Run starts.
        self._state.run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        steps = build_pipeline(self._state)
        self._go_to("run")
        self._pages["run"].start(steps)
