"""Pure GUI table styling: no database queries or changes."""
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHeaderView, QStyledItemDelegate, QAbstractItemView

PALETTE = [
    '#ffcf65',  # golden yellow
    '#bde96b',  # lime
    '#8ee2dc',  # turquoise
    '#d4b8f3',  # lavender
    '#f8a5ca',  # pink
    '#f8e3aa',  # cream
    '#a9d9ed',  # sky blue
    '#e6d5f3',
]

class ColorfulRetroHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setMinimumHeight(46)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSectionsClickable(False)
        self.setStretchLastSection(True)

    def paintSection(self, painter, rect, logical_index):
        if not rect.isValid():
            return
        painter.save()
        painter.fillRect(rect, QColor(PALETTE[logical_index % len(PALETTE)]))
        painter.setPen(QPen(QColor('#241f1b'), 2))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        title = str(self.model().headerData(logical_index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or '')
        font = QFont('Haettenschweiler', 10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor('#171b19'))
        painter.drawText(rect.adjusted(6, 3, -6, -3), Qt.AlignmentFlag.AlignCenter, title)
        painter.restore()

class LinkedIdDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        heading = str(index.model().headerData(index.column(), Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or '')
        field = heading.strip().lower().replace(' ', '_')
        text = str(index.data() or '')
        # Only ID fields get the link treatment. Avoid changing numeric grades or names.
        if field.endswith('_id') and text:
            option.font = QFont('Haettenschweiler', 11)
            option.font.setUnderline(True)
            if not (option.state & __import__('PySide6.QtWidgets', fromlist=['QStyle']).QStyle.StateFlag.State_Selected):
                option.palette.setColor(option.palette.ColorRole.Text, QColor('#075b88'))
            option.backgroundBrush = QColor('#e3f5fa' if index.row() % 2 == 0 else '#d6edf4')

def install_retro_table_style(table):
    if table.property('studentdb_retro_table_installed'):
        return
    table.setProperty('studentdb_retro_table_installed', True)
    table.setHorizontalHeader(ColorfulRetroHeader(table))
    table.setItemDelegate(LinkedIdDelegate(table))
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setShowGrid(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.verticalHeader().setDefaultSectionSize(39)
    table.horizontalHeader().setMinimumSectionSize(95)
    # Stretch columns across the full available width; preserve minimum ID widths.
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setMinimumSectionSize(125)
    table.setFont(QFont('Haettenschweiler', 11))
    # Readable ID columns: full UUID remains available without clipping where possible.
    for col in range(table.columnCount()):
        heading = table.horizontalHeaderItem(col)
        if heading and heading.text().lower().replace(' ', '_').endswith('_id'):
            table.horizontalHeader().setMinimumSectionSize(150)
    table.setToolTip('Double-click a highlighted ID to open its linked record, where supported.')
