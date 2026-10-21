"""Reusable PySide6 screens for StudentDB academic modules."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QDateEdit, QDialogButtonBox
)
from PySide6.QtCore import QDate
from . import academic_repository as repo
from psycopg import errors
from .report_pages import ReportPage


def show_error(parent, error):
    if isinstance(error, errors.CheckViolation):
        constraint = getattr(error.diag, "constraint_name", None)
        message = (
            "A value does not match the database rules.\n\n"
            f"Failed constraint: {constraint or 'Unknown'}\n\n"
            f"Details: {error}"
        )

    elif isinstance(error, errors.ForeignKeyViolation):
        message = (
            "This record is referenced by another record, "
            "or the selected related record does not exist.\n\n"
            f"Details: {error}"
        )

    elif isinstance(error, errors.UniqueViolation):
        message = "This ID or another unique value already exists."

    elif isinstance(error, ValueError):
        message = str(error)

    else:
        message = str(error)

    QMessageBox.critical(parent, "StudentDB — Database Error", message)


def make_table():
    table = QTableWidget()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setStretchLastSection(True)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(False)
    table.setWordWrap(False)
    return table


def populate(table, records, fields=None):
    fields = fields or (list(records[0]) if records else [])
    table.setColumnCount(len(fields))
    table.setHorizontalHeaderLabels([f.replace('_', ' ').title() for f in fields])
    table.setRowCount(len(records))
    for i, row in enumerate(records):
        for j, field in enumerate(fields):
            table.setItem(i, j, QTableWidgetItem(str(row.get(field) if row.get(field) is not None else '')))
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    return fields


class RecordDialog(QDialog):
    def __init__(self, name, fields, schema, record=None, parent=None):
        super().__init__(parent)
        self.name = name  # Identifies the module, such as Teachers
        self.setWindowTitle(('Edit ' if record else 'Add ') + name)
        self.setMinimumWidth(500)
        self.widgets = {}
        self.schema = schema
        self.record = record or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        if name == 'Teachers':
            teacher_id = QLineEdit(str(self.record.get('teacher_id') or ''))
            teacher_id.setPlaceholderText('Enter Teacher ID')
            teacher_id.setReadOnly(record is not None)
            teacher_id.setToolTip('For UUID database columns, enter a valid UUID. Text columns can accept IDs like TCH-001.')
            form.addRow('Teacher ID:', teacher_id)
            self.widgets['teacher_id'] = teacher_id
        for field in fields:
            value = self.record.get(field)
            if field in repo.FOREIGN_KEYS:
                widget = QComboBox()
                widget.addItem('— Select —', None)
                for key, label in repo.choices(field):
                    widget.addItem(f'{label} ({key})', key)
                if value is not None:
                    index = widget.findData(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
            else:
                widget = QLineEdit('' if value is None else str(value))
                if field in ('units', 'max_score', 'percentage'):
                    widget.setPlaceholderText('Enter a number')
                elif field.endswith('_date') or field in ('start_date', 'end_date'):
                    widget.setPlaceholderText('YYYY-MM-DD')
            form.addRow(field.replace('_', ' ').title() + ':', widget)
            self.widgets[field] = widget
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('saveButton')
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_and_accept(self):
        if self.name == 'Teachers' and not self.widgets['teacher_id'].text().strip():
            QMessageBox.warning(self, 'Teacher ID required', 'Please enter a Teacher ID.')
            return
        self.accept()

    def values(self):
        return {field: (widget.currentData() if isinstance(widget, QComboBox) else widget.text().strip())
                for field, widget in self.widgets.items()}


class EntityPage(QWidget):
    def __init__(self, name, status_callback=None):
        super().__init__()
        self.name = name
        self.status_callback = status_callback or (lambda text: None)
        self.records = []
        self.pk = repo.ENTITIES[name][1]
        layout = QVBoxLayout(self)
        heading = QLabel(name.upper())
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        actions = QHBoxLayout()
        for text, handler, style in [
            ('↻ Refresh', self.refresh, ''), ('+ Add', self.add_record, 'primaryButton'),
            ('✎ Edit Selected', self.edit_record, 'editButton'), ('✕ Delete Selected', self.delete_record, 'dangerButton')
        ]:
            button = QPushButton(text)
            if style:
                button.setObjectName(style)
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.table = make_table()
        layout.addWidget(self.table)
        self.info = QLabel('Ready')
        layout.addWidget(self.info)

    def selected(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.records):
            QMessageBox.information(self, 'Select a record', 'Select a row first.')
            return None
        return self.records[index]

    def refresh(self, *_):
        try:
            table, pk, fields, schema = repo.entity_fields(self.name)
            self.records = repo.rows(self.name)
            if self.name == 'Teachers':
                display_fields = [
                    'teacher_id',
                    'first_name',
                    'last_name',
                    'email',
                    'department',
                    'subject_description',
                    'subject_id'
                ]
            else:
                display_fields = [pk] + fields

            populate(self.table, self.records, display_fields)
            self.table.setProperty('id_fields', display_fields)
            self.info.setText(f'{len(self.records)} record(s)')
            self.status_callback(f'{self.name}: {len(self.records)} records loaded')
        except Exception as exc:
            self.info.setText('Could not load records')
            show_error(self, exc)

    def open_dialog(self, record=None):
        try:
            _, _, fields, schema = repo.entity_fields(self.name)
            dialog = RecordDialog(self.name, fields, schema, record, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                repo.save_entity(self.name, dialog.values(), record[self.pk] if record else None)
                self.refresh()
        except Exception as exc:
            show_error(self, exc)

    def add_record(self, *_):
        self.open_dialog()

    def edit_record(self, *_):
        record = self.selected()
        if record:
            self.open_dialog(record)

    def delete_record(self, *_):
        record = self.selected()
        if not record:
            return
        answer = QMessageBox.question(self, 'Confirm deletion',
            f'Delete {self.name} record {record[self.pk]}?\nReferenced records may prevent deletion.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            try:
                repo.delete_entity(self.name, record[self.pk])
                self.refresh()
            except Exception as exc:
                show_error(self, exc)


class ScoreDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Encode Student Score')
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.widgets = {}
        schema = repo.score_schema()
        for field in ('enrollment_id', 'component_id', 'period_id', 'score', 'remarks'):
            if field not in schema:
                continue
            if field in ('enrollment_id', 'component_id', 'period_id'):
                widget = QComboBox()
                widget.addItem('— Select —', None)
                options = repo.enrollment_choices() if field == 'enrollment_id' else repo.choices(field)
                for key, label in options:
                    widget.addItem(f'{label} ({key})', key)
            else:
                widget = QLineEdit()
                if field == 'score':
                    widget.setPlaceholderText('0.00')
            self.widgets[field] = widget
            form.addRow(field.replace('_', ' ').title(), widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('saveButton')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {field: (widget.currentData() if isinstance(widget, QComboBox) else widget.text().strip())
                for field, widget in self.widgets.items()}


class ScoresPage(QWidget):
    def __init__(self, status_callback=None):
        super().__init__()
        self.status_callback = status_callback or (lambda text: None)
        layout = QVBoxLayout(self)
        heading = QLabel('SCORE ENCODING')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        bar = QHBoxLayout()
        for text, action in [('↻ Refresh', self.refresh), ('+ Encode Score', self.add_score),
                             ('✓ Calculate Period Grade', self.calculate)]:
            button = QPushButton(text)
            button.clicked.connect(action)
            if 'Encode' in text: button.setObjectName('primaryButton')
            if 'Calculate' in text: button.setObjectName('saveButton')
            bar.addWidget(button)
        layout.addLayout(bar)
        self.table = make_table()
        layout.addWidget(self.table)
        self.info = QLabel('Ready')
        layout.addWidget(self.info)

    def refresh(self, *_):
        try:
            records = repo.score_rows()
            fields = list(repo.score_schema())
            populate(self.table, records, fields)
            self.table.setProperty('id_fields', fields)
            self.info.setText(f'{len(records)} encoded scores')
        except Exception as exc:
            show_error(self, exc)

    def add_score(self, *_):
        try:
            dialog = ScoreDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                repo.save_score(dialog.values())
                self.refresh()
        except Exception as exc:
            show_error(self, exc)

    def calculate(self, *_):
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle('Calculate Final Period Grade')
            layout = QVBoxLayout(dialog)
            form = QFormLayout()
            enrollment = QComboBox()
            period = QComboBox()
            for key, label in repo.enrollment_choices():
                enrollment.addItem(label, key)
            for key, label in repo.choices('period_id'):
                period.addItem(label, key)
            form.addRow('Enrollment', enrollment)
            form.addRow('Grading Period', period)
            layout.addLayout(form)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                if enrollment.currentData() is None or period.currentData() is None:
                    raise ValueError('Choose an enrollment and grading period')
                grade = repo.calculate_period_grade(enrollment.currentData(), period.currentData())
                QMessageBox.information(self, 'Grade saved', f'Calculated period grade: {grade}')
                self.refresh()
        except Exception as exc:
            show_error(self, exc)


class GradesPage(QWidget):
    def __init__(self, overall=False):
        super().__init__()
        self.overall = overall
        layout = QVBoxLayout(self)
        title = QLabel('OVERALL GRADES' if overall else 'GRADES & TRANSCRIPTS')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        note = QLabel('Overall percentage = Midterm × 40% + Finals × 60%. Missing periods remain pending.' if overall
                      else 'Saved final period grades from PostgreSQL.')
        layout.addWidget(note)
        button = QPushButton('↻ Refresh')
        button.clicked.connect(self.refresh)
        layout.addWidget(button)
        self.table = make_table()
        layout.addWidget(self.table)
        self.info = QLabel('Ready')
        layout.addWidget(self.info)

    def refresh(self, *_):
        try:
            records = repo.overall_rows() if self.overall else repo.grade_rows()
            fields = (['student_id', 'first_name', 'last_name', 'class_code', 'midterm_percentage', 'finals_percentage', 'overall_percentage', 'final_equiv', 'remarks']
                      if self.overall else ['student_id', 'first_name', 'last_name', 'class_code', 'period_name', 'final_grade', 'remarks', 'date_encoded'])
            populate(self.table, records, fields)
            self.table.setProperty('id_fields', fields)
            self.info.setText(f'{len(records)} record(s)')
        except Exception as exc:
            show_error(self, exc)
