"""SortLipidsPage: per-domain lipid composition for every domain that has points.

Which domains have points, and their share of each leaflet, comes from replaying Distribute
Domains and Place Domains on the preview point directory (`domain_preview_math.py`); with a
single domain, Domain 0 holds every point. A table is shown for each such domain. Rows are
kept for every domain up to `state.domain_count`, since `input.str` lists them all and PCG
only warns about a listed domain without points.

Row set per domain starts as every lipid `state.selected_lipids` holds (evenly split so each
domain's upper/lower ratios already sum to 1 on first visit), with the area per lipid from
`apl_estimate.py`; "Delete row" removes a lipid from one domain's table only, and each
table's "Add lipid" drop-down offers the selected lipids that table lacks. On Continue,
any shown domain whose ratios don't sum to 1 gets a normalize confirmation (Ok scales that
domain's values to sum to 1 and proceeds; Cancel leaves the page untouched) - matching
`input.str`'s `RatioUp`/`RatioDown` columns (`PCG`'s worked example has `POPC 0.5 0.5 0.63` /
`POPE 0.5 0.5 0.64`, summing to 1 each column).
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.float_spinbox import FloatSpinBox
from ..state import DomainLipid, WizardState
from ..ts2cg_bridge.apl_estimate import FALLBACK_APL, REFERENCE_TEMPERATURE, estimate_apl
from ..ts2cg_bridge.domain_preview_math import compute_preview_domains, domain_point_shares
from .domain_op_dialog import color_icon, domain_color
from .preview_progress import ensure_preview

_RATIO_SUM_TOLERANCE = 1e-3
_COLUMNS = ["Lipid", "Upper ratio", "Lower ratio", "APL (nm²)", ""]
_DESCRIPTION = (
    "One table per domain that has points after Distribute Domains and Place Domains. Upper "
    "and lower ratios are each lipid's share of that domain on the outer and inner leaflet. "
    "APL is the area per lipid PCG uses to decide how many lipids fit on the membrane. Its "
    "default is the Martini 3 lipidome benchmark's simulated value, shifted to "
    f"{REFERENCE_TEMPERATURE:.0f} K, where the benchmark has the lipid, and otherwise an "
    "estimate from the lipid's tails in its ITP."
)

# Domain id -> (outer-leaflet share, inner-leaflet share or None), or None for "every point".
DomainShares = dict[int, tuple[float, float | None] | None]


class SortLipidsPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._tables: dict[int, QTableWidget] = {}
        self._shown_domains: list[int] = []
        self._shares: DomainShares = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Sort lipids")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        description = QLabel(_DESCRIPTION)
        description.setWordWrap(True)
        description.setStyleSheet("color: #555;")
        layout.addWidget(description)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #777;")
        layout.addWidget(self._status_label)

        tables_widget = QWidget()
        self._tables_container = QVBoxLayout(tables_widget)
        self._tables_container.setContentsMargins(0, 0, 0, 0)
        self._tables_container.setSpacing(20)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidget(tables_widget)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self._scroll_area, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.clicked.connect(self._on_continue_clicked)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        """Syncs every domain's rows from `state.selected_lipids` (adds a row for a newly
        selected lipid, drops a row for one no longer selected), then rebuilds one table per
        domain with points - call each time this page is shown."""
        for domain_index in range(self._state.domain_count):
            self._sync_domain_rows(domain_index)
        self._shares, notes = self._domain_shares()
        self._shown_domains = sorted(d for d in self._shares if d < self._state.domain_count)
        empty = [d for d in range(self._state.domain_count) if d not in self._shares]
        if empty:
            names = ", ".join(f"Domain {d}" for d in empty)
            notes.append(f"{names}: no points after Distribute Domains and Place Domains, so no lipids needed.")
        self._status_label.setText(" ".join(notes))
        self._status_label.setVisible(bool(notes))
        self._rebuild_tables()

    def _rebuild_tables(self) -> None:
        """Rebuilds the shown domains' tables from `state.domain_lipids`, keeping the scroll position."""
        scroll_bar = self._scroll_area.verticalScrollBar()
        position = scroll_bar.value()
        self._clear_layout(self._tables_container)
        self._tables = {}
        for domain_index in self._shown_domains:
            rows = self._state.domain_lipids.get(domain_index, [])
            self._tables_container.addWidget(self._build_domain_table(domain_index, rows, self._shares[domain_index]))
        self._tables_container.addStretch(1)
        # After the layout has resized the scroll range for the new tables.
        QTimer.singleShot(0, scroll_bar, partial(scroll_bar.setValue, position))

    def _domain_shares(self) -> tuple[DomainShares, list[str]]:
        """(shares, notes): the domains with points and their leaflet shares, plus notes to show."""
        if self._state.domain_count <= 1:
            return {0: None}, []
        try:
            removed = ensure_preview(self, self._state)
            domains = compute_preview_domains(self._state.preview_point_dir, self._state, self._state.domain_ops)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not a programming error
            note = f"Could not determine which domains have points ({exc}), so every domain is shown."
            return dict.fromkeys(range(self._state.domain_count)), [note]
        notes = []
        if removed > 0:
            notes.append(f"{removed} Place Domains operation(s) were removed because the settings they used changed.")
        return dict(domain_point_shares(domains)), notes

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    @staticmethod
    def _fit_table_to_contents(table: QTableWidget) -> None:
        """Sizes `table` to exactly its columns and rows, with no scroll bars of its own."""
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frame = 2 * table.frameWidth()
        width = sum(table.columnWidth(c) for c in range(table.columnCount())) + frame
        height = (
            table.horizontalHeader().sizeHint().height()
            + sum(table.rowHeight(r) for r in range(table.rowCount()))
            + frame
        )
        table.setFixedSize(width, height)

    def _default_apl(self, name: str) -> float:
        itp_path = self._state.lipid_to_itp.get(name)
        if itp_path is None:
            return FALLBACK_APL
        return estimate_apl(Path(itp_path), name)

    def _sync_domain_rows(self, domain_index: int) -> list[DomainLipid]:
        rows = self._state.domain_lipids.setdefault(domain_index, [])
        known = self._state.domain_known_lipids.setdefault(domain_index, set())
        was_empty = len(rows) == 0
        existing_names = {r.name for r in rows}
        selected = self._state.selected_lipids

        # Only a lipid this domain has genuinely never seen before gets auto-added -
        # one already `known` but missing from `rows` was deliberately deleted via
        # its "Delete row" button, and stays deleted through this same sync.
        for name in selected:
            if name not in existing_names and name not in known:
                apl = self._default_apl(name)
                rows.append(DomainLipid(name=name, ratio_up=0.0, ratio_down=0.0, area_per_lipid=apl))
                known.add(name)

        selected_set = set(selected)
        rows[:] = [r for r in rows if r.name in selected_set]
        # A lipid dropped from the overall selection entirely is forgotten too, so a
        # later re-selection is treated as genuinely new (auto-added again), not as
        # still "known" from before.
        known.intersection_update(selected_set)

        # A brand-new domain (first time it has any rows at all) starts evenly split,
        # so its own ratios already sum to 1 without the user doing anything - matches
        # "one can continue without changing anything" for the common case.
        if was_empty and rows:
            even_share = 1.0 / len(rows)
            for row in rows:
                row.ratio_up = even_share
                row.ratio_down = even_share

        return rows

    def _domain_header(self, domain_index: int, share: tuple[float, float | None] | None) -> QWidget:
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        swatch = QLabel()
        swatch.setPixmap(color_icon(domain_color(self._state, domain_index)).pixmap(12, 12))
        header_layout.addWidget(swatch)
        label = QLabel(f"Domain {domain_index}")
        label.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(label)
        if share is None:
            extent = "every point" if self._state.domain_count <= 1 else ""
        else:
            outer, inner = share
            extent = f"{outer:.0%} of the outer leaflet"
            if inner is not None:
                extent += f", {inner:.0%} of the inner leaflet"
        if extent:
            extent_label = QLabel(extent)
            extent_label.setStyleSheet("color: #777;")
            header_layout.addWidget(extent_label)
        header_layout.addStretch(1)
        return header

    def _build_domain_table(
        self, domain_index: int, rows: list[DomainLipid], share: tuple[float, float | None] | None
    ) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        container_layout.addWidget(self._domain_header(domain_index, share))

        table = QTableWidget(len(rows), len(_COLUMNS))
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.verticalHeader().setVisible(False)
        for row_index, lipid in enumerate(rows):
            name_item = QTableWidgetItem(lipid.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_index, 0, name_item)

            up_box = FloatSpinBox(minimum=0.0, maximum=1.0, value=lipid.ratio_up, step=0.05, decimals=3)
            up_box.valueChanged.connect(lambda value, row=lipid: setattr(row, "ratio_up", value))
            table.setCellWidget(row_index, 1, up_box)

            down_box = FloatSpinBox(minimum=0.0, maximum=1.0, value=lipid.ratio_down, step=0.05, decimals=3)
            down_box.valueChanged.connect(lambda value, row=lipid: setattr(row, "ratio_down", value))
            table.setCellWidget(row_index, 2, down_box)

            apl_box = FloatSpinBox(minimum=0.05, maximum=10.0, value=lipid.area_per_lipid, step=0.01, decimals=3)
            apl_box.valueChanged.connect(lambda value, row=lipid: setattr(row, "area_per_lipid", value))
            table.setCellWidget(row_index, 3, apl_box)

            delete_button = QPushButton("Delete row")
            delete_button.clicked.connect(lambda _checked, d=domain_index, n=lipid.name: self._on_delete_row(d, n))
            table.setCellWidget(row_index, 4, delete_button)

        self._fit_table_to_contents(table)
        container_layout.addWidget(table, alignment=Qt.AlignmentFlag.AlignLeft)
        container_layout.addLayout(self._add_lipid_row(domain_index, rows))
        self._tables[domain_index] = table
        return container

    def _add_lipid_row(self, domain_index: int, rows: list[DomainLipid]) -> QHBoxLayout:
        """A drop-down of the selected lipids missing from this domain, and its "Add lipid" button."""
        present = {row.name for row in rows}
        missing = [name for name in self._state.selected_lipids if name not in present]
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 4, 0, 0)
        lipid_box = QComboBox()
        lipid_box.setMinimumContentsLength(14)
        lipid_box.addItems(missing)
        add_button = QPushButton("Add lipid")
        add_button.clicked.connect(
            lambda _checked, d=domain_index, box=lipid_box: self._on_add_lipid(d, box.currentText())
        )
        if not missing:
            lipid_box.setPlaceholderText("All selected lipids are here")
            lipid_box.setEnabled(False)
            add_button.setEnabled(False)
        add_row.addWidget(lipid_box)
        add_row.addWidget(add_button)
        add_row.addStretch(1)
        return add_row

    def _on_add_lipid(self, domain_index: int, name: str) -> None:
        """Appends `name` to the domain with ratios of 0, which keeps the domain's sums, or of
        1 when it is the domain's only lipid."""
        rows = self._state.domain_lipids.setdefault(domain_index, [])
        ratio = 0.0 if rows else 1.0
        rows.append(DomainLipid(name=name, ratio_up=ratio, ratio_down=ratio, area_per_lipid=self._default_apl(name)))
        self._rebuild_tables()

    def _on_delete_row(self, domain_index: int, name: str) -> None:
        rows = self._state.domain_lipids.get(domain_index, [])
        self._state.domain_lipids[domain_index] = [r for r in rows if r.name != name]
        self._rebuild_tables()

    def _on_continue_clicked(self) -> None:
        empty_domains = [d for d in self._shown_domains if not self._state.domain_lipids.get(d)]
        if empty_domains:
            names = ", ".join(f"Domain {d}" for d in empty_domains)
            QMessageBox.warning(
                self, "Empty domain", f"{names} has no lipids left - add at least one lipid before continuing."
            )
            return

        needs_normalizing = [d for d in self._shown_domains if not self._domain_sums_to_one(d)]
        if needs_normalizing:
            names = ", ".join(f"Domain {d}" for d in needs_normalizing)
            answer = QMessageBox.warning(
                self,
                "Ratios don't sum to 1",
                f"{names}: upper and/or lower ratios don't sum to 1. They will now be "
                "normalized to 1.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
            for domain_index in needs_normalizing:
                self._normalize_domain(domain_index)
            self._rebuild_tables()

        self.continue_requested.emit()

    def _domain_sums_to_one(self, domain_index: int) -> bool:
        rows = self._state.domain_lipids.get(domain_index, [])
        up_sum = sum(r.ratio_up for r in rows)
        down_sum = sum(r.ratio_down for r in rows)
        return abs(up_sum - 1.0) < _RATIO_SUM_TOLERANCE and abs(down_sum - 1.0) < _RATIO_SUM_TOLERANCE

    def _normalize_domain(self, domain_index: int) -> None:
        rows = self._state.domain_lipids.get(domain_index, [])
        up_sum = sum(r.ratio_up for r in rows)
        down_sum = sum(r.ratio_down for r in rows)
        if up_sum > 0:
            for row in rows:
                row.ratio_up = row.ratio_up / up_sum
        if down_sum > 0:
            for row in rows:
                row.ratio_down = row.ratio_down / down_sum
