"""Retro StudentDB PySide6 GUI. No Flask files or database schema are changed."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QFont, QFontDatabase, QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QGraphicsDropShadowEffect
)
from . import repository
from .retro_tables import install_retro_table_style
from .academic_pages import EntityPage, ScoresPage, GradesPage, show_error
from .report_pages import ReportPage

class RetroControlShadows(QObject):
    """Apply crisp arcade-style shadows to buttons and combo boxes, including dialogs."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Polish and isinstance(watched, (QPushButton, QComboBox)):
            if watched.graphicsEffect() is None:
                shadow = QGraphicsDropShadowEffect(watched)
                shadow.setBlurRadius(0)
                shadow.setOffset(3, 3)
                shadow.setColor(QColor('#241f1b'))
                watched.setGraphicsEffect(shadow)
        return super().eventFilter(watched, event)


BASE = Path(__file__).resolve().parent
NAV_ITEMS = [
    ('▦', 'Dashboard'), ('▣', 'Students'), ('▤', 'Teachers'),
    ('▧', 'Subjects'), ('▥', 'Class Offerings'), ('▨', 'Enrollments'),
    ('▣', 'Grading Periods'), ('▤', 'Grade Components'),
    ('▥', 'Grade Weights'), ('▥', 'Score Encoding'),
    ('▦', 'Grades & Transcripts'), ('▧', 'Overall Grades'),('▤', 'Class List'),
    ('▥', 'Class Grade Sheet'), ('▦', 'Student Grade Report'),
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(False)
        self.table.cellDoubleClicked.connect(self.on_double_click)
        self.table.setColumnWidth(0, 135)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(5, 110)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.count_label = QLabel('0 student records')
        actions.addWidget(self.count_label)
        actions.addStretch()
        edit = QPushButton('✎ Edit Selected')
        edit.setObjectName('editButton')
        edit.clicked.connect(self.edit_record)
        actions.addWidget(edit)
        delete = QPushButton('✕ Delete Selected')
        delete.setObjectName('dangerButton')
        delete.clicked.connect(self.delete_record)
        actions.addWidget(delete)
        root.addLayout(actions)
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
        self.recent_table = QTableWidget(0, 6)
        self.recent_table.setHorizontalHeaderLabels(['Student ID', 'First Name', 'Last Name', 'Program', 'Year Level', 'Status'])
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setColumnWidth(0, 125)
        self.recent_table.setColumnWidth(3, 120)
        self.recent_table.setColumnWidth(4, 100)
        self.recent_table.verticalHeader().setVisible(False)
        preview_layout.addWidget(self.recent_table)
        root.addWidget(preview, 1)
        self.connection_label = QLabel('DATABASE STATUS: Not checked')
        self.connection_label.setObjectName('connectionStatus')
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
                cur.execute('SELECT student_id, first_name, last_name, program, year_level, status FROM student ORDER BY student_id DESC LIMIT 8')
                students = cur.fetchall()
                self.recent_table.setRowCount(len(students))
                for i, student in enumerate(students):
                    for j, key in enumerate(('student_id', 'first_name', 'last_name', 'program', 'year_level', 'status')):
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
        side.setSpacing(4)
        side.addWidget(QLabel('◈  MAIN MENU'))
        self.nav_buttons = []
        self.pages = QStackedWidget()
        self.history = []
        self.students_navigation_hint = 'Double-click an ID to open its source record'
        self.dashboard = DashboardPage(self.navigate)
        self.students = StudentsPage(self.set_status)
        for index, (symbol, name) in enumerate(NAV_ITEMS):
            button = QPushButton(f'{symbol}   {name}')
            button.setObjectName('navButton')
            shadow = QGraphicsDropShadowEffect(button)
            shadow.setBlurRadius(0)
            shadow.setOffset(4, 4)
            shadow.setColor(QColor('#28211c'))
            button.setGraphicsEffect(shadow)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=index: self.navigate(idx))
            side.addWidget(button)
            self.nav_buttons.append(button)
            if index == 0:
                page = self.dashboard
            elif name == 'Students':
                page = self.students
            elif name == 'Score Encoding':
                page = ScoresPage(self.set_status)
            elif name == 'Grades & Transcripts':
                page = GradesPage()
            elif name == 'Overall Grades':
                page = GradesPage(overall=True)
            elif name == 'Class List':
                page = ReportPage('class_list', self.set_status)
            elif name == 'Class Grade Sheet':
                page = ReportPage('grade_sheet', self.set_status)
            elif name == 'Student Grade Report':
                page = ReportPage('student_report', self.set_status)
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
        side.addStretch()
        side.addWidget(QLabel('SYSTEM  ▪  LOCAL DESKTOP'))
        middle.addWidget(sidebar)
        content = QFrame()
        content.setObjectName('content')
        content_layout = QVBoxLayout(content)
        back_bar = QHBoxLayout()
        self.back_button = QPushButton('← BACK TO PREVIOUS RECORD')
        self.back_button.setObjectName('backButton')
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        back_bar.addWidget(self.back_button)
        back_bar.addStretch()
        content_layout.addLayout(back_bar)
        content_layout.addWidget(self.pages)
        middle.addWidget(content, 1)
        outer.addLayout(middle, 1)
        self.footer = QLabel('  READY  |  PostgreSQL: existing connection  |  StudentDB Desktop v1')
        self.footer.setObjectName('footer')
        outer.addWidget(self.footer)
        self.navigate(0, remember=False)

    def set_status(self, message):
        if not hasattr(self, 'footer'):
            return
        self.footer.setText(f'  {message}  |  StudentDB Desktop v1')

    def handle_table_double_click(self, page, row, column):
        table = page.table
        header = table.horizontalHeaderItem(column)
        cell = table.item(row, column)
        if not header or not cell:
            return
        fields = table.property('id_fields')
        field = fields[column] if fields and column < len(fields) else header.text().lower().replace(' ', '_')
        if field.endswith('_id') and self.open_link(field, cell.text()):
            return
        if isinstance(page, EntityPage):
            page.edit_record()

    def open_link(self, field, value):
        """Open the source record and remember where the user came from."""
        destinations = {
            'student_id': 'Students', 'teacher_id': 'Teachers',
            'subject_id': 'Subjects', 'offering_id': 'Class Offerings',
            'enrollment_id': 'Enrollments', 'period_id': 'Grading Periods',
            'grading_period_id': 'Grading Periods',
            'component_id': 'Grade Components',
            'percentage_id': 'Grade Weights',
        }
        name = destinations.get(field)
        if not name or not value:
            return False
        index = next((i for i, (_, label) in enumerate(NAV_ITEMS) if label == name), None)
        if index is None:
            return False

        previous_index = self.pages.currentIndex()
        previous_record = self.current_record_id()
        self.navigate(index, remember=False)
        page = self.pages.currentWidget()
        table = getattr(page, 'table', None)
        if table is None:
            return True
        fields = table.property('id_fields')
        target_column = next((c for c in range(table.columnCount())
                              if (fields[c] if fields and c < len(fields) else
                                  table.horizontalHeaderItem(c).text().lower().replace(' ', '_')) == field), -1)
        match = -1
        if target_column >= 0:
            for r in range(table.rowCount()):
                item = table.item(r, target_column)
                if item and item.text() == str(value):
                    match = r
                    break
        if match < 0:
            QMessageBox.information(self, 'Record not found',
                f'{name} record {value} was not found in the loaded table.\n'
                'It may have been deleted or may be outside the current result limit.')
            self.navigate(previous_index, remember=False)
            self.restore_record(previous_record)
            return True
        if previous_index != index:
            self.history.append((previous_index, previous_record))
        self.back_button.setEnabled(bool(self.history))
        table.selectRow(match)
        table.scrollToItem(table.item(match, target_column))
        self.set_status(f'Opened {name}: {value}')
        return True

    def current_record_id(self):
        page = self.pages.currentWidget()
        table = getattr(page, 'table', None)
        if table is None or table.currentRow() < 0:
            return None
        # Record identity is the first column on Students and CRUD entity pages.
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
        index, record_id = self.history.pop()
        self.navigate(index, remember=False)
        self.restore_record(record_id)
        self.back_button.setEnabled(bool(self.history))

    def navigate(self, index, remember=True):
        if index < 0 or index >= self.pages.count():
            return
        previous_index = self.pages.currentIndex()
        if remember and previous_index != index:
            self.history.append((previous_index, self.current_record_id()))
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.back_button.setEnabled(bool(self.history))
        if index == 0:
            self.dashboard.refresh()
        elif self.pages.currentWidget() is self.students:
            self.students.refresh()
        else:
            self.pages.currentWidget().refresh()


def launch():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.retro_shadows = RetroControlShadows(app)
    app.installEventFilter(app.retro_shadows)
    app.setFont(QFont('Consolas', 11))
    font_path = BASE.parent / 'assets' / 'fonts' / 'Minecraftia-Regular.ttf'
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    stylesheet = (BASE / 'styles.qss').read_text(encoding='utf-8')
    app.setStyleSheet(stylesheet.replace('Minecraftia', 'Consolas'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
