"""Retro StudentDB PySide6 GUI. No Flask files or database schema are changed."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView
)
from . import repository
from .academic_pages import EntityPage, ScoresPage, GradesPage

BASE = Path(__file__).resolve().parent
NAV_ITEMS = [
    ('▦', 'Dashboard'), ('▣', 'Students'), ('▤', 'Teachers'),
    ('▧', 'Subjects'), ('▥', 'Class Offerings'), ('▨', 'Enrollments'),
    ('▣', 'Grading Periods'), ('▤', 'Grade Components'),
    ('▥', 'Score Encoding'), ('▦', 'Grades & Transcripts'),
    ('▧', 'Overall Grades'), ('▥', 'Grade Weights')
]


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
        save.setObjectName('primaryButton')
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
        tools.addWidget(refresh)
        add = QPushButton('+ Add Student')
        add.setObjectName('primaryButton')
        add.clicked.connect(self.add_record)
        tools.addWidget(add)
        root.addLayout(tools)
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.edit_record)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.count_label = QLabel('0 student records')
        actions.addWidget(self.count_label)
        actions.addStretch()
        edit = QPushButton('✎ Edit Selected')
        edit.clicked.connect(self.edit_record)
        actions.addWidget(edit)
        delete = QPushButton('✕ Delete Selected')
        delete.setObjectName('dangerButton')
        delete.clicked.connect(self.delete_record)
        actions.addWidget(delete)
        root.addLayout(actions)
        self.refresh()

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
            QMessageBox.critical(self, 'PostgreSQL Error', str(exc))
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
                QMessageBox.critical(self, 'Save Failed', str(exc))

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
                QMessageBox.critical(self, 'Update Failed', str(exc))

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
                QMessageBox.critical(self, 'Delete Failed', str(exc))


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
    def __init__(self, navigate_callback=None):
        super().__init__()
        self.navigate_callback = navigate_callback
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.addWidget(section_header('SYSTEM DASHBOARD', 'StudentDB / Academic Control Center'))
        stats = QGridLayout()
        self.stat_labels = {}
        for i, (name, table) in enumerate([('STUDENTS', 'student'), ('TEACHERS', 'teacher'),
                                           ('SUBJECTS', 'subject'), ('ENROLLMENTS', 'enrollment')]):
            card = QFrame()
            card.setObjectName('panel')
            content = QVBoxLayout(card)
            heading = QLabel(name)
            heading.setObjectName('subtitle')
            content.addWidget(heading)
            number = QLabel('—')
            number.setObjectName('statLabel')
            content.addWidget(number)
            stats.addWidget(card, i // 2, i % 2)
            self.stat_labels[table] = number
        root.addLayout(stats)
        quick = QFrame()
        quick.setObjectName('panel')
        quick_layout = QVBoxLayout(quick)
        quick_layout.addWidget(QLabel('QUICK ACCESS'))
        buttons = QHBoxLayout()
        for name, index in [('Students', 1), ('Teachers', 2), ('Subjects', 3),
                            ('Class Offerings', 4), ('Enrollments', 5)]:
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, idx=index: self.open_page(idx))
            buttons.addWidget(button)
        quick_layout.addLayout(buttons)
        root.addWidget(quick)
        preview = QFrame()
        preview.setObjectName('panel')
        preview_layout = QVBoxLayout(preview)
        preview_layout.addWidget(QLabel('STUDENT DIRECTORY / PREVIEW'))
        self.recent_table = QTableWidget(0, 4)
        self.recent_table.setHorizontalHeaderLabels(['Student ID', 'First Name', 'Last Name', 'Program'])
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.verticalHeader().setVisible(False)
        preview_layout.addWidget(self.recent_table)
        root.addWidget(preview, 1)
        self.connection_label = QLabel('DATABASE STATUS: Not checked')
        root.addWidget(self.connection_label)

    def open_page(self, index):
        if self.navigate_callback:
            self.navigate_callback(index)

    def refresh(self):
        from db import get_db
        try:
            with get_db() as conn, conn.cursor() as cur:
                for table, label in self.stat_labels.items():
                    cur.execute(f'SELECT COUNT(*) AS total FROM {table}')
                    label.setText(str(cur.fetchone()['total']))
                cur.execute('SELECT student_id, first_name, last_name, program FROM student ORDER BY student_id DESC LIMIT 8')
                students = cur.fetchall()
                self.recent_table.setRowCount(len(students))
                for i, student in enumerate(students):
                    for j, key in enumerate(('student_id', 'first_name', 'last_name', 'program')):
                        self.recent_table.setItem(i, j, QTableWidgetItem(str(student.get(key) or '')))
                cur.execute('SELECT current_database() AS db, inet_server_port() AS port')
                info = cur.fetchone()
                self.connection_label.setText(f"DATABASE STATUS: CONNECTED | {info['db']} | Port {info['port']}")
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
        self.setWindowTitle('StudentDB Retro OS — Desktop Edition')
        self.resize(1200, 760)
        self.setMinimumSize(920, 600)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        banner = QLabel('▣  STUDENTDB RETRO OS                                      STUDENT INFORMATION & GRADING SYSTEM')
        banner.setObjectName('banner')
        outer.addWidget(banner)
        middle = QHBoxLayout()
        middle.setContentsMargins(12, 12, 12, 12)
        middle.setSpacing(12)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(225)
        side = QVBoxLayout(sidebar)
        side.addWidget(QLabel('◈  MAIN MENU'))
        self.nav_buttons = []
        self.pages = QStackedWidget()
        self.dashboard = DashboardPage(self.navigate)
        self.students = StudentsPage(self.set_status)
        for index, (symbol, name) in enumerate(NAV_ITEMS):
            button = QPushButton(f'{symbol}   {name}')
            button.setObjectName('navButton')
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=index: self.navigate(idx))
            side.addWidget(button)
            self.nav_buttons.append(button)
            if index == 0:
                page = self.dashboard
            elif index == 1:
                page = self.students
            elif name == 'Score Encoding':
                page = ScoresPage(self.set_status)
            elif name == 'Grades & Transcripts':
                page = GradesPage()
            elif name == 'Overall Grades':
                page = GradesPage(overall=True)
            else:
                page = EntityPage(name, self.set_status)
            self.pages.addWidget(page)
        side.addStretch()
        side.addWidget(QLabel('SYSTEM  ▪  LOCAL DESKTOP'))
        middle.addWidget(sidebar)
        content = QFrame()
        content.setObjectName('content')
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(self.pages)
        middle.addWidget(content, 1)
        outer.addLayout(middle, 1)
        self.footer = QLabel('  READY  |  PostgreSQL: existing connection  |  StudentDB Desktop v1')
        self.footer.setObjectName('footer')
        outer.addWidget(self.footer)
        self.navigate(0)

    def set_status(self, message):
        if not hasattr(self, 'footer'):
            return
        self.footer.setText(f'  {message}  |  StudentDB Desktop v1')

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        if index == 0:
            self.dashboard.refresh()
        elif index == 1:
            self.students.refresh()
        else:
            self.pages.currentWidget().refresh()


def launch():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Consolas', 10))
    font_path = BASE.parent / 'assets' / 'fonts' / 'Minecraftia-Regular.ttf'
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    stylesheet = (BASE / 'styles.qss').read_text(encoding='utf-8')
    app.setStyleSheet(stylesheet.replace('Minecraftia', 'Consolas'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
