"""Unified, non-destructive grading configuration for class offerings."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QFrame
)
from . import academic_repository as repo
from .academic_pages import show_error
from .retro_tables import install_retro_table_style


class GradingConfigurationPage(QWidget):
    def __init__(self, status_callback=None):
        super().__init__()
        self.status_callback = status_callback or (lambda *_: None)
        self.component_rows = []
        root = QVBoxLayout(self)
        title = QLabel('GRADING CONFIGURATION')
        title.setObjectName('sectionTitle')
        root.addWidget(title)
        top = QHBoxLayout()
        top.addWidget(QLabel('SUBJECT / CLASS OFFERING'))
        self.offering = QComboBox()
        self.offering.setMinimumWidth(320)
        self.offering.currentIndexChanged.connect(self.load_details)
        top.addWidget(self.offering, 1)
        root.addLayout(top)
        self.inputs = {}
        for period in ('Midterm', 'Finals'):
            panel = QFrame()
            panel.setObjectName('panel')
            grid = QGridLayout(panel)
            heading = QLabel(period.upper())
            heading.setObjectName('subtitle')
            grid.addWidget(heading, 0, 0, 1, 3)
            for col, heading in enumerate(('COMPONENT', 'MAX SCORE', 'WEIGHT (%)')):
                grid.addWidget(QLabel(heading), 1, col)
            for i, (kind, label) in enumerate((('quiz', 'Quiz'), ('project', 'Laboratory / Project'), ('exam', 'Exam')), 2):
                grid.addWidget(QLabel(label), i, 0)
                maximum = QLineEdit()
                maximum.setPlaceholderText('e.g. 50')
                weight = QLineEdit()
                weight.setPlaceholderText('e.g. 30')
                grid.addWidget(maximum, i, 1)
                grid.addWidget(weight, i, 2)
                self.inputs[(period, kind)] = (maximum, weight)
            root.addWidget(panel)
        content = QHBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Period', 'Component', 'Max Score', 'Scores', 'Component ID'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        install_retro_table_style(self.table)
        content.addWidget(self.table, 1)
        actions = QVBoxLayout()
        for text, handler, style in (
            ('↻ Refresh', self.refresh, ''),
            ('✓ Save Configuration', self.save, 'primaryButton'),
            ('✕ Delete Unscored Component', self.delete_component, 'dangerButton'),
        ):
            button = QPushButton(text)
            if style:
                button.setObjectName(style)
            button.clicked.connect(handler)
            button.setMinimumHeight(43)
            actions.addWidget(button)
        actions.addStretch()
        side = QWidget()
        side.setFixedWidth(220)
        side.setLayout(actions)
        content.addWidget(side)
        root.addLayout(content, 1)
        self.info = QLabel('Choose an offering to view its configuration.')
        root.addWidget(self.info)

    def refresh(self, *_):
        previous = self.offering.currentData()
        try:
            offerings = repo.configuration_offerings()
            self.offering.blockSignals(True)
            self.offering.clear()
            self.offering.addItem('— Select a subject / offering —', None)
            for item in offerings:
                self.offering.addItem(
                    f"{item['subject_code']} — {item['class_code']} "
                    f"({item['school_year']} / {item['semester']})",
                    str(item['offering_id']))
            index = self.offering.findData(str(previous)) if previous is not None else 0
            self.offering.setCurrentIndex(max(0, index))
            self.offering.blockSignals(False)
            self.load_details()
        except Exception as exc:
            self.offering.blockSignals(False)
            show_error(self, exc)

    def load_details(self, *_):
        offering_id = self.offering.currentData()
        self.component_rows = []
        self.table.setRowCount(0)
        for fields in self.inputs.values():
            for field in fields:
                field.clear()
        if not offering_id:
            return
        try:
            periods, components, weights = repo.configuration_details(offering_id)
            period_by_id = {}
            for period in periods:
                label = str(period['name']).strip().lower()
                if label in ('midterm', 'final', 'finals'):
                    period_by_id[str(period['period_id'])] = 'Midterm' if label == 'midterm' else 'Finals'
            for component in components:
                period = period_by_id.get(str(component['grading_period_id']))
                kind = repo.normalize_component_type(component['type'])
                if period and (period, kind) in self.inputs:
                    self.inputs[(period, kind)][0].setText(str(component['max_score']))
                self.component_rows.append((component, period or 'Other'))
            for weight in weights:
                label = str(weight['component_type']).strip().lower()
                period = 'Midterm' if label.startswith('midterm ') else ('Finals' if label.startswith(('final ', 'finals ')) else None)
                kind = repo.normalize_component_type(label)
                if period and (period, kind) in self.inputs:
                    self.inputs[(period, kind)][1].setText(str(weight['percentage']))
            self.table.setRowCount(len(self.component_rows))
            for row, (component, period) in enumerate(self.component_rows):
                for col, value in enumerate((period, component['name'], component['max_score'],
                                              component['score_count'], component['component_id'])):
                    self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.info.setText(f'{len(self.component_rows)} component(s) | Existing scores are protected')
        except Exception as exc:
            show_error(self, exc)

    def save(self, *_):
        offering_id = self.offering.currentData()
        if not offering_id:
            QMessageBox.warning(self, 'Required', 'Choose a subject / class offering.')
            return
        values = {}
        for period in ('Midterm', 'Finals'):
            values[period] = {}
            for kind in ('quiz', 'project', 'exam'):
                maximum, weight = self.inputs[(period, kind)]
                values[period][kind] = (maximum.text(), weight.text())
        try:
            repo.save_configuration(offering_id, values)
            self.load_details()
            self.status_callback('Grading configuration saved')
            QMessageBox.information(self, 'Saved', 'Midterm and Finals configuration saved.')
        except Exception as exc:
            # Remain on the page with inputs intact for correction.
            show_error(self, exc)

    def delete_component(self, *_):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.component_rows):
            QMessageBox.information(self, 'Select component', 'Select a component to delete.')
            return
        component = self.component_rows[index][0]
        answer = QMessageBox.question(self, 'Confirm deletion',
            'Delete this component only if it has no student scores?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            repo.delete_configuration_component(component['component_id'])
            self.load_details()
        except Exception as exc:
            show_error(self, exc)
