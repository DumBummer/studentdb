"""Reusable PySide6 screens for StudentDB academic modules."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QMessageBox, QDateEdit, QDialogButtonBox, QTabWidget
)
from PySide6.QtCore import QDate, Qt
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
        if name == 'Grading Periods':
            self.subject_selector = QComboBox()
            self.subject_selector.addItem('— Select subject —', None)
            for sid, label in repo.choices('subject_id'):
                self.subject_selector.addItem(label, sid)
            form.addRow('Subject:', self.subject_selector)
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
        if self.name == 'Grading Periods' and not self.subject_selector.currentData():
            QMessageBox.warning(self, 'Subject required', 'Select a subject first.')
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
        self.search_input = None
        self.filtered_records = []
        if self.name == 'Teachers':
            search_row = QHBoxLayout()
            search_row.addWidget(QLabel('SEARCH TEACHERS'))
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText('Search name, teacher ID, department, or assigned subject...')
            self.search_input.setClearButtonEnabled(True)
            self.search_input.textChanged.connect(self.filter_teachers)
            search_row.addWidget(self.search_input, 1)
            layout.addLayout(search_row)

        content = QHBoxLayout()
        self.table = make_table()
        content.addWidget(self.table, 1)
        actions = QVBoxLayout()
        for text, handler, style in [
            ('↻ Refresh', self.refresh, ''), ('+ Add', self.add_record, 'primaryButton'),
            ('✎ Edit Selected', self.edit_record, 'editButton'), ('✕ Delete Selected', self.delete_record, 'dangerButton')
        ]:
            button = QPushButton(text)
            if style:
                button.setObjectName(style)
            button.clicked.connect(handler)
            button.setMinimumHeight(42)
            actions.addWidget(button)
        actions.addStretch(1)
        side = QWidget()
        side.setFixedWidth(170)
        side.setLayout(actions)
        content.addWidget(side)
        layout.addLayout(content, 1)
        self.info = QLabel('Ready')
        layout.addWidget(self.info)

    def selected(self):
        index = self.table.currentRow()
        visible = self.filtered_records if self.name == 'Teachers' else self.records
        if index < 0 or index >= len(visible):
            QMessageBox.information(self, 'Select a record', 'Select a row first.')
            return None
        return visible[index]

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

            if self.name == 'Teachers':
                self.filter_teachers()
            else:
                populate(self.table, self.records, display_fields)
            self.table.setProperty('id_fields', display_fields)
            self.info.setText(f'{len(self.records)} record(s)')
            self.status_callback(f'{self.name}: {len(self.records)} records loaded')
        except Exception as exc:
            self.info.setText('Could not load records')
            show_error(self, exc)

    def filter_teachers(self, *_):
        """Filter the loaded teacher rows without changing database records."""
        if self.name != 'Teachers':
            return
        query = self.search_input.text().strip().casefold()
        fields = ('teacher_id', 'first_name', 'last_name', 'department',
                  'subject_description', 'subject_id')
        self.filtered_records = [
            record for record in self.records
            if not query or query in ' '.join(
                str(record.get(field) or '') for field in fields
            ).casefold()
        ]
        display_fields = ['teacher_id', 'first_name', 'last_name', 'email',
                          'department', 'subject_description', 'subject_id']
        populate(self.table, self.filtered_records, display_fields)
        self.table.setProperty('id_fields', display_fields)
        self.info.setText(
            f'{len(self.filtered_records)} of {len(self.records)} teacher record(s)')

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
    """Choose an enrolled student and one of the selected offering's components."""
    def __init__(self, offering_id, students, components, selected_period=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Encode Component Score')
        self.setMinimumWidth(510)
        self.offering_id = offering_id
        self.components = components
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.student = QComboBox()
        self.student.addItem('Select an enrolled student', None)
        for row in students:
            self.student.addItem(f"{row['student_name']} ({row['student_id']})", row['enrollment_id'])
        self.period = QComboBox()
        self.period.addItem('Select period', None)
        for period in ('Midterm', 'Finals'):
            self.period.addItem(period, period)
        self.component = QComboBox()
        self.component.addItem('Select component', None)
        self.score = QLineEdit()
        self.score.setPlaceholderText('Enter raw score')
        self.maximum = QLabel('Maximum: —')
        self.remarks = QLineEdit()
        form.addRow('Enrolled student *', self.student)
        form.addRow('Period *', self.period)
        form.addRow('Component *', self.component)
        form.addRow('Raw score *', self.score)
        form.addRow('', self.maximum)
        form.addRow('Remarks', self.remarks)
        layout.addLayout(form)
        self.period.currentIndexChanged.connect(self.update_components)
        self.component.currentIndexChanged.connect(self.update_maximum)
        if selected_period:
            self.period.setCurrentIndex(self.period.findData(selected_period))
        self.update_components()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName('saveButton')
        buttons.accepted.connect(self.validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_components(self, *_):
        period = self.period.currentData()
        self.component.clear()
        self.component.addItem('Select component', None)
        for item in self.components:
            key = str(item['period_name']).lower()
            key = 'Finals' if key in ('final', 'finals') else 'Midterm' if key == 'midterm' else key
            if key == period:
                self.component.addItem(
                    f"{item['name']} / {item['type']} (/{item['max_score']})", item)
        self.update_maximum()

    def update_maximum(self, *_):
        item = self.component.currentData()
        self.maximum.setText(f"Maximum: {item['max_score']}" if item else 'Maximum: —')

    def validate_and_save(self):
        from decimal import Decimal, InvalidOperation
        student = self.student.currentData()
        component = self.component.currentData()
        if not student or not component:
            QMessageBox.warning(self, 'Missing selection', 'Select an enrolled student, period, and component.')
            return
        try:
            score = Decimal(self.score.text().strip())
            maximum = Decimal(str(component['max_score']))
            if not score.is_finite() or score < 0 or score > maximum:
                raise ValueError()
        except (InvalidOperation, ValueError):
            QMessageBox.warning(self, 'Invalid raw score',
                                f"Score must be a number between 0 and {component['max_score']}.")
            self.score.setFocus()
            return
        try:
            repo.save_score({
                'enrollment_id': student,
                'component_id': component['component_id'],
                'period_id': component['period_id'],
                'score': str(score),
                'remarks': self.remarks.text().strip(),
            })
        except Exception as exc:
            show_error(self, exc)
            return
        self.accept()


class ScoresPage(QWidget):
    """Offering-filtered component score gradebook with separate period tables."""
    def __init__(self, status_callback=None):
        super().__init__()
        self.status_callback = status_callback or (lambda text: None)
        self._loading = False
        self.components = []
        self.students = []
        self.scores = {}
        layout = QVBoxLayout(self)
        heading = QLabel('COMPONENT SCORE')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        selector = QHBoxLayout()
        selector.addWidget(QLabel('Subject / Class Offering'))
        self.offering = QComboBox()
        self.offering.setMinimumWidth(300)
        selector.addWidget(self.offering, 1)
        layout.addLayout(selector)
        self.tabs = QTabWidget()
        self.tabs.setObjectName('scorePeriodTabs')
        self.tabs.setDocumentMode(False)
        self.tabs.setStyleSheet('''
            QTabWidget#scorePeriodTabs::pane { border: 2px solid #242424; background: #fdf8ef; }
            QTabWidget#scorePeriodTabs QTabBar::tab {
                background: #d8d0bd; color: #222; border: 2px solid #252525;
                padding: 11px 34px; min-width: 115px; font-weight: bold;
            }
            QTabWidget#scorePeriodTabs QTabBar::tab:selected { background: #ffd471; }
            QTabWidget#scorePeriodTabs QTabBar::tab:hover:!selected { background: #eee0bd; }
        ''')
        self.tables = {}
        for period in ('Midterm', 'Finals'):
            table = make_table()
            table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.horizontalHeader().setMinimumSectionSize(105)
            table.verticalHeader().setDefaultSectionSize(38)
            table.setShowGrid(True)
            table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                  QAbstractItemView.EditTrigger.EditKeyPressed)
            table.itemChanged.connect(lambda item, p=period: self.save_cell(p, item))
            self.tables[period] = table
            self.tabs.addTab(table, period)
        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self.tabs, 1)
        side = QVBoxLayout()
        for label, callback in [('↻ Refresh', self.refresh),
                                ('+ Encode Score', self.add_score),
                                ('✓ Calculate Period Grade', self.calculate)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            if 'Encode' in label: button.setObjectName('primaryButton')
            if 'Calculate' in label: button.setObjectName('saveButton')
            side.addWidget(button)
        side.addStretch()
        actions = QWidget()
        actions.setFixedWidth(190)
        actions.setLayout(side)
        body.addWidget(actions)
        layout.addLayout(body, 1)
        self.info = QLabel('Choose a subject to view enrolled students and scores.')
        layout.addWidget(self.info)
        self.offering.currentIndexChanged.connect(self.refresh)
        self.load_offerings()

    def load_offerings(self):
        try:
            old = self.offering.currentData()
            self.offering.blockSignals(True)
            self.offering.clear()
            self.offering.addItem('— Select subject / class —', None)
            for row in repo.component_offerings():
                label = (f"{row['subject_code']} — {row['subject_name']} | "
                         f"{row['class_code']} | {row['school_year']} {row['semester']}")
                self.offering.addItem(label, row['offering_id'])
            if old is not None:
                idx = self.offering.findData(old)
                if idx >= 0: self.offering.setCurrentIndex(idx)
        except Exception as exc:
            show_error(self, exc)
        finally:
            self.offering.blockSignals(False)
        self.refresh()

    def refresh(self, *_):
        self._loading = True
        try:
            offering_id = self.offering.currentData()
            self.components = repo.offering_components(offering_id) if offering_id else []
            self.students, self.scores = repo.offering_score_grid(offering_id) if offering_id else ([], {})
            for period, table in self.tables.items():
                comps = [c for c in self.components
                         if ('Finals' if str(c['period_name']).lower() in ('final','finals')
                             else 'Midterm' if str(c['period_name']).lower() == 'midterm' else '')
                         == period]
                table.blockSignals(True)
                table.clear()
                table.setRowCount(len(self.students))
                table.setColumnCount(2 + len(comps))
                table.setHorizontalHeaderLabels(
                    ['Student ID', 'Student Name'] +
                    [f"{c['name']} (/{c['max_score']})" for c in comps])
                for row_idx, student in enumerate(self.students):
                    for col_idx, value in enumerate((student['student_id'], student['student_name'])):
                        cell = QTableWidgetItem(str(value))
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        table.setItem(row_idx, col_idx, cell)
                    for col_idx, comp in enumerate(comps, 2):
                        saved = self.scores.get((student['enrollment_id'], comp['component_id']))
                        cell = QTableWidgetItem(str(saved['score']) if saved else '')
                        cell.setData(Qt.ItemDataRole.UserRole, comp)
                        cell.setToolTip(f"Maximum: {comp['max_score']} | Enrollment: {student['enrollment_id']}")
                        table.setItem(row_idx, col_idx, cell)
                table.setProperty('id_fields', [])
                # Stretch short gradebooks to fill the available area; scroll when wide.
                header = table.horizontalHeader()
                if table.columnCount() <= 5:
                    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                else:
                    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                    table.setColumnWidth(0, 145)
                    table.setColumnWidth(1, 205)
                    for column in range(2, table.columnCount()):
                        table.setColumnWidth(column, 185)
                table.blockSignals(False)
            self.info.setText(
                f"{len(self.students)} enrolled student(s) | {len(self.components)} configured components | "
                "Double-click a score to edit, or use Encode Score.")
        except Exception as exc:
            show_error(self, exc)
        finally:
            for table in self.tables.values():
                table.blockSignals(False)
            self._loading = False

    def save_cell(self, period, item):
        if self._loading or item.column() < 2 or item.row() >= len(self.students):
            return
        from decimal import Decimal, InvalidOperation
        comp = item.data(Qt.ItemDataRole.UserRole)
        if not comp:
            return
        student = self.students[item.row()]
        try:
            value = Decimal(item.text().strip())
            maximum = Decimal(str(comp['max_score']))
            if not value.is_finite() or not (0 <= value <= maximum):
                raise ValueError(f'Score must be between 0 and {maximum}.')
            repo.save_score({
                'enrollment_id': student['enrollment_id'],
                'component_id': comp['component_id'],
                'period_id': comp['period_id'],
                'score': str(value), 'remarks': None})
            self.status_callback(f"Saved {student['student_name']} — {comp['name']}: {value}")
        except (InvalidOperation, ValueError) as exc:
            QMessageBox.warning(self, 'Invalid score', str(exc) if str(exc) else 'Enter a valid score.')
        except Exception as exc:
            show_error(self, exc)
        self.refresh()

    def add_score(self, *_):
        if not self.offering.currentData():
            QMessageBox.information(self, 'Choose subject', 'Select a subject/class offering first.')
            return
        period = self.tabs.tabText(self.tabs.currentIndex())
        dialog = ScoreDialog(self.offering.currentData(), self.students,
                             self.components, period, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def calculate(self, *_):
        if not self.offering.currentData():
            QMessageBox.information(self, 'Choose subject', 'Select a subject/class offering first.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Calculate Period Grade')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        student = QComboBox()
        for row in self.students:
            student.addItem(f"{row['student_name']} ({row['student_id']})", row['enrollment_id'])
        period = QComboBox()
        period.addItem('Choose period', None)
        seen = set()
        for c in self.components:
            if c['period_id'] not in seen:
                seen.add(c['period_id'])
                period.addItem(str(c['period_name']), c['period_id'])
        form.addRow('Student', student)
        form.addRow('Period', period)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if student.currentData() is None or period.currentData() is None:
                QMessageBox.warning(self, 'Missing selection', 'Choose a student and period.')
                return
            try:
                grade = repo.calculate_period_grade(student.currentData(), period.currentData())
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
            if self.overall:
                # Convert only the displayed period grades to the existing
                # college grade-point scale. Keep raw percentages in the DB
                # and use them for weighted overall grade calculations.
                records = [dict(record) for record in records]
                for record in records:
                    for key in ('midterm_percentage', 'finals_percentage'):
                        value = record.get(key)
                        record[key] = (f'{repo.college_grade_point(value):.2f}'
                                       if value is not None else None)
            populate(self.table, records, fields)
            if self.overall:
                self.table.setHorizontalHeaderLabels([
                    'Student ID', 'First Name', 'Last Name', 'Class Code',
                    'Midterm Grade', 'Finals Grade', 'Overall %',
                    'Final Equivalent', 'Remarks'
                ])
            self.table.setProperty('id_fields', fields)
            self.info.setText(f'{len(records)} record(s)')
        except Exception as exc:
            show_error(self, exc)
