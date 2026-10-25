"""Read-only Audit History page for the StudentDB PySide6 desktop app."""
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QDialog, QTextEdit, QMessageBox
)
from . import audit_repository


def pretty_json(value):
    if value is None:
        return '(none)'
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return value
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


class AuditHistoryPage(QWidget):
    def __init__(self, status_callback=None):
        super().__init__()
        self.status_callback = status_callback
        self.records = []
        layout = QVBoxLayout(self)
        heading = QLabel('AUDIT HISTORY')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        layout.addWidget(QLabel('Read-only history of database INSERT, UPDATE and DELETE operations.'))

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search record ID, table, action or audit ID...')
        self.search.returnPressed.connect(self.refresh)
        controls.addWidget(self.search, 3)
        self.table_filter = QComboBox()
        self.table_filter.addItem('All tables', '')
        controls.addWidget(self.table_filter, 1)
        self.action_filter = QComboBox()
        for label, value in [('All actions', ''), ('INSERT', 'INSERT'),
                             ('UPDATE', 'UPDATE'), ('DELETE', 'DELETE')]:
            self.action_filter.addItem(label, value)
        controls.addWidget(self.action_filter, 1)
        refresh = QPushButton('↻ Refresh')
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Audit ID', 'Timestamp', 'Table', 'Action', 'Record ID'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.show_details)
        layout.addWidget(self.table)

        footer = QHBoxLayout()
        self.count_label = QLabel('Ready')
        footer.addWidget(self.count_label)
        footer.addStretch()
        details = QPushButton('View Before / After')
        details.setObjectName('primaryButton')
        details.clicked.connect(self.show_details)
        footer.addWidget(details)
        layout.addLayout(footer)
        self.table_filter.currentIndexChanged.connect(self.refresh)
        self.action_filter.currentIndexChanged.connect(self.refresh)
        # Defer querying until the user opens this page or presses Refresh.

    def refresh(self, *_):
        try:
            selected = self.table_filter.currentData() or ''
            names = audit_repository.audit_tables()
            self.table_filter.blockSignals(True)
            self.table_filter.clear()
            self.table_filter.addItem('All tables', '')
            for name in names:
                self.table_filter.addItem(name, name)
            index = self.table_filter.findData(selected)
            self.table_filter.setCurrentIndex(index if index >= 0 else 0)
            self.table_filter.blockSignals(False)
            self.records = audit_repository.audit_rows(
                self.search.text(), self.table_filter.currentData() or '',
                self.action_filter.currentData() or '')
            self.table.setRowCount(len(self.records))
            for row_idx, record in enumerate(self.records):
                values = (record['audit_id'], record['changed_at'],
                          record['table_name'], record['action'], record['record_id'])
                for col_idx, value in enumerate(values):
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value or '')))
            self.table.resizeColumnsToContents()
            self.count_label.setText(f'{len(self.records)} audit record(s) shown (maximum 500)')
            if self.status_callback:
                self.status_callback(f'Loaded {len(self.records)} audit events')
        except Exception as exc:
            QMessageBox.critical(self, 'Audit history error', str(exc))

    def show_details(self, *_):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            QMessageBox.information(
                self, 'Audit History', 'Select an audit record first.'
            )
            return

        record = self.records[row]

        dialog = QDialog(self)
        dialog.setWindowTitle(
            f"Audit #{record['audit_id']} — {record['action']}"
        )
        dialog.resize(820, 620)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(
            f"Table: {record['table_name']} | Record: {record['record_id']}\n"
            f"Action: {record['action']} | Timestamp: {record['changed_at']}"
        ))

        halves = QHBoxLayout()

        audit_text_style = """
            QTextEdit {
                background-color: #FFF8E7;
                color: #28211C;
                border: 3px solid #28211C;
                padding: 10px;
                font-family: Consolas;
                font-size: 12px;
                selection-background-color: #247D80;
                selection-color: #FFFFFF;
            }
        """

        for title, value in [
            ('BEFORE', record['old_data']),
            ('AFTER', record['new_data'])
        ]:
            side = QVBoxLayout()

            label = QLabel(title)
            side.addWidget(label)

            editor = QTextEdit()
            editor.setReadOnly(True)
            editor.setPlainText(pretty_json(value))

            editor.setStyleSheet("""
                QTextEdit {
                    background-color: #FFF8E7;
                    color: #28211C;
                    border: 3px solid #28211C;
                    padding: 10px;
                    font-family: Consolas;
                    font-size: 12px;
                    selection-background-color: #247D80;
                    selection-color: #FFFFFF;
                }
            """)

            side.addWidget(editor)
            halves.addLayout(side)

        layout.addLayout(halves)

        close = QPushButton('Close')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)

        dialog.exec()