from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QColor, QPainter, QTextCursor, QBrush
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QListWidget,
    QTextEdit,
    QPlainTextEdit,
    QLabel,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QListWidgetItem,
    QInputDialog,
    QMenu,
    QAbstractItemView,
    QDialog,
    QGridLayout,
)

from models.scenario import Scenario
from models.block import ScriptBlock
from models.note import Note
from models.template import ScenarioTemplate, TemplateBlock
from services.duration_calculator import DurationCalculator
from services.file_storage import FileStorage
from services.pdf_exporter import PdfExporter


class DraggableBlockList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.after_drop_callback = None

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def dropEvent(self, event):
        super().dropEvent(event)

        if self.after_drop_callback is not None:
            self.after_drop_callback()


class NoteMarkerArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(self.editor.marker_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_marker_area(event)

    def mousePressEvent(self, event):
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        self.editor.handle_marker_area_click(position)


class LineNoteEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.marker_area = NoteMarkerArea(self)

        self.notes_provider = lambda: []
        self.request_add_note_callback = None
        self.note_marker_clicked_callback = None

        self.setViewportMargins(self.marker_area_width(), 0, 0, 0)

        self.updateRequest.connect(self.update_marker_area)
        self.blockCountChanged.connect(self.update_marker_area_width)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_editor_context_menu)

    def marker_area_width(self):
        return 48

    def update_marker_area_width(self):
        self.setViewportMargins(self.marker_area_width(), 0, 0, 0)

    def update_marker_area(self, rect, dy):
        if dy:
            self.marker_area.scroll(0, dy)
        else:
            self.marker_area.update(0, rect.y(), self.marker_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_marker_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        content_rect = self.contentsRect()
        self.marker_area.setGeometry(
            QRect(
                content_rect.left(),
                content_rect.top(),
                self.marker_area_width(),
                content_rect.height(),
            )
        )

    def refresh_note_markers(self):
        self.marker_area.update()

    def get_notes_by_line(self):
        notes_by_line = {}

        for note in self.notes_provider():
            notes_by_line.setdefault(note.line_index, []).append(note)

        return notes_by_line

    def visible_blocks(self):
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()

        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        viewport_bottom = self.viewport().rect().bottom()

        while block.isValid() and top <= viewport_bottom:
            if block.isVisible() and bottom >= 0:
                yield block_number, int(top), int(bottom)

            block = block.next()
            block_number += 1
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()

    def marker_rects_for_line(self, line_index: int, top: int, bottom: int):
        notes_by_line = self.get_notes_by_line()
        notes = notes_by_line.get(line_index, [])

        square_size = 10
        gap = 4
        y = top + max(0, (bottom - top - square_size) // 2)

        rects = []

        for index, note in enumerate(notes[:3]):
            x = 6 + index * (square_size + gap)
            rect = QRect(x, y, square_size, square_size)
            rects.append((rect, note))

        return rects

    def paint_marker_area(self, event):
        painter = QPainter(self.marker_area)
        painter.fillRect(event.rect(), QColor("#F3F3F3"))

        for line_index, top, bottom in self.visible_blocks():
            rects = self.marker_rects_for_line(line_index, top, bottom)

            for rect, note in rects:
                color = QColor(note.color)

                if not color.isValid():
                    color = QColor("#FFD966")

                painter.fillRect(rect, color)
                painter.setPen(QColor("#555555"))
                painter.drawRect(rect)

    def handle_marker_area_click(self, position):
        for line_index, top, bottom in self.visible_blocks():
            rects = self.marker_rects_for_line(line_index, top, bottom)

            for rect, note in rects:
                if rect.contains(position):
                    if self.note_marker_clicked_callback is not None:
                        self.note_marker_clicked_callback(note.id)
                    return

    def show_editor_context_menu(self, position):
        cursor = self.cursorForPosition(position)
        line_index = cursor.blockNumber()

        notes_on_line = [
            note for note in self.notes_provider()
            if note.line_index == line_index
        ]

        menu = QMenu(self)

        cut_action = menu.addAction("Вырезать")
        copy_action = menu.addAction("Копировать")
        paste_action = menu.addAction("Вставить")
        select_all_action = menu.addAction("Выделить всё")

        menu.addSeparator()

        if len(notes_on_line) >= 3:
            add_note_action = menu.addAction("Лимит заметок достигнут")
            add_note_action.setEnabled(False)
        else:
            add_note_action = menu.addAction("Добавить заметку")

        selected_action = menu.exec(self.mapToGlobal(position))

        if selected_action == cut_action:
            self.cut()
        elif selected_action == copy_action:
            self.copy()
        elif selected_action == paste_action:
            self.paste()
        elif selected_action == select_all_action:
            self.selectAll()
        elif selected_action == add_note_action and len(notes_on_line) < 3:
            if self.request_add_note_callback is not None:
                self.request_add_note_callback(line_index)

class ColorPickerDialog(QDialog):
    def __init__(
        self,
        current_color: str = "#FFD966",
        parent=None,
        window_title: str = "Выбор цвета",
    ):
        super().__init__(parent)

        self.setWindowTitle(window_title)
        self.selected_color = current_color

        main_layout = QVBoxLayout()
        grid_layout = QGridLayout()

        self.color_label = QLabel(f"Выбранный цвет: {self.selected_color}")

        colors = [
            ("Жёлтый", "#FFD966"),
            ("Зелёный", "#B6D7A8"),
            ("Голубой", "#9FC5E8"),
            ("Синий", "#6FA8DC"),
            ("Фиолетовый", "#B4A7D6"),
            ("Розовый", "#F4CCCC"),
            ("Красный", "#E06666"),
            ("Оранжевый", "#F6B26B"),
            ("Серый", "#D9D9D9"),
        ]

        for index, (name, color) in enumerate(colors):
            button = QPushButton(name)
            button.setStyleSheet(
                f"background-color: {color}; color: black; padding: 8px;"
            )
            button.clicked.connect(
                lambda checked=False, selected=color: self.select_color(selected)
            )

            row = index // 3
            column = index % 3
            grid_layout.addWidget(button, row, column)

        buttons_layout = QHBoxLayout()

        self.confirm_button = QPushButton("Выбрать")
        self.confirm_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.confirm_button)
        buttons_layout.addWidget(self.cancel_button)

        main_layout.addWidget(self.color_label)
        main_layout.addLayout(grid_layout)
        main_layout.addLayout(buttons_layout)

        self.setLayout(main_layout)

    def select_color(self, color: str):
        self.selected_color = color
        self.color_label.setText(f"Выбранный цвет: {self.selected_color}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Редактор сценариев видеоконтента")
        self.resize(1250, 720)

        self.scenario = Scenario(title="Новый сценарий")
        self.current_template = None

        self.current_block_id = None
        self.selected_note_id = None
        self.next_block_id = 1

        self.setup_ui()
        self.update_duration_label()
        self.set_note_panel_enabled(False)

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        center_layout = QVBoxLayout()
        note_layout = QVBoxLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Название сценария")
        self.title_input.setText(self.scenario.title)
        self.title_input.textChanged.connect(self.update_scenario_title)

        self.blocks_list = DraggableBlockList()
        self.blocks_list.currentItemChanged.connect(self.select_block)
        self.blocks_list.after_drop_callback = self.sync_blocks_order_from_list

        self.blocks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.blocks_list.customContextMenuRequested.connect(self.show_block_context_menu)

        self.add_block_button = QPushButton("Добавить блок")
        self.add_block_button.clicked.connect(self.add_block)

        self.delete_block_button = QPushButton("Удалить блок")
        self.delete_block_button.clicked.connect(self.delete_block)

        self.save_button = QPushButton("Сохранить сценарий")
        self.save_button.clicked.connect(self.save_scenario)

        self.load_button = QPushButton("Открыть сценарий")
        self.load_button.clicked.connect(self.load_scenario)

        self.export_pdf_button = QPushButton("Экспорт в PDF")
        self.export_pdf_button.clicked.connect(self.export_scenario_to_pdf)

        self.save_template_button = QPushButton("Сохранить как шаблон")
        self.save_template_button.clicked.connect(self.save_current_as_template)

        self.import_template_button = QPushButton("Импорт шаблона")
        self.import_template_button.clicked.connect(self.import_template)

        self.create_from_template_button = QPushButton("Новый сценарий по шаблону")
        self.create_from_template_button.clicked.connect(self.create_scenario_from_template)

        left_layout.addWidget(QLabel("Сценарий"))
        left_layout.addWidget(self.title_input)

        left_layout.addWidget(QLabel("Блоки сценария"))
        left_layout.addWidget(self.blocks_list)

        left_layout.addWidget(self.add_block_button)
        left_layout.addWidget(self.delete_block_button)

        left_layout.addWidget(QLabel("Файлы"))
        left_layout.addWidget(self.save_button)
        left_layout.addWidget(self.load_button)
        left_layout.addWidget(self.export_pdf_button)

        left_layout.addWidget(QLabel("Шаблоны"))
        left_layout.addWidget(self.save_template_button)
        left_layout.addWidget(self.import_template_button)
        left_layout.addWidget(self.create_from_template_button)

        self.block_title_input = QLineEdit()
        self.block_title_input.setPlaceholderText("Название блока")
        self.block_title_input.textChanged.connect(self.update_block_title)

        self.hint_button = QPushButton("?")
        self.hint_button.setFixedSize(28, 28)
        self.hint_button.setToolTip("Подсказка: не задана")
        self.hint_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hint_button.customContextMenuRequested.connect(self.show_hint_context_menu)

        block_title_layout = QHBoxLayout()
        block_title_layout.addWidget(self.block_title_input)
        block_title_layout.addWidget(self.hint_button)

        self.text_editor = LineNoteEditor()
        self.text_editor.setPlaceholderText("Введите текст выбранного блока")
        self.text_editor.textChanged.connect(self.update_block_text)
        self.text_editor.notes_provider = self.get_current_block_notes
        self.text_editor.request_add_note_callback = self.add_note_to_line
        self.text_editor.note_marker_clicked_callback = self.select_note_by_id

        self.duration_label = QLabel("Примерная длительность: 0 мин. 0 сек.")

        center_layout.addWidget(QLabel("Название блока"))
        center_layout.addLayout(block_title_layout)
        center_layout.addWidget(QLabel("Текст блока"))
        center_layout.addWidget(self.text_editor)
        center_layout.addWidget(self.duration_label)

        self.note_panel_title = QLabel("Заметка не выбрана")
        self.note_line_label = QLabel("")

        self.note_text_editor = QTextEdit()
        self.note_text_editor.setPlaceholderText("Текст заметки")
        self.note_text_editor.textChanged.connect(self.update_selected_note_text)

        self.note_color_button = QPushButton("Изменить цвет заметки")
        self.note_color_button.clicked.connect(self.change_selected_note_color)

        self.delete_note_button = QPushButton("Удалить заметку")
        self.delete_note_button.clicked.connect(self.delete_selected_note)

        note_layout.addWidget(QLabel("Панель заметки"))
        note_layout.addWidget(self.note_panel_title)
        note_layout.addWidget(self.note_line_label)
        note_layout.addWidget(self.note_text_editor)
        note_layout.addWidget(self.note_color_button)
        note_layout.addWidget(self.delete_note_button)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(center_layout, 3)
        main_layout.addLayout(note_layout, 1)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def update_scenario_title(self):
        self.scenario.title = self.title_input.text()

    def get_next_default_block_title(self) -> str:
        existing_titles = {block.title for block in self.scenario.blocks}

        number = 1

        while f"Блок {number}" in existing_titles:
            number += 1

        return f"Блок {number}"

    def add_block(self):
        block = ScriptBlock(
            id=self.next_block_id,
            title=self.get_next_default_block_title(),
            order_index=len(self.scenario.blocks),
            text="",
            color="#FFFFFF",
            hint="",
            notes=[],
        )

        self.scenario.blocks.append(block)
        self.next_block_id += 1

        self.refresh_blocks_list()
        self.blocks_list.setCurrentRow(len(self.scenario.blocks) - 1)

    def delete_block(self):
        current_item = self.blocks_list.currentItem()

        if current_item is None:
            return

        block_id = current_item.data(Qt.UserRole)

        self.scenario.blocks = [
            block for block in self.scenario.blocks
            if block.id != block_id
        ]

        self.recalculate_order_indexes()
        self.current_block_id = None
        self.selected_note_id = None

        self.refresh_blocks_list()
        self.clear_editors()
        self.update_duration_label()

    def show_block_context_menu(self, position):
        item = self.blocks_list.itemAt(position)

        if item is None:
            return

        self.blocks_list.setCurrentItem(item)

        menu = QMenu(self)

        duplicate_action = menu.addAction("Дублировать блок")
        change_color_action = menu.addAction("Изменить цвет блока")
        reset_color_action = menu.addAction("Снять цвет блока")

        selected_action = menu.exec(self.blocks_list.mapToGlobal(position))

        block_id = item.data(Qt.UserRole)

        if selected_action == duplicate_action:
            self.duplicate_block_by_id(block_id)
        elif selected_action == change_color_action:
            self.change_block_color_by_id(block_id)
        elif selected_action == reset_color_action:
            self.reset_block_color_by_id(block_id)

    def change_block_color_by_id(self, block_id: int):
        block = self.find_block_by_id(block_id)

        if block is None:
            return

        color = self.choose_color(block.color, "Выбор цвета блока")

        if color is None:
            return

        block.color = color
        self.refresh_blocks_list(keep_current=True)

    def reset_block_color_by_id(self, block_id: int):
        block = self.find_block_by_id(block_id)

        if block is None:
            return

        block.color = "#FFFFFF"
        self.refresh_blocks_list(keep_current=True)

    def duplicate_block_by_id(self, block_id: int):
        source_block = self.find_block_by_id(block_id)

        if source_block is None:
            return

        source_row = None

        for row in range(self.blocks_list.count()):
            item = self.blocks_list.item(row)

            if item.data(Qt.UserRole) == block_id:
                source_row = row
                break

        if source_row is None:
            return

        copied_notes = [
            Note(
                id=note.id,
                text=note.text,
                color=note.color,
                line_index=note.line_index,
            )
            for note in source_block.notes
        ]

        duplicated_block = ScriptBlock(
            id=self.next_block_id,
            title=f"{source_block.title} (копия)",
            order_index=source_row + 1,
            text=source_block.text,
            color=source_block.color,
            hint=source_block.hint,
            notes=copied_notes,
        )

        self.next_block_id += 1

        ordered_blocks = sorted(self.scenario.blocks, key=lambda block: block.order_index)
        ordered_blocks.insert(source_row + 1, duplicated_block)

        self.scenario.blocks = ordered_blocks
        self.recalculate_order_indexes()

        self.refresh_blocks_list()
        self.blocks_list.setCurrentRow(source_row + 1)
        self.update_duration_label()

    def select_block(self, current: QListWidgetItem, previous: QListWidgetItem = None):
        if current is None:
            return

        block_id = current.data(Qt.UserRole)
        block = self.find_block_by_id(block_id)

        if block is None:
            return

        self.current_block_id = block.id
        self.selected_note_id = None

        self.block_title_input.blockSignals(True)
        self.text_editor.blockSignals(True)

        self.block_title_input.setText(block.title)
        self.text_editor.setPlainText(block.text)
        self.update_hint_display(block.hint)

        self.block_title_input.blockSignals(False)
        self.text_editor.blockSignals(False)

        self.normalize_note_line_indexes(block)
        self.text_editor.refresh_note_markers()
        self.set_note_panel_enabled(False)

    def update_block_title(self):
        block = self.get_current_block()

        if block is None:
            return

        block.title = self.block_title_input.text()

        current_item = self.blocks_list.currentItem()
        if current_item is not None:
            current_item.setText(block.title)

    def show_hint_context_menu(self, position):
        block = self.get_current_block()

        if block is None:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Редактировать подсказку")

        selected_action = menu.exec(self.hint_button.mapToGlobal(position))

        if selected_action == edit_action:
            self.edit_current_block_hint()

    def edit_current_block_hint(self):
        block = self.get_current_block()

        if block is None:
            return

        new_hint, ok = QInputDialog.getMultiLineText(
            self,
            "Редактировать подсказку",
            f"Подсказка для блока «{block.title}»:",
            block.hint,
        )

        if not ok:
            return

        block.hint = new_hint
        self.update_hint_display(block.hint)

    def update_hint_display(self, hint: str):
        if hint.strip():
            self.hint_button.setToolTip(f"Подсказка:\n{hint}")
        else:
            self.hint_button.setToolTip("Подсказка: не задана")

    def update_block_text(self):
        block = self.get_current_block()

        if block is None:
            return

        block.text = self.text_editor.toPlainText()
        self.normalize_note_line_indexes(block)
        self.update_duration_label()
        self.text_editor.refresh_note_markers()

    def choose_color(self, current_color: str = "#FFD966", window_title: str = "Выбор цвета"):
        dialog = ColorPickerDialog(
            current_color=current_color,
            parent=self,
            window_title=window_title,
        )

        if dialog.exec() == QDialog.Accepted:
            return dialog.selected_color

        return None

    def add_note_to_line(self, line_index: int):
        block = self.get_current_block()

        if block is None:
            QMessageBox.warning(
                self,
                "Блок не выбран",
                "Сначала выберите блок, к которому нужно добавить заметку.",
            )
            return

        notes_on_line = [
            note for note in block.notes
            if note.line_index == line_index
        ]

        if len(notes_on_line) >= 3:
            QMessageBox.warning(
                self,
                "Лимит заметок",
                "К одному месту текста можно добавить не больше трёх заметок.",
            )
            return

        note_text, ok = QInputDialog.getMultiLineText(
            self,
            "Новая заметка",
            "Введите текст заметки:",
            "",
        )

        if not ok or not note_text.strip():
            return

        color = self.choose_color("#FFD966")

        if color is None:
            return

        next_note_id = self.get_next_note_id(block)

        note = Note(
            id=next_note_id,
            text=note_text.strip(),
            color=color,
            line_index=line_index,
        )

        block.notes.append(note)
        self.text_editor.refresh_note_markers()
        self.select_note_by_id(note.id)

    def get_next_note_id(self, block: ScriptBlock):
        if not block.notes:
            return 1

        return max(note.id for note in block.notes) + 1

    def get_current_block_notes(self):
        block = self.get_current_block()

        if block is None:
            return []

        return block.notes

    def select_note_by_id(self, note_id: int):
        note = self.find_note_by_id(note_id)

        if note is None:
            return

        self.selected_note_id = note.id
        self.move_cursor_to_line(note.line_index)

        self.set_note_panel_enabled(True)

        self.note_text_editor.blockSignals(True)

        self.note_panel_title.setText("Заметка")
        self.note_line_label.setText("Привязана к выбранному месту в тексте")
        self.note_text_editor.setPlainText(note.text)

        self.note_text_editor.blockSignals(False)

        self.update_note_color_button(note.color)

    def find_note_by_id(self, note_id: int):
        block = self.get_current_block()

        if block is None:
            return None

        for note in block.notes:
            if note.id == note_id:
                return note

        return None

    def update_selected_note_text(self):
        note = self.find_note_by_id(self.selected_note_id)

        if note is None:
            return

        note.text = self.note_text_editor.toPlainText()

    def change_selected_note_color(self):
        note = self.find_note_by_id(self.selected_note_id)

        if note is None:
            return

        color = self.choose_color(note.color)

        if color is None:
            return

        note.color = color
        self.update_note_color_button(note.color)
        self.text_editor.refresh_note_markers()

    def delete_selected_note(self):
        block = self.get_current_block()

        if block is None or self.selected_note_id is None:
            return

        block.notes = [
            note for note in block.notes
            if note.id != self.selected_note_id
        ]

        self.selected_note_id = None
        self.set_note_panel_enabled(False)
        self.text_editor.refresh_note_markers()

    def update_note_color_button(self, color: str):
        self.note_color_button.setStyleSheet(
            f"background-color: {color}; color: black;"
        )

    def set_note_panel_enabled(self, enabled: bool):
        self.note_text_editor.setEnabled(enabled)
        self.note_color_button.setEnabled(enabled)
        self.delete_note_button.setEnabled(enabled)

        if not enabled:
            self.selected_note_id = None

            self.note_text_editor.blockSignals(True)

            self.note_panel_title.setText("Заметка не выбрана")
            self.note_line_label.setText("")
            self.note_text_editor.clear()
            self.note_color_button.setStyleSheet("")

            self.note_text_editor.blockSignals(False)

    def move_cursor_to_line(self, line_index: int):
        block = self.text_editor.document().findBlockByNumber(line_index)

        if not block.isValid():
            return

        cursor = QTextCursor(block)
        self.text_editor.setTextCursor(cursor)
        self.text_editor.ensureCursorVisible()

    def normalize_note_line_indexes(self, block: ScriptBlock):
        line_count = max(1, self.text_editor.blockCount())

        for note in block.notes:
            if note.line_index < 0:
                note.line_index = 0

            if note.line_index >= line_count:
                note.line_index = line_count - 1

    def sync_blocks_order_from_list(self):
        new_order = []

        for row in range(self.blocks_list.count()):
            item = self.blocks_list.item(row)
            block_id = item.data(Qt.UserRole)

            block = self.find_block_by_id(block_id)

            if block is not None:
                block.order_index = row
                new_order.append(block)

        self.scenario.blocks = new_order

        current_item = self.blocks_list.currentItem()

        if current_item is not None:
            self.current_block_id = current_item.data(Qt.UserRole)

    def refresh_blocks_list(self, keep_current: bool = False):
        current_id = self.current_block_id if keep_current else None

        self.blocks_list.blockSignals(True)
        self.blocks_list.clear()

        item_to_select = None

        sorted_blocks = sorted(self.scenario.blocks, key=lambda block: block.order_index)

        for block in sorted_blocks:
            item = QListWidgetItem(block.title)
            item.setData(Qt.UserRole, block.id)

            color = QColor(block.color)

            if color.isValid():
                item.setBackground(QBrush(color))

            self.blocks_list.addItem(item)

            if keep_current and block.id == current_id:
                item_to_select = item

        self.blocks_list.blockSignals(False)

        if item_to_select is not None:
            self.blocks_list.setCurrentItem(item_to_select)

    def recalculate_order_indexes(self):
        for index, block in enumerate(self.scenario.blocks):
            block.order_index = index

    def find_block_by_id(self, block_id: int):
        for block in self.scenario.blocks:
            if block.id == block_id:
                return block

        return None

    def get_current_block(self):
        if self.current_block_id is None:
            return None

        return self.find_block_by_id(self.current_block_id)

    def clear_editors(self):
        self.block_title_input.blockSignals(True)
        self.text_editor.blockSignals(True)

        self.block_title_input.clear()
        self.text_editor.clear()
        self.update_hint_display("")
        self.text_editor.refresh_note_markers()

        self.block_title_input.blockSignals(False)
        self.text_editor.blockSignals(False)

        self.set_note_panel_enabled(False)

    def update_duration_label(self):
        full_text = " ".join(block.text for block in self.scenario.blocks)
        minutes = DurationCalculator.calculate_minutes(full_text)
        formatted_duration = DurationCalculator.format_duration(minutes)

        self.duration_label.setText(f"Примерная длительность: {formatted_duration}")

    def save_scenario(self):
        Path("data/scripts").mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сценарий",
            "data/scripts/scenario.json",
            "JSON files (*.json)",
        )

        if not file_path:
            return

        try:
            FileStorage.save_scenario(self.scenario, file_path)
            QMessageBox.information(self, "Готово", "Сценарий успешно сохранён.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить сценарий:\n{error}")

    def export_scenario_to_pdf(self):
        if not self.scenario.blocks:
            QMessageBox.warning(
                self,
                "Нет данных",
                "Перед экспортом добавьте хотя бы один блок сценария.",
            )
            return

        Path("data/scripts").mkdir(parents=True, exist_ok=True)

        safe_title = self.make_safe_file_name(self.scenario.title)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт сценария в PDF",
            f"data/scripts/{safe_title}.pdf",
            "PDF files (*.pdf)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        try:
            PdfExporter.export_scenario_to_pdf(self.scenario, file_path)
            QMessageBox.information(self, "Готово", "Сценарий успешно экспортирован в PDF.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать сценарий:\n{error}")

    def load_scenario(self):
        Path("data/scripts").mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть сценарий",
            "data/scripts",
            "JSON files (*.json)",
        )

        if not file_path:
            return

        try:
            self.scenario = FileStorage.load_scenario(file_path)
            self.current_template = None

            self.title_input.setText(self.scenario.title)

            if self.scenario.blocks:
                self.next_block_id = max(block.id for block in self.scenario.blocks) + 1
            else:
                self.next_block_id = 1

            self.current_block_id = None
            self.selected_note_id = None

            self.refresh_blocks_list()
            self.clear_editors()
            self.update_duration_label()

            if self.scenario.blocks:
                self.blocks_list.setCurrentRow(0)

            QMessageBox.information(self, "Готово", "Сценарий успешно открыт.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть сценарий:\n{error}")

    def save_current_as_template(self):
        if not self.scenario.blocks:
            QMessageBox.warning(
                self,
                "Нет блоков",
                "Чтобы создать шаблон, сначала добавьте хотя бы один блок.",
            )
            return

        template_name, ok = QInputDialog.getText(
            self,
            "Название шаблона",
            "Введите название шаблона:",
            text=f"Шаблон: {self.scenario.title}",
        )

        if not ok or not template_name.strip():
            return

        template_blocks = []

        sorted_blocks = sorted(self.scenario.blocks, key=lambda block: block.order_index)

        for index, block in enumerate(sorted_blocks):
            template_blocks.append(
                TemplateBlock(
                    title=block.title,
                    order_index=index,
                    color=block.color,
                    hint=block.hint,
                )
            )

        template = ScenarioTemplate(
            title=template_name.strip(),
            blocks=template_blocks,
        )

        Path("data/templates").mkdir(parents=True, exist_ok=True)

        safe_name = self.make_safe_file_name(template.title)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить шаблон",
            f"data/templates/{safe_name}.json",
            "JSON files (*.json)",
        )

        if not file_path:
            return

        try:
            FileStorage.save_template(template, file_path)
            self.current_template = template
            QMessageBox.information(self, "Готово", "Шаблон успешно сохранён.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить шаблон:\n{error}")

    def import_template(self) -> bool:
        Path("data/templates").mkdir(parents=True, exist_ok=True)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт шаблона",
            "data/templates",
            "JSON files (*.json)",
        )

        if not file_path:
            return False

        try:
            self.current_template = FileStorage.load_template(file_path)
            QMessageBox.information(
                self,
                "Готово",
                f"Шаблон «{self.current_template.title}» успешно импортирован.",
            )
            return True
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать шаблон:\n{error}")
            return False

    def create_scenario_from_template(self):
        if self.current_template is None:
            loaded = self.import_template()

            if not loaded:
                return

        scenario_title, ok = QInputDialog.getText(
            self,
            "Новый сценарий",
            "Введите название нового сценария:",
            text=f"Сценарий по шаблону «{self.current_template.title}»",
        )

        if not ok or not scenario_title.strip():
            return

        sorted_template_blocks = sorted(
            self.current_template.blocks,
            key=lambda block: block.order_index,
        )

        new_blocks = []

        for index, template_block in enumerate(sorted_template_blocks):
            new_blocks.append(
                ScriptBlock(
                    id=index + 1,
                    title=template_block.title,
                    order_index=index,
                    text="",
                    color=template_block.color,
                    hint=template_block.hint,
                    notes=[],
                )
            )

        self.scenario = Scenario(
            title=scenario_title.strip(),
            template_name=self.current_template.title,
            blocks=new_blocks,
        )

        self.next_block_id = len(new_blocks) + 1
        self.current_block_id = None
        self.selected_note_id = None

        self.title_input.setText(self.scenario.title)
        self.refresh_blocks_list()
        self.clear_editors()
        self.update_duration_label()

        if self.scenario.blocks:
            self.blocks_list.setCurrentRow(0)

        QMessageBox.information(self, "Готово", "Сценарий создан по шаблону.")

    def make_safe_file_name(self, name: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        safe_name = "".join("_" if char in invalid_chars else char for char in name)
        safe_name = safe_name.strip()

        if not safe_name:
            return "template"

        return safe_name