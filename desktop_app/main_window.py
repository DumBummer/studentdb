"""Retro StudentDB PySide6 GUI. No Flask files or database schema are changed."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QFont, QFontDatabase, QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QGraphicsDropShadowEffect, QTabWidget, QScrollArea
)
from . import repository
from .retro_tables import install_retro_table_style
from .academic_pages import EntityPage, RecordDialog, populate, ScoresPage, GradesPage, show_error
from . import academic_repository as academic_repo
from db import get_db
from .report_pages import ReportPage
from .class_offerings_page import ClassOfferingsPage
from .enrollments_page import EnrollmentsPage
from .audit_page import AuditHistoryPage

class RetroControlShadows(QObject):
    """Apply crisp arcade-style shadows to buttons and combo boxes, including dialogs."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Polish and isinstance(watched, (QPushButton, QComboBox)):
            if watched.graphicsEffect() is None:
                shadow = QGraphicsDropShadowEffect(watched)
                shadow.setBlurRadius(12)
                shadow.setOffset(0, 2)
                shadow.setColor(QColor(25, 36, 42, 32))
                watched.setGraphicsEffect(shadow)
        return super().eventFilter(watched, event)


BASE = Path(__file__).resolve().parent
NAV_ITEMS = [
    ('▦', 'Dashboard'), ('▣', 'Students'), ('▤', 'Teachers'),
    ('▧', 'Subjects'), ('▥', 'Classes'), ('▨', 'Enrollments'),
    ('▣', 'Grading Configuration'), ('▥', 'Component Score'),
    ('▦', 'Grades & Transcripts'), ('▧', 'Overall Grades'),
    ('▥', 'Class Grade Sheet'), ('▦', 'Student Grade Report'),
    ('▣', 'Audit History'),
]


class SubjectGradingPage(EntityPage):
    def __init__(self, name, status_callback=None):
        super().__init__(name, status_callback)
        self.offerings_by_subject = {}
        self.periods_by_subject = {}
        line_widget = QWidget()
        line = QHBoxLayout(line_widget)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(QLabel('SUBJECT'))
        self.subject_filter = QComboBox()
        self.subject_filter.setMinimumWidth(260)
        line.addWidget(self.subject_filter, 1)
        note = ('Periods are shared across subjects; showing periods used by this subject.'
                if name == 'Grading Periods' else 'Filtered by subject and its class offerings.')
        hint = QLabel(note)
        hint.setWordWrap(True)
        line.addWidget(hint, 2)
        self.layout().insertWidget(1, line_widget)
        self.subject_filter.currentIndexChanged.connect(self.apply_subject_filter)

    def refresh(self, *_):
        try:
            with get_db() as conn, conn.cursor() as cur:
                cur.execute("""SELECT s.subject_id, s.subject_code, s.subject_name, o.offering_id
                    FROM subject s LEFT JOIN class_offering o ON o.subject_id=s.subject_id
                    ORDER BY s.subject_code, o.class_code, o.section""")
                options = cur.fetchall()
                cur.execute("""SELECT DISTINCT o.subject_id, c.grading_period_id AS period_id
                    FROM grade_component c JOIN class_offering o ON o.offering_id=c.offering_id
                    WHERE c.grading_period_id IS NOT NULL""")
                periods = cur.fetchall()
                periods.extend(academic_repo.subject_period_links())
            self.offerings_by_subject = {}
            self.periods_by_subject = {}
            for r in periods:
                self.periods_by_subject.setdefault(str(r['subject_id']), set()).add(str(r['period_id']))
            previous = self.subject_filter.currentData()
            self.subject_filter.blockSignals(True)
            self.subject_filter.clear()
            self.subject_filter.addItem('All subjects', None)
            seen = set()
            for r in options:
                sid = str(r['subject_id'])
                self.offerings_by_subject.setdefault(sid, set())
                if r['offering_id'] is not None:
                    self.offerings_by_subject[sid].add(str(r['offering_id']))
                if sid not in seen:
                    seen.add(sid)
                    self.subject_filter.addItem(f"{r['subject_code']} — {r['subject_name']}", sid)
            idx = self.subject_filter.findData(previous)
            self.subject_filter.setCurrentIndex(idx if idx >= 0 else 0)
            self.subject_filter.blockSignals(False)
            self.records = academic_repo.rows(self.name)
            self.apply_subject_filter()
        except Exception as exc:
            self.info.setText('Could not load grading records')
            show_error(self, exc)

    def apply_subject_filter(self, *_):
        subject = self.subject_filter.currentData()
        if subject is None:
            self.filtered_records = list(self.records)
        elif self.name == 'Grading Periods':
            allowed = self.periods_by_subject.get(subject, set())
            self.filtered_records = [r for r in self.records if str(r['period_id']) in allowed]
        else:
            allowed = self.offerings_by_subject.get(subject, set())
            self.filtered_records = [r for r in self.records if str(r.get('offering_id')) in allowed]
        _, pk, fields, _ = academic_repo.entity_fields(self.name)
        display_fields = [pk] + fields
        populate(self.table, self.filtered_records, display_fields)
        self.table.setProperty('id_fields', display_fields)
        self.info.setText(f'{len(self.filtered_records)} of {len(self.records)} record(s)')
        self.status_callback(f'{self.name}: {len(self.filtered_records)} records shown')

    def selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.filtered_records):
            QMessageBox.information(self, 'Select a record', 'Select a row first.')
            return None
        return self.filtered_records[row]

    def open_dialog(self, record=None):
        if self.name != 'Grading Periods':
            return super().open_dialog(record)
        try:
            _, _, fields, schema = academic_repo.entity_fields(self.name)
            dialog = RecordDialog(self.name, fields, schema, record, self)
            current_subject = self.subject_filter.currentData()
            if current_subject is not None:
                index = dialog.subject_selector.findData(current_subject)
                if index >= 0:
                    dialog.subject_selector.setCurrentIndex(index)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                academic_repo.assign_subject_period(
                    dialog.subject_selector.currentData(), dialog.values(),
                    record['period_id'] if record else None)
                self.refresh()
        except Exception as exc:
            show_error(self, exc)


class GradingConfigurationPage(QWidget):
    """Keep the existing three working CRUD editors accessible under one sidebar entry."""
    def __init__(self, status_callback):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('GRADING CONFIGURATION')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        note = QLabel('Configure periods, components, and weights using the tabs below. '
                      'Existing score records remain in PostgreSQL.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs = QTabWidget()
        self.tabs.setObjectName('gradingConfigTabs')
        self.tabs.setStyleSheet('''
            QTabWidget#gradingConfigTabs::pane { border: 2px solid #242424; background: #fdf8ef; }
            QTabWidget#gradingConfigTabs QTabBar::tab {
                background: #d8d0bd; color: #222; border: 2px solid #252525;
                padding: 11px 24px; min-width: 135px; font-weight: bold;
            }
            QTabWidget#gradingConfigTabs QTabBar::tab:selected { background: #ffd471; }
            QTabWidget#gradingConfigTabs QTabBar::tab:hover:!selected { background: #eee0bd; }
        ''')
        self.editors = {}
        for name in ('Grading Periods', 'Grade Components', 'Grade Weights'):
            editor = SubjectGradingPage(name, status_callback)
            editor.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            editor.table.horizontalHeader().setMinimumSectionSize(110)
            editor.table.verticalHeader().setDefaultSectionSize(38)
            editor.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            self.editors[name] = editor
            self.tabs.addTab(editor, name)
        layout.addWidget(self.tabs, 1)

    def refresh(self):
        self.editors[self.tabs.tabText(self.tabs.currentIndex())].refresh()

    def open_editor(self, name):
        editor = self.editors[name]
        self.tabs.setCurrentWidget(editor)
        editor.refresh()
        return editor


class StudentDialog(QDialog):
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Student' if record else 'New Student')
        self.setMinimumWidth(430)
        self.record = record
        root = QVBoxLayout(self)
        title = QLabel('STUDENT RECORD EDITOR')
        title.setObjectName('sectionTitle')
        root.addWidget(title)
        form = QFormLayout()
        self.fields = {}
        for key, label in [('student_id', 'Student ID'), ('first_name', 'First Name'),
                           ('last_name', 'Last Name'), ('email', 'Email'), ('program', 'Program')]:
            edit = QLineEdit(str((record or {}).get(key) or ''))
            edit.setPlaceholderText(label)
            if key == 'student_id' and record:
                edit.setReadOnly(True)
            form.addRow(label + ':', edit)
            self.fields[key] = edit
        self.year_level = QComboBox()
        self.year_level.addItems([
            '1st Year',
            '2nd Year',
            '3rd Year',
            '4th Year'
        ])

        self.year_level.setCurrentText(
            str((record or {}).get('year_level') or '1st Year')
        )

        form.addRow('Year Level:', self.year_level)
        self.status = QComboBox()
        self.status.addItems(['Active', 'Inactive', 'Enrolled', 'Graduated'])
        existing_status = str((record or {}).get('status') or 'Active')
        if self.status.findText(existing_status) < 0:
            self.status.addItem(existing_status)
        self.status.setCurrentText(existing_status)
        form.addRow('Status:', self.status)
        root.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        save = QPushButton('Save Record')
        save.setObjectName('saveButton')
        save.clicked.connect(self.validate_and_accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)

    def validate_and_accept(self):
        values = self.values()
        if not values['student_id'] or not values['first_name'] or not values['last_name']:
            QMessageBox.warning(self, 'Missing Information',
                                'Student ID, first name, and last name are required.')
            return
        self.accept()

    def values(self):
        result = {key: field.text().strip() for key, field in self.fields.items()}
        result['status'] = self.status.currentText()
        result['year_level'] = self.year_level.currentText()
        return result


class StudentsPage(QWidget):
    def __init__(self, status_callback):
        super().__init__()
        self.status_callback = status_callback
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.addWidget(section_header('STUDENT RECORDS', 'Manage student information'))
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search ID, name, email or program...')
        self.search.textChanged.connect(self.refresh)
        tools.addWidget(self.search, 1)
        refresh = QPushButton('↻ Refresh')
        refresh.clicked.connect(self.refresh)
        add = QPushButton('+ Add Student')
        add.setObjectName('primaryButton')
        add.clicked.connect(self.add_record)
        root.addLayout(tools)
        button_column = QVBoxLayout()
        button_column.setSpacing(8)
        button_column.addWidget(refresh)
        button_column.addWidget(add)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Student ID',
            'First Name',
            'Last Name',
            'Email',
            'Program',
            'Year Level',
            'Status'
            ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.cellDoubleClicked.connect(self.on_double_click)
        self.table.setColumnWidth(0, 135)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(5, 110)
        table_row = QHBoxLayout()
        table_row.addWidget(self.table, 1)
        actions = button_column
        self.count_label = QLabel('0 student records')
        actions.addStretch()
        edit = QPushButton('✎ Edit Selected')
        edit.setObjectName('editButton')
        edit.clicked.connect(self.edit_record)
        actions.addWidget(edit)
        delete = QPushButton('✕ Delete Selected')
        delete.setObjectName('dangerButton')
        delete.clicked.connect(self.delete_record)
        actions.addWidget(delete)
        side_panel = QWidget()
        side_panel.setFixedWidth(170)
        side_panel.setLayout(actions)
        table_row.addWidget(side_panel)
        root.addLayout(table_row, 1)
        root.addWidget(self.count_label)
        self.refresh()

    def on_double_click(self, row, column):
        field = repository.FIELDS[column]
        if field.endswith('_id') and self.window().open_link(field, self.table.item(row, column).text()):
            return
        self.edit_record()

    def selected_record(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Select Student', 'Select a student row first.')
            return None
        keys = repository.FIELDS
        return {key: self.table.item(row, index).text() for index, key in enumerate(keys)}

    def refresh(self, *_):
        try:
            records = repository.list_students(self.search.text())
        except Exception as exc:
            self.table.setRowCount(0)
            self.count_label.setText('Database unavailable')
            self.status_callback('Database connection error')
            show_error(self, exc)
            return
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            for col, key in enumerate(repository.FIELDS):
                item = QTableWidgetItem(str(record.get(key) or ''))
                self.table.setItem(row, col, item)
        self.count_label.setText(f'{len(records)} student record(s)')
        self.status_callback(f'Loaded {len(records)} students')

    def add_record(self):
        dialog = StudentDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                repository.add_student(dialog.values())
                self.refresh()
                self.status_callback('Student added')
            except Exception as exc:
                show_error(self, exc)

    def edit_record(self, *_):
        record = self.selected_record()
        if not record:
            return
        dialog = StudentDialog(self, record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                repository.update_student(record['student_id'], dialog.values())
                self.refresh()
                self.status_callback('Student updated')
            except Exception as exc:
                show_error(self, exc)

    def delete_record(self):
        record = self.selected_record()
        if not record:
            return
        answer = QMessageBox.question(
            self, 'Confirm Deletion',
            f"Delete student {record['student_id']}?\nThis may be blocked if the student has enrollments.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            try:
                repository.delete_student(record['student_id'])
                self.refresh()
                self.status_callback('Student deleted')
            except Exception as exc:
                show_error(self, exc)


def section_header(title, subtitle):
    wrapper = QFrame()
    wrapper.setObjectName('panel')
    layout = QVBoxLayout(wrapper)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    sub = QLabel(subtitle)
    sub.setObjectName('subtitle')
    layout.addWidget(sub)
    return wrapper


class DashboardPage(QWidget):
    """Dashboard-only quick previews; no main-tab navigation."""
    PREVIEWS = {
        'Students': (
            ['Student ID', 'Full Name', 'Program', 'Year Level'],
            """SELECT student_id, CONCAT_WS(' ', first_name, last_name) AS full_name,
                      program, year_level FROM student ORDER BY student_id DESC LIMIT 200""",
            ('student_id', 'full_name', 'program', 'year_level')),
        'Teachers': (
            ['Teacher ID', 'Full Name', 'Department'],
            """SELECT teacher_id, CONCAT_WS(' ', first_name, last_name) AS full_name,
                      department FROM teacher ORDER BY teacher_id LIMIT 200""",
            ('teacher_id', 'full_name', 'department')),
        'Subjects': (
            ['Subject Code', 'Description', 'Units'],
            """SELECT subject_code, COALESCE(NULLIF(description, ''), subject_name) AS description,
                      units FROM subject ORDER BY subject_code LIMIT 200""",
            ('subject_code', 'description', 'units')),
        'Class Offerings': (
            ['Subject Code', 'Section', 'Semester', 'Schedule', 'Room', 'Teacher Name', 'Teacher ID'],
            """SELECT s.subject_code, o.section, o.semester, o.schedule, o.room,
                      CONCAT_WS(' ', t.first_name, t.last_name) AS teacher_name, t.teacher_id
               FROM class_offering o
               JOIN subject s ON s.subject_id = o.subject_id
               JOIN teacher t ON t.teacher_id = o.teacher_id
               ORDER BY s.subject_code, o.section LIMIT 200""",
            ('subject_code', 'section', 'semester', 'schedule', 'room', 'teacher_name', 'teacher_id')),
        'Enrollments': (
            ['Student Name', 'Student ID', 'Year Enrolled', 'Status'],
            """SELECT CONCAT_WS(' ', s.first_name, s.last_name) AS student_name,
                      s.student_id, EXTRACT(YEAR FROM e.enroll_date)::int AS year_enrolled,
                      CASE WHEN LOWER(e.status) = 'enrolled' THEN 'Enrolled'
                           ELSE 'Unenrolled' END AS status
               FROM enrollment e JOIN student s ON s.student_id = e.student_id
               ORDER BY e.enroll_date DESC, s.student_id LIMIT 200""",
            ('student_name', 'student_id', 'year_enrolled', 'status')),
    }

    def __init__(self, navigate_callback=None):
        super().__init__()
        self.active_preview = 'Students'
        root = QVBoxLayout(self)
        root.setSpacing(9)
        root.addWidget(section_header('SYSTEM DASHBOARD', 'StudentDB / Academic Control Center'))

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.stat_labels = {}
        for name, table in [('STUDENTS', 'student'), ('TEACHERS', 'teacher'),
                            ('SUBJECTS', 'subject'), ('ENROLLMENTS', 'enrollment')]:
            card = QFrame()
            card.setObjectName('panel')
            card.setMinimumWidth(0)
            content = QVBoxLayout(card)
            content.setContentsMargins(10, 8, 10, 8)
            heading = QLabel(name)
            heading.setObjectName('subtitle')
            content.addWidget(heading)
            number = QLabel('—')
            number.setObjectName('statLabel')
            content.addWidget(number)
            stats.addWidget(card, 1)
            self.stat_labels[table] = number
        root.addLayout(stats)

        preview = QFrame()
        preview.setObjectName('panel')
        preview_layout = QVBoxLayout(preview)
        preview_layout.setSpacing(8)
        self.preview_title = QLabel('STUDENTS / QUICK PREVIEW')
        preview_layout.addWidget(self.preview_title)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.recent_table = QTableWidget()
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.verticalHeader().setVisible(False)
        body.addWidget(self.recent_table, 1)

        controls = QFrame()
        controls.setObjectName('panel')
        controls.setFixedWidth(160)
        control_layout = QVBoxLayout(controls)
        control_layout.setContentsMargins(7, 9, 7, 9)
        control_layout.addWidget(QLabel('QUICK ACCESS'))
        self.quick_buttons = {}
        for name in self.PREVIEWS:
            button = QPushButton(name)
            button.setObjectName('navButton')
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.clicked.connect(lambda checked=False, label=name: self.show_preview(label))
            control_layout.addWidget(button)
            self.quick_buttons[name] = button
        control_layout.addStretch()
        body.addWidget(controls)
        preview_layout.addLayout(body, 1)
        root.addWidget(preview, 1)
        self.connection_label = QLabel('DATABASE STATUS: Not checked')
        self.connection_label.setObjectName('connectionStatus')
        root.addWidget(self.connection_label)
        install_retro_table_style(self.recent_table)
        self.show_preview('Students', load=False)

    def show_preview(self, name, load=True):
        if name not in self.PREVIEWS:
            return
        self.active_preview = name
        headers, _, _ = self.PREVIEWS[name]
        self.preview_title.setText(name.upper() + ' / QUICK PREVIEW')
        self.recent_table.clearContents()
        self.recent_table.setRowCount(0)
        self.recent_table.setColumnCount(len(headers))
        self.recent_table.setHorizontalHeaderLabels(headers)
        for button_name, button in self.quick_buttons.items():
            button.setChecked(button_name == name)
        if load:
            self.refresh()

    def refresh(self):
        from db import get_db
        try:
            with get_db() as conn, conn.cursor() as cur:
                for table, label in self.stat_labels.items():
                    cur.execute(f'SELECT COUNT(*) AS total FROM {table}')
                    label.setText(str(cur.fetchone()['total']))
                headers, query, keys = self.PREVIEWS[self.active_preview]
                cur.execute(query)
                records = cur.fetchall()
                self.recent_table.setRowCount(len(records))
                for i, record in enumerate(records):
                    for j, key in enumerate(keys):
                        value = record.get(key)
                        self.recent_table.setItem(
                            i, j, QTableWidgetItem('' if value is None else str(value)))
                # Keep columns usable, with horizontal scrolling for long offering records.
                self.recent_table.resizeColumnsToContents()
                for j in range(self.recent_table.columnCount()):
                    self.recent_table.setColumnWidth(
                        j, max(115, min(250, self.recent_table.columnWidth(j) + 14)))
                cur.execute('SELECT current_database() AS db, inet_server_port() AS port')
                info = cur.fetchone()
                self.connection_label.setText(
                    f"DATABASE STATUS: CONNECTED | {info['db']} | Port {info['port']}")
        except Exception as exc:
            self.connection_label.setText(f'DATABASE STATUS: UNAVAILABLE — {exc}')
            for label in self.stat_labels.values():
                label.setText('—')
            self.recent_table.setRowCount(0)


class PlaceholderPage(QWidget):
    def __init__(self, name):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(section_header(name.upper(), 'Desktop module coming next'))
        text = QLabel('This section is not connected yet.\nYour existing Flask functionality remains available.')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('NDMU Grading Management System — Desktop Edition')
        self.resize(1320, 820)
        self.setMinimumSize(940, 610)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        banner = QLabel('▣  NDMU                                      STUDENT INFORMATION & GRADING SYSTEM')
        banner.setObjectName('banner')
        outer.addWidget(banner)
        middle = QHBoxLayout()
        middle.setContentsMargins(16, 16, 16, 16)
        middle.setSpacing(16)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(238)
        side = QVBoxLayout(sidebar)
        side.setSpacing(8)
        side.addWidget(QLabel('WORKSPACE'))
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName('navScroll')
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_holder = QWidget()
        nav_layout = QVBoxLayout(nav_holder)
        nav_layout.setContentsMargins(0, 2, 5, 2)
        nav_layout.setSpacing(5)
        nav_scroll.setWidget(nav_holder)
        side.addWidget(nav_scroll, 1)
        nav_sections = {
            'Dashboard': 'OVERVIEW',
            'Students': 'ACADEMIC RECORDS',
            'Grading Configuration': 'GRADING',
            'Class Grade Sheet': 'REPORTS',
            'Audit History': 'SYSTEM',
        }
        self.nav_buttons = []
        self.pages = QStackedWidget()
        self.history = []  # Back stack: (page index, selected row identity)
        self.forward_history = []
        self._navigation_ready = False
        self.context_filters = {}
        self.context_labels = {}
        self.students_navigation_hint = 'Double-click an ID to open its source record'
        self.dashboard = DashboardPage(self.navigate)
        self.students = StudentsPage(self.set_status)
        for index, (symbol, name) in enumerate(NAV_ITEMS):
            if name in nav_sections:
                group_label = QLabel(nav_sections[name])
                group_label.setObjectName('navGroupLabel')
                nav_layout.addWidget(group_label)
            button = QPushButton(f'{symbol}   {name}')
            button.setObjectName('navButton')
            shadow = QGraphicsDropShadowEffect(button)
            shadow.setBlurRadius(10)
            shadow.setOffset(0, 2)
            shadow.setColor(QColor(25, 36, 42, 26))
            button.setGraphicsEffect(shadow)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=index: self.navigate(idx))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
            if index == 0:
                page = self.dashboard
            elif name == 'Students':
                page = self.students
            elif name == 'Grading Configuration':
                page = GradingConfigurationPage(self.set_status)
            elif name == 'Component Score':
                page = ScoresPage(self.set_status)
            elif name == 'Grades & Transcripts':
                page = GradesPage()
            elif name == 'Overall Grades':
                page = GradesPage(overall=True)
            elif name in ('Classes', 'Class Offerings'):
                page = ClassOfferingsPage(self.set_status)
            elif name == 'Enrollments':
                page = EnrollmentsPage(self.set_status)
            elif name == 'Class Grade Sheet':
                page = ReportPage('grade_sheet', self.set_status)
            elif name == 'Student Grade Report':
                page = ReportPage('student_report', self.set_status)
            elif name == 'Audit History':
                page = AuditHistoryPage(self.set_status)
            else:
                page = EntityPage(name, self.set_status)
            # Apply table styling to each page when it is created.
            for widget in page.findChildren(QTableWidget):
                install_retro_table_style(widget)
            self.pages.addWidget(page)
        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            if page is self.students:
                continue
            table = getattr(page, 'table', None)
            if table is not None:
                table.cellDoubleClicked.connect(
                    lambda row, col, page=page: self.handle_table_double_click(page, row, col))
        self._install_academic_actions()
        teacher_page = self.pages.widget(self._academic_index('Teachers'))
        if getattr(teacher_page, 'search_input', None) is not None:
            teacher_page.search_input.textChanged.connect(
                lambda *_: self._apply_context_filter(self._academic_index('Teachers'))
                if self.pages.currentWidget() is teacher_page else None)
        nav_layout.addStretch()
        side.addWidget(QLabel('SYSTEM  ▪  LOCAL DESKTOP'))
        middle.addWidget(sidebar)
        content = QFrame()
        content.setObjectName('content')
        content_layout = QVBoxLayout(content)
        back_bar = QHBoxLayout()
        self.back_button = QPushButton('← BACK')
        self.back_button.setObjectName('backButton')
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        back_bar.addWidget(self.back_button)
        self.forward_button = QPushButton('FORWARD →')
        self.forward_button.setObjectName('backButton')
        self.forward_button.setEnabled(False)
        self.forward_button.clicked.connect(self.go_forward)
        back_bar.addWidget(self.forward_button)
        self.home_button = QPushButton('⌂ DASHBOARD')
        self.home_button.setObjectName('backButton')
        self.home_button.clicked.connect(lambda: self.navigate(0))
        back_bar.addWidget(self.home_button)
        self.clear_filter_button = QPushButton('CLEAR FILTER')
        self.clear_filter_button.setObjectName('backButton')
        self.clear_filter_button.clicked.connect(self.clear_current_filter)
        back_bar.addWidget(self.clear_filter_button)
        self.breadcrumb = QLabel('DASHBOARD')
        self.breadcrumb.setObjectName('subtitle')
        back_bar.addWidget(self.breadcrumb)
        back_bar.addStretch()
        content_layout.addLayout(back_bar)
        content_layout.addWidget(self.pages)
        middle.addWidget(content, 1)
        outer.addLayout(middle, 1)
        self.footer = QLabel('  READY  |  PostgreSQL: existing connection  |  StudentDB Desktop v1')
        self.footer.setObjectName('footer')
        outer.addWidget(self.footer)
        self._navigation_ready = True
        self.navigate(0, remember=False)

    def set_status(self, message):
        if not hasattr(self, 'footer'):
            return
        self.footer.setText(f'  {message}  |  StudentDB Desktop v1')

    def handle_table_double_click(self, page, row, column):
        """Follow real foreign-key cells; otherwise preserve entity edit behavior."""
        table = page.table
        header = table.horizontalHeaderItem(column)
        cell = table.item(row, column)
        if not header or not cell:
            return
        fields = table.property('id_fields')
        field = (fields[column] if fields and column < len(fields)
                 else header.text().lower().replace(' ', '_'))
        if field.endswith('_id') and self.open_link(field, cell.text()):
            return
        if isinstance(page, EntityPage):
            page.edit_record()

    def _snapshot(self):
        """Remember current page and selected record, without storing table row numbers."""
        index = self.pages.currentIndex()
        return (index, self.current_record_id(), self.context_filters.get(index), self.context_labels.get(index, ''))

    def _update_navigation_controls(self):
        self.back_button.setEnabled(bool(self.history))
        self.forward_button.setEnabled(bool(self.forward_history))
        index = self.pages.currentIndex()
        if 0 <= index < len(NAV_ITEMS):
            name = NAV_ITEMS[index][1]
            suffix = self.context_labels.get(index, '')
            self.breadcrumb.setText('HOME  /  ' + name.upper() + (('  /  ' + suffix) if suffix else ''))
            self.clear_filter_button.setVisible(index in self.context_filters)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def _show_page(self, index, selected_id=None, filter_spec=None, label=''):
        if filter_spec is None:
            self.context_filters.pop(index, None)
            self.context_labels.pop(index, None)
        else:
            self.context_filters[index] = filter_spec
            self.context_labels[index] = label
        """Switch pages without modifying history (used by back/forward)."""
        self.pages.setCurrentIndex(index)
        page = self.pages.currentWidget()
        if page is self.dashboard:
            page.refresh()
        elif page is self.students:
            page.refresh()
        elif hasattr(page, 'refresh'):
            page.refresh()
        self._apply_context_filter(index)
        if selected_id is not None:
            self.restore_record(selected_id)
        self._update_navigation_controls()

    def _academic_index(self, name):
        return next((i for i, (_, label) in enumerate(NAV_ITEMS) if label == name), -1)

    def _selected_entity(self):
        page = self.pages.currentWidget()
        if isinstance(page, EntityPage):
            row = page.table.currentRow()
            visible = page.filtered_records if isinstance(page, SubjectGradingPage) or page.name == 'Teachers' else page.records
            return visible[row] if 0 <= row < len(visible) else None
        return None

    def _install_academic_actions(self):
        """Add related-record actions without replacing existing CRUD buttons."""
        actions = {
            'Subjects': [('VIEW CLASS OFFERINGS', 'subject_offerings')],
            'Teachers': [('VIEW ASSIGNED CLASSES', 'teacher_offerings')],
        }
        for name, buttons in actions.items():
            index = self._academic_index(name)
            if index < 0:
                continue
            page = self.pages.widget(index)
            panel = QHBoxLayout()
            for title, action in buttons:
                button = QPushButton(title)
                button.setObjectName('backButton')
                button.clicked.connect(lambda checked=False, a=action: self.academic_action(a))
                panel.addWidget(button)
            page.layout().insertLayout(1, panel)

    def academic_action(self, action):
        record = self._selected_entity()
        if action == 'class_offering':
            page = self.pages.currentWidget()
            if not isinstance(page, ReportPage):
                return
            value = page.selector.currentData()
            if value is not None:
                self.open_link('offering_id', value)
            return
        if not record:
            QMessageBox.information(self, 'Select a record', 'Select a row first.')
            return
        if action == 'subject_offerings':
            self.navigate_related('Class Offerings', 'subject_id', record.get('subject_id'),
                                  f"SUBJECT {record.get('subject_code', '')}")
        elif action == 'teacher_offerings':
            self.navigate_related('Class Offerings', 'teacher_id', record.get('teacher_id'),
                                  f"TEACHER {record.get('teacher_id', '')}")
        elif action == 'offering_subject':
            self.open_link('subject_id', record.get('subject_id'))
        elif action == 'offering_teacher':
            self.open_link('teacher_id', record.get('teacher_id'))
        elif action == 'offering_class_list':
            self.navigate_related('Class Offerings', 'offering_id', record.get('offering_id'),
                                  f"CLASS {record.get('class_code', '')}")

    def navigate_related(self, name, field, value, label=''):
        if value is None or str(value).strip() == '':
            QMessageBox.information(self, 'Missing link', 'No related record is assigned.')
            return False
        index = self._academic_index(name)
        if index < 0:
            return False
        target = (field, str(value))
        if index == self.pages.currentIndex() and self.context_filters.get(index) == target:
            return True
        self.history.append(self._snapshot())
        self.forward_history.clear()
        self._show_page(index, filter_spec=target, label=label or f'{field}: {value}')
        self.set_status(f'{name} filtered by {field}: {value}')
        return True

    def _apply_context_filter(self, index):
        page = self.pages.widget(index)
        spec = self.context_filters.get(index)
        if isinstance(page, ClassOfferingsPage):
            if spec:
                field, value = spec
                if field == 'offering_id': page.select_offering(value)
                elif field == 'teacher_id': page.select_teacher(value)
                elif field == 'subject_id': page.select_subject(value)
            return
        if not isinstance(page, EntityPage):
            return
        # Teachers' existing live search remains intact. Use the original records,
        # then apply context filtering only to the visible table.
        if page.name == 'Teachers':
            page.filter_teachers()
        if not spec:
            return
        field, value = spec
        if page.name == 'Teachers':
            records = page.filtered_records
        else:
            records = page.records
        from .academic_pages import populate
        matching = [r for r in records if str(r.get(field, '')) == value]
        fields = page.table.property('id_fields') or (list(records[0]) if records else [])
        populate(page.table, matching, fields)
        page.table.setProperty('id_fields', fields)
        if page.name == 'Teachers':
            page.filtered_records = matching
        page.info.setText(f'{len(matching)} matching record(s) — {field}: {value}')

    def clear_current_filter(self):
        index = self.pages.currentIndex()
        if index not in self.context_filters:
            return
        self.history.append(self._snapshot())
        self.forward_history.clear()
        self.context_filters.pop(index, None)
        self.context_labels.pop(index, None)
        self._show_page(index)

    def open_link(self, field, value):
        destinations = {
            'student_id': 'Students', 'teacher_id': 'Teachers',
            'subject_id': 'Subjects', 'offering_id': 'Class Offerings',
            'enrollment_id': 'Enrollments', 'period_id': 'Grading Configuration',
            'grading_period_id': 'Grading Configuration',
            'component_id': 'Grading Configuration', 'percentage_id': 'Grading Configuration',
        }
        name = destinations.get(field)
        if not name or value is None or str(value).strip() == '':
            return False
        index = self._academic_index(name)
        if index < 0:
            return False
        if name in ('Teachers', 'Subjects', 'Class Offerings'):
            return self.navigate_related(name, field, value, f'{field}: {value}')
        previous = self._snapshot()
        self._show_page(index)
        current_page = self.pages.currentWidget()
        if isinstance(current_page, GradingConfigurationPage):
            editor_name = {
                'period_id': 'Grading Periods',
                'grading_period_id': 'Grading Periods',
                'component_id': 'Grade Components',
                'percentage_id': 'Grade Weights',
            }.get(field)
            if editor_name:
                editor = current_page.open_editor(editor_name)
                table = editor.table
            else:
                return False
        else:
            table = getattr(current_page, 'table', None)
        if table is None:
            return False
        fields = table.property('id_fields') or []
        col = next((i for i, key in enumerate(fields) if key == field), -1)
        if col < 0:
            col = 0
        for row in range(table.rowCount()):
            item = table.item(row, col)
            if item and item.text() == str(value):
                self.history.append(previous)
                self.forward_history.clear()
                table.selectRow(row)
                table.scrollToItem(item)
                return True
        self._show_page(*previous)
        QMessageBox.information(self, 'Record not found', f'No matching {name} record: {value}')
        return True

    def current_record_id(self):
        page = self.pages.currentWidget()
        table = getattr(page, 'table', None)
        if table is None or table.currentRow() < 0:
            return None
        if not isinstance(page, (StudentsPage, EntityPage)):
            return None
        item = table.item(table.currentRow(), 0)
        return item.text() if item else None

    def restore_record(self, value):
        if value is None:
            return
        table = getattr(self.pages.currentWidget(), 'table', None)
        if table is None:
            return
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and item.text() == str(value):
                table.selectRow(row)
                table.scrollToItem(item)
                break

    def go_back(self):
        if not self.history:
            return
        target = self.history.pop()
        self.forward_history.append(self._snapshot())
        self._show_page(*target)

    def go_forward(self):
        if not self.forward_history:
            return
        target = self.forward_history.pop()
        self.history.append(self._snapshot())
        self._show_page(*target)

    def navigate(self, index, remember=True):
        if not (0 <= index < self.pages.count()):
            return
        previous = self.pages.currentIndex()
        if index == previous and self._navigation_ready:
            self._update_navigation_controls()
            return
        if remember and self._navigation_ready and previous != index:
            self.history.append(self._snapshot())
            self.forward_history.clear()
        self._show_page(index, filter_spec=self.context_filters.get(index),
                        label=self.context_labels.get(index, ''))


def launch():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.retro_shadows = RetroControlShadows(app)
    app.installEventFilter(app.retro_shadows)
    app.setFont(QFont('Segoe UI', 10))
    font_path = BASE.parent / 'assets' / 'fonts' / 'Minecraftia-Regular.ttf'
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    stylesheet = (BASE / 'styles.qss').read_text(encoding='utf-8')
    app.setStyleSheet(stylesheet.replace('Minecraftia', 'Segoe UI'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
