"""Interactive, read-only report pages. Styling comes from existing StudentDB QSS."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMessageBox
)
from . import academic_reports as reports


def _display(value):
    return '' if value is None else str(value)


class ReportPage(QWidget):
    def __init__(self, report_type, status_callback=None):
        super().__init__()
        self.report_type = report_type
        self.status_callback = status_callback
        names = {
            'class_list': 'CLASS LIST',
            'grade_sheet': 'CLASS GRADE SHEET',
            'student_report': 'STUDENT GRADE REPORT & GWA',
        }
        root = QVBoxLayout(self)
        heading = QLabel(names[report_type])
        heading.setObjectName('sectionTitle')
        root.addWidget(heading)
        tools = QHBoxLayout()
        tools.addWidget(QLabel('Teacher: ' if report_type == 'class_list' else ('Select student:' if report_type == 'student_report' else 'Select class:')))
        self.teacher_selector = None
        if report_type == 'class_list':
            self.teacher_selector = QComboBox()
            self.teacher_selector.setMinimumWidth(170)
            tools.addWidget(self.teacher_selector, 1)
            tools.addWidget(QLabel('Assigned subject / section:'))
        self.selector = QComboBox()
        tools.addWidget(self.selector, 2)
        refresh = QPushButton('Refresh Report')
        refresh.setObjectName('primaryButton')
        refresh.clicked.connect(self.refresh)
        tools.addWidget(refresh)
        root.addLayout(tools)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        root.addWidget(self.table)
        self.summary = QLabel('Select a record to view its report.')
        root.addWidget(self.summary)
        self.selector.currentIndexChanged.connect(self.refresh)
        if self.teacher_selector is not None:
            self.teacher_selector.currentIndexChanged.connect(self.load_teacher_subjects)
        self.load_choices()

    def load_choices(self):
        if self.report_type == 'class_list':
            try:
                self.teacher_selector.blockSignals(True)
                previous = self.teacher_selector.currentData()
                self.teacher_selector.clear()
                self.teacher_selector.addItem('Select a teacher...', None)
                for option in reports.teacher_choices():
                    self.teacher_selector.addItem(str(option['label']), option['id'])
                index = self.teacher_selector.findData(previous)
                self.teacher_selector.setCurrentIndex(index if index >= 0 else 0)
                self.teacher_selector.blockSignals(False)
                self.load_teacher_subjects()
            except Exception as exc:
                QMessageBox.critical(self, 'Report error', str(exc))
            return
        try:
            options = (reports.student_choices() if self.report_type == 'student_report'
                       else reports.class_choices())
            self.selector.blockSignals(True)
            self.selector.clear()
            for option in options:
                self.selector.addItem(str(option['label']), option['id'])
            self.selector.blockSignals(False)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, 'Report error', str(exc))

    def load_teacher_subjects(self, *_):
        if self.teacher_selector is None:
            return
        teacher_id = self.teacher_selector.currentData()
        previous_offering = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem('Select an assigned subject...', None)
        try:
            if teacher_id is not None:
                for option in reports.teacher_subject_choices(teacher_id):
                    self.selector.addItem(str(option['label']), option['id'])
            index = self.selector.findData(previous_offering)
            self.selector.setCurrentIndex(index if index >= 0 else 0)
        except Exception as exc:
            QMessageBox.critical(self, 'Report error', str(exc))
        finally:
            self.selector.blockSignals(False)
        self.refresh()

    def select_offering(self, offering_id):
        """Allow navigation from Class Offerings to preselect teacher and subject."""
        if self.teacher_selector is None:
            return False
        try:
            teacher_id = reports.teacher_for_offering(offering_id)
            index = self.teacher_selector.findData(teacher_id)
            if index < 0:
                self.load_choices()
                index = self.teacher_selector.findData(teacher_id)
            if index < 0:
                return False
            self.teacher_selector.setCurrentIndex(index)
            offering_index = self.selector.findData(offering_id)
            if offering_index < 0:
                return False
            self.selector.setCurrentIndex(offering_index)
            return True
        except Exception:
            return False

    def _populate(self, headers, fields, records):
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(records))
        for i, record in enumerate(records):
            for j, field in enumerate(fields):
                self.table.setItem(i, j, QTableWidgetItem(_display(record.get(field))))
        self.table.resizeColumnsToContents()

    def refresh(self, *_):
        selected = self.selector.currentData()
        if selected is None:
            self.table.setRowCount(0)
            self.summary.setText('Select a teacher and an assigned subject to view enrolled students.' if self.report_type == 'class_list' else 'No records available.')
            return
        try:
            if self.report_type == 'class_list':
                rows = reports.class_list(selected)
                self._populate(['Student ID', 'Last Name', 'First Name', 'Enrollment Status', 'Class'],
                               ['student_id', 'last_name', 'first_name', 'enrollment_status', 'class_code'], rows)
                summary = f'{len(rows)} enrollment(s) in this class'
            elif self.report_type == 'grade_sheet':
                rows = reports.class_grade_sheet(selected)
                self._populate(['Student ID', 'Last Name', 'First Name', 'Midterm %', 'MG Point',
                                'Finals %', 'FG Point', 'Overall %', 'Final Point', 'Remarks'],
                               ['student_id', 'last_name', 'first_name', 'midterm', 'midterm_equiv',
                                'finals', 'finals_equiv', 'overall', 'final_equiv', 'remarks'], rows)
                summary = f'{len(rows)} student enrollment(s); pending grades remain blank'
            else:
                rows, gwa, units = reports.student_grade_report(selected)
                self._populate(['Class', 'Subject Code', 'Subject Name', 'Teacher', 'Units',
                                'Midterm %', 'Finals %', 'Overall %', 'Final Point', 'Remarks'],
                               ['class_code', 'subject_code', 'subject_name', 'teacher', 'units',
                                'midterm', 'finals', 'overall', 'final_equiv', 'remarks'], rows)
                summary = (f'GWA: {_display(gwa) if gwa is not None else "Pending"}  |  '
                           f'Completed units: {units}  |  Enrollments: {len(rows)}')
            self.summary.setText(summary)
            if self.status_callback:
                self.status_callback(summary)
        except Exception as exc:
            QMessageBox.critical(self, 'Report error', str(exc))
