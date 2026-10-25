"""Compact enrollment management with inline selectors and date entry."""
from datetime import date
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDateEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QFrame, QSplitter
)
from . import academic_repository as repo
from .academic_pages import show_error


class EnrollmentsPage(QWidget):
    def __init__(self, status_callback=None):
        super().__init__()
        self.status_callback = status_callback or (lambda text: None)
        self.records = []
        self.visible_records = []
        self._selected_id = None
        layout = QVBoxLayout(self)
        title = QLabel('ENROLLMENTS')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        layout.addWidget(body, 1)

        table_panel = QWidget()
        left = QVBoxLayout(table_panel)
        left.addWidget(QLabel('ENROLLMENT RECORDS'))
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Enrollment ID', 'Student', 'Class', 'Enroll Date', 'Status'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.itemSelectionChanged.connect(self.load_selected)
        self.table.setProperty('id_fields', ['enrollment_id', 'student_id', 'offering_id', 'enroll_date', 'status'])
        left.addWidget(self.table, 1)
        self.info = QLabel('0 enrollment(s)')
        left.addWidget(self.info)
        body.addWidget(table_panel)

        form_panel = QFrame()
        right = QVBoxLayout(form_panel)
        right.addWidget(QLabel('ENROLLMENT DETAILS'))
        form = QFormLayout()
        self.student = QComboBox()
        self.student.setMinimumWidth(225)
        self.offering = QComboBox()
        self.status = QComboBox()
        for value, label in [('enrolled', 'Enrolled'), ('dropped', 'Unenrolled / Dropped'), ('completed', 'Completed')]:
            self.status.addItem(label, value)
        self.enroll_date = QDateEdit()
        self.enroll_date.setCalendarPopup(True)
        self.enroll_date.setDisplayFormat('yyyy-MM-dd')
        self.enroll_date.setDate(QDate.currentDate())
        form.addRow('Student ID / Name *', self.student)
        form.addRow('Offering ID / Class *', self.offering)
        form.addRow('Enrollment Status *', self.status)
        form.addRow('Enroll Date *', self.enroll_date)
        right.addLayout(form)
        self.selection_label = QLabel('New enrollment')
        right.addWidget(self.selection_label)
        for caption, callback, style in (
            ('↻ Refresh', self.refresh, ''),
            ('✓ Save Enrollment', self.save, 'primaryButton'),
            ('✎ Update Selected', self.update, 'editButton'),
            ('✕ Delete Selected', self.delete, 'dangerButton'),
            ('Clear Selection', self.clear_form, ''),
        ):
            button = QPushButton(caption)
            button.setMinimumHeight(42)
            if style:
                button.setObjectName(style)
            button.clicked.connect(callback)
            right.addWidget(button)
        right.addStretch(1)
        body.addWidget(form_panel)
        body.setSizes([700, 370])
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        self.refresh()

    def _choices(self):
        from db import get_db
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""SELECT student_id, CONCAT_WS(' ',first_name,last_name) AS name
                           FROM student ORDER BY last_name,first_name""")
            students = cur.fetchall()
            cur.execute("""SELECT o.offering_id, o.class_code, s.subject_code, o.section
                           FROM class_offering o LEFT JOIN subject s ON s.subject_id=o.subject_id
                           ORDER BY o.class_code, o.section""")
            offerings = cur.fetchall()
        return students, offerings

    def refresh(self, *_):
        try:
            students, offerings = self._choices()
            old_student, old_offering = self.student.currentData(), self.offering.currentData()
            self.student.blockSignals(True)
            self.student.clear()
            self.student.addItem('— Select student —', None)
            for student in students:
                self.student.addItem(f"{student['student_id']} — {student['name']}", str(student['student_id']))
            self.student.setCurrentIndex(max(0, self.student.findData(old_student)))
            self.student.blockSignals(False)
            self.offering.blockSignals(True)
            self.offering.clear()
            self.offering.addItem('— Select class offering —', None)
            for offering in offerings:
                self.offering.addItem(
                    f"{offering['class_code']} | {offering['subject_code']} | "
                    f"Section {offering['section']} ({offering['offering_id']})",
                    str(offering['offering_id']))
            self.offering.setCurrentIndex(max(0, self.offering.findData(old_offering)))
            self.offering.blockSignals(False)
            self.records = repo.rows('Enrollments')
            self.visible_records = self.records
            self.table.blockSignals(True)
            self.table.setRowCount(len(self.records))
            for i, record in enumerate(self.records):
                values = (
                    record.get('enrollment_id'), record.get('student_id'),
                    record.get('offering_id'), record.get('enroll_date'), record.get('status'))
                for j, value in enumerate(values):
                    self.table.setItem(i, j, QTableWidgetItem(str(value or '')))
            self.table.blockSignals(False)
            self.info.setText(f'{len(self.records)} enrollment(s)')
            if self._selected_id:
                for i, record in enumerate(self.records):
                    if str(record['enrollment_id']) == str(self._selected_id):
                        self.table.selectRow(i)
                        break
            self.status_callback(f'Enrollments: {len(self.records)} records loaded')
        except Exception as exc:
            show_error(self, exc)

    def load_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            return
        record = self.records[row]
        self._selected_id = record['enrollment_id']
        self.student.setCurrentIndex(max(0, self.student.findData(str(record['student_id']))))
        self.offering.setCurrentIndex(max(0, self.offering.findData(str(record['offering_id']))))
        self.status.setCurrentIndex(max(0, self.status.findData(str(record['status']).lower())))
        value = record.get('enroll_date')
        if value:
            parsed = QDate.fromString(str(value)[:10], 'yyyy-MM-dd')
            if parsed.isValid():
                self.enroll_date.setDate(parsed)
        self.selection_label.setText(f"Selected: {self._selected_id}")

    def _values(self):
        if not self.student.currentData():
            self.student.setFocus()
            raise ValueError('Select a student.')
        if not self.offering.currentData():
            self.offering.setFocus()
            raise ValueError('Select a class offering.')
        return {
            'student_id': self.student.currentData(),
            'offering_id': self.offering.currentData(),
            'status': self.status.currentData(),
            'enroll_date': self.enroll_date.date().toString('yyyy-MM-dd')
        }

    def save(self, *_):
        try:
            repo.save_entity('Enrollments', self._values())
            self.clear_form()
            self.refresh()
            self.status_callback('Enrollment saved')
        except Exception as exc:
            show_error(self, exc)

    def update(self, *_):
        if not self._selected_id:
            QMessageBox.information(self, 'Select enrollment', 'Select a row to update.')
            return
        try:
            repo.save_entity('Enrollments', self._values(), self._selected_id)
            self.refresh()
            self.status_callback('Enrollment updated')
        except Exception as exc:
            show_error(self, exc)

    def delete(self, *_):
        if not self._selected_id:
            QMessageBox.information(self, 'Select enrollment', 'Select a row to delete.')
            return
        if QMessageBox.question(
            self, 'Confirm deletion',
            'Delete this enrollment? Existing scores may prevent deletion.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            repo.delete_entity('Enrollments', self._selected_id)
            self.clear_form()
            self.refresh()
        except Exception as exc:
            show_error(self, exc)

    def clear_form(self, *_):
        self._selected_id = None
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)
        self.student.setCurrentIndex(0)
        self.offering.setCurrentIndex(0)
        self.status.setCurrentIndex(0)
        self.enroll_date.setDate(QDate.currentDate())
        self.selection_label.setText('New enrollment')
