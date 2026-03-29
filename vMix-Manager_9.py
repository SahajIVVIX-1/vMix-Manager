#!/usr/bin/env python3
"""
vMix Script Manager
===================
A PyQt6 application for managing vMix .vmix production files.
"""

import sys, os, json, csv, uuid, copy, re, logging, shutil, subprocess, platform # <--- ADD shutil
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom
import shutil
import re
import ctypes

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QToolBar, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
    QFileDialog, QMessageBox, QInputDialog, QTabWidget, QGroupBox,
    QCheckBox, QHeaderView, QAbstractItemView, QTextEdit, QMenu,
    QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QSizePolicy,
    QProgressBar, QStyledItemDelegate, QComboBox
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QTimer,
    QObject, QThread
)
from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence, QIcon, QPalette, QLinearGradient, QBrush

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME, APP_VERSION = "vMix Manager", "6"

VIDEO_EXTS = {'.mp4','.avi','.mov','.mkv','.wmv','.flv','.m4v','.webm','.ts','.mts'}
IMAGE_EXTS = {'.jpg','.jpeg','.png','.bmp','.gif','.tiff','.tga','.webp'}
AUDIO_EXTS = {'.mp3','.wav','.aac','.flac','.ogg','.wma','.m4a'}
ALL_MEDIA  = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

INPUT_TYPES = {1:"Image", 0:"Video", 3:"Audio", 6:"Desktop", 7:"NDI", 12:"Title", 20:"Camera"}

DEF_CAT_NAMES = {
    0: "ALL", 1: "Red", 2: "Green", 3: "Orange", 4: "Purple", 5: "Aqua", 6: "Blue",
    7: "Custom1", 8: "Custom2", 9: "Custom3", 10: "Custom4", 11: "Custom5",
    12: "Custom6", 13: "Custom7", 14: "Custom8", 15: "Custom9", 16: "Custom10",
    17: "Custom11", 18: "Custom12", 19: "Custom13", 20: "Custom14", 21: "Custom15", 22: "Custom16"
}

CAT_MAP = {
    1: "Red", 2: "Green", 3: "Orange", 4: "Purple", 5: "Aqua", 6: "Blue",
    7: "Custom1", 8: "Custom2", 9: "Custom3", 10: "Custom4", 11: "Custom5",
    12: "Custom6", 13: "Custom7", 14: "Custom8", 15: "Custom9", 16: "Custom10",
    17: "Custom11", 18: "Custom12", 19: "Custom13", 20: "Custom14", 21: "Custom15", 22: "Custom16"
}

CAT_ID_LOOKUP = {
    "All.Text": 0,
    "Red.Text": 1,
    "Green.Text": 2,
    "Orange.Text": 3,
    "Purple.Text": 4,
    "Aqua.Text": 5,
    "Blue.Text": 6,
    "Custom1.Text": 7,  "Custom2.Text": 8,  "Custom3.Text": 9,  "Custom4.Text": 10,
    "Custom5.Text": 11, "Custom6.Text": 12, "Custom7.Text": 13, "Custom8.Text": 14,
    "Custom9.Text": 15, "Custom10.Text": 16, "Custom11.Text": 17, "Custom12.Text": 18,
    "Custom13.Text": 19, "Custom14.Text": 20, "Custom15.Text": 21, "Custom16.Text": 22
}

CAT_ENABLED_LOOKUP = {k.replace(".Text", ".Enabled"): v for k, v in CAT_ID_LOOKUP.items()}

# ── Professional Black & White Theme with Rainbow Accent System ────────────────
C = {
    # Base surfaces — deep black to soft charcoal
    'bg':       '#0A0A0A',   # Near-black base
    'bg2':      '#111111',   # Panel surface
    'bg3':      '#1A1A1A',   # Elevated surface
    'bg4':      '#222222',   # Input fields
    'bg5':      '#2A2A2A',   # Hovered surface

    # Text hierarchy
    'text':     '#F0F0F0',   # Primary white text
    'text2':    '#C8C8C8',   # Secondary text
    'dim':      '#888888',   # Muted / placeholder
    'dim2':     '#555555',   # Very muted

    # Borders — subtle white lines
    'border':   '#2E2E2E',   # Default border
    'border2':  '#3E3E3E',   # Active border
    'border3':  '#505050',   # Focus border

    # Rainbow accents — used contextually for labels, icons, highlights
    'r_red':    '#FF4D4D',   # Error / Remove / Danger
    'r_orange': '#FF8C00',   # Warning / Pending
    'r_yellow': '#FFD700',   # Attention / Star
    'r_green':  '#39D353',   # Success / OK
    'r_cyan':   '#00D4FF',   # Info / Link
    'r_blue':   '#4D9FFF',   # Primary action
    'r_violet': '#9B59FF',   # Special / Transform
    'r_pink':   '#FF6EB4',   # Category highlight

    # Semantic aliases
    'accent':   '#4D9FFF',   # Primary CTA (blue)
    'ok':       '#39D353',   # Success green
    'warn':     '#FF8C00',   # Warning orange
    'err':      '#FF4D4D',   # Error red
    'hi':       '#1E1E1E',   # Highlight bg
    'alt':      '#141414',   # Alternate row
}

# Rainbow gradient colors for header text (cycles through spectrum)
RAINBOW_WORDS = ['#FF4D4D', '#FF8C00', '#FFD700', '#39D353', '#00D4FF', '#4D9FFF', '#9B59FF']


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def rainbow_html(text: str) -> str:
    """Wraps each character in a rainbow color span for QLabel rich text."""
    result = ""
    colors = RAINBOW_WORDS
    char_idx = 0
    for ch in text:
        if ch == ' ':
            result += '&nbsp;'
        else:
            col = colors[char_idx % len(colors)]
            result += f'<span style="color:{col};">{ch}</span>'
            char_idx += 1
    return result


# ── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class VmixInput:
    key: str = ""
    original_title: str = ""
    input_type: int = 1
    category: int = 0
    position: int = 0
    file_path: str = ""
    xml_payload: str = ""
    state: str = "1"
    muted: str = "True"
    volume_f: str = "1"
    loop: str = "False"
    extra_attrs: Dict = field(default_factory=dict)

    @property
    def type_name(self): return INPUT_TYPES.get(self.input_type, f"Type-{self.input_type}")
    @property
    def filename(self): return Path(self.file_path).name if self.file_path else self.original_title

@dataclass
class VmixCategory:
    index: int = 0
    name: str = ""
    enabled: bool = True
    inputs: List[VmixInput] = field(default_factory=list)

    @property
    def display_name(self): return self.name or DEF_CAT_NAMES.get(self.index, f"Cat {self.index}")
    def count(self): return len(self.inputs)

class VmixParser:
    def __init__(self):
        self.categories: Dict[int, VmixCategory] = {}
        self.vmix_version = "9"
        self.file_path = ""
        self._orig_root: Optional[ET.Element] = None
        self.default_pos = (
            '<?xml version="1.0" encoding="utf-16"?><ArrayOfMatrixPosition '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<MatrixPosition><Hidden>false</Hidden><Border><Enabled>false</Enabled><Thickness>0</Thickness>'
            '<Radius>0</Radius><ColourHTML>White</ColourHTML></Border><Mirror>false</Mirror><ZoomX>1</ZoomX>'
            '<DesignerLocked>false</DesignerLocked><ZoomY>1</ZoomY><PostZoomX>1</PostZoomX><PostZoomY>1</PostZoomY>'
            '<RotateOrigin><X>0</X><Y>0</Y><Z>0</Z></RotateOrigin><Rotate><X>0</X><Y>0</Y><Z>0</Z></Rotate>'
            '<PanX>0</PanX><PanY>0</PanY><SourceRotation>R0</SourceRotation></MatrixPosition></ArrayOfMatrixPosition>'
        )

    def load(self, path: str) -> bool:
        try:
            self.file_path = path
            tree = ET.parse(path)
            self._orig_root = tree.getroot()
            self._parse()
            return True
        except Exception as e:
            logging.error(f"Load failed: {e}")
            return False

    def _parse(self):
        self.categories = {}
        name_map = {}
        enabled_map = {}

        cs_node = self._orig_root.find('CategorySettings')
        if cs_node is not None:
            for child in cs_node:
                if child.tag in CAT_ID_LOOKUP:
                    name_map[CAT_ID_LOOKUP[child.tag]] = child.text
                if child.tag in CAT_ENABLED_LOOKUP:
                    enabled_map[CAT_ENABLED_LOOKUP[child.tag]] = (child.text == "1")

        for i in range(23):
            raw_name = name_map.get(i, "")
            if i == 0:
                name = "ALL"
                is_enabled = True
            else:
                name = raw_name if (raw_name and raw_name.strip()) else "Empty Cat"
                is_enabled = enabled_map.get(i, True)
            self.categories[i] = VmixCategory(index=i, name=name, enabled=is_enabled)

        for el in self._orig_root.findall('Input'):
            inp = self._parse_input(el)
            if inp.category in self.categories:
                self.categories[inp.category].inputs.append(inp)

    def _parse_input(self, el: ET.Element) -> VmixInput:
        a = el.attrib
        fp = (el.text or "").strip()
        return VmixInput(
            key=a.get('Key', str(uuid.uuid4())),
            original_title=a.get('OriginalTitle', Path(fp).name if fp else 'Unknown'),
            input_type=int(a.get('Type','1')),
            category=int(a.get('Category','0')),
            position=int(a.get('Position','0')),
            file_path=fp,
            xml_payload=a.get('XML', ''),
            extra_attrs={k:v for k,v in a.items() if k not in {'Key','OriginalTitle','Type','Category','Position', 'XML'}}
        )

    def swap_categories(self, idx_a: int, idx_b: int):
        if idx_a not in self.categories or idx_b not in self.categories:
            return False
        self.categories[idx_a].name, self.categories[idx_b].name = \
            self.categories[idx_b].name, self.categories[idx_a].name
        self.categories[idx_a].inputs, self.categories[idx_b].inputs = \
            self.categories[idx_b].inputs, self.categories[idx_a].inputs
        for inp in self.categories[idx_a].inputs:
            inp.category = idx_a
        for inp in self.categories[idx_b].inputs:
            inp.category = idx_b
        return True

    def save(self, path: str) -> bool:
        try:
            root = ET.Element('XML')
            ET.SubElement(root, 'Version').text = self.vmix_version
            ET.SubElement(root, 'ZoomManager')
            for cat in sorted(self.categories.values(), key=lambda c: c.index):
                for inp in sorted(cat.inputs, key=lambda x: x.position):
                    root.append(self._build_el(inp))
            if self._orig_root is not None:
                for el in self._orig_root:
                    if el.tag in ('Version', 'ZoomManager', 'Input'): continue
                    new_el = copy.deepcopy(el)
                    if new_el.tag == 'CategorySettings':
                        for child in new_el:
                            idx = CAT_ID_LOOKUP.get(child.tag)
                            if idx is not None and idx in self.categories:
                                cat = self.categories[idx]
                                child.text = "" if cat.name == "Empty Cat" else cat.name
                            idx_en = CAT_ENABLED_LOOKUP.get(child.tag)
                            if idx_en is not None and idx_en in self.categories:
                                child.text = "1" if self.categories[idx_en].enabled else "0"
                    root.append(new_el)
            tree = ET.ElementTree(root)
            with open(path, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=False)
            self.file_path = path
            return True
        except Exception as e:
            logging.error(f"Save failed: {e}"); return False

    def _build_el(self, inp: VmixInput) -> ET.Element:
        attrs = {
            'Type': str(inp.input_type), 'Position': str(inp.position), 'State': '1',
            'OriginalTitle': inp.original_title, 'Key': inp.key,
            'Category': str(inp.category), 'AspectRatio': '100',
            'VideoShader_Alpha': '1', 'VideoShader_White': '1',
            'VideoShader_ClippingX2': '1', 'VideoShader_ClippingY2': '1',
            'Positions': self.default_pos
        }
        if hasattr(inp, 'xml_payload') and inp.xml_payload:
            attrs['XML'] = inp.xml_payload
        attrs.update(inp.extra_attrs)
        el = ET.Element('Input', attrib={k: str(v) for k, v in attrs.items() if v is not None})
        if inp.file_path: el.text = inp.file_path
        return el

    def create_new(self):
        self.categories = {i: VmixCategory(index=i, name="" if i>0 else "ALL") for i in range(23)}
        self._orig_root = None
        self.file_path = ""

    def add_category(self, name: str) -> VmixCategory:
        idx = next((i for i in range(1, 23) if not self.categories[i].name), 1)
        self.categories[idx].name = name
        return self.categories[idx]

    def add_input(self, cat_idx: int, file_path: str):
        pos = len(self.categories[cat_idx].inputs)
        inp = VmixInput(key=str(uuid.uuid4()), original_title=Path(file_path).name,
                        input_type=0 if Path(file_path).suffix.lower() in VIDEO_EXTS else 1,
                        category=cat_idx, position=pos, file_path=file_path)
        self.categories[cat_idx].inputs.append(inp)

    def remove_input(self, inp: VmixInput):
        if inp.category in self.categories:
            self.categories[inp.category].inputs.remove(inp)

    def reorder(self, cat_idx: int):
        for i, inp in enumerate(self.categories[cat_idx].inputs):
            inp.position = i


# ── File Scanner ───────────────────────────────────────────────────────────────
class FileScanner:
    @staticmethod
    def scan(folder: str, recursive=False, exts=None) -> List[str]:
        exts = exts or ALL_MEDIA
        p = Path(folder); pat = "**/*" if recursive else "*"
        return sorted([str(f) for f in p.glob(pat) if f.is_file() and f.suffix.lower() in exts])

    @staticmethod
    def subfolders(folder: str) -> List[Tuple[str, List[str]]]:
        result = []
        for sub in sorted(Path(folder).iterdir()):
            if sub.is_dir():
                files = sorted([str(f) for f in sub.iterdir()
                                if f.is_file() and f.suffix.lower() in ALL_MEDIA])
                if files: result.append((sub.name, files))
        return result

    @staticmethod
    def detect(fp: str) -> str:
        ext = Path(fp).suffix.lower()
        return "Video" if ext in VIDEO_EXTS else ("Image" if ext in IMAGE_EXTS else ("Audio" if ext in AUDIO_EXTS else "Unknown"))


def sanitize_folder_name(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


class BigEditorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setMinimumHeight(44)
        editor.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        editor.setStyleSheet(
            f"background: {C['bg4']}; color: {C['text']}; "
            f"border: 2px solid {C['r_blue']}; border-radius: 3px; padding: 5px 8px;"
        )
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        rect.setHeight(44)
        editor.setGeometry(rect)


# ── Export Worker ──────────────────────────────────────────────────────────────
class ExportWorker(QObject):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(int, int)
    log_msg = pyqtSignal(str, str)

    def __init__(self, categories: List[VmixCategory], destination_root: str):
        super().__init__()
        self.categories = categories
        self.destination_root = destination_root

    def run(self):
        success_count = 0
        error_count = 0
        total_files = sum(len(cat.inputs) for cat in self.categories)
        if total_files == 0:
            self.finished.emit(0, 0)
            return
        self.log_msg.emit(f"Starting export of {total_files} files...", "INFO")
        for cat in self.categories:
            safe_name = sanitize_folder_name(cat.display_name)
            target_dir = Path(self.destination_root) / safe_name
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                self.log_msg.emit(f"Could not create folder {safe_name}: {e}", "ERROR")
                error_count += len(cat.inputs)
                continue
            for inp in cat.inputs:
                src_path = inp.file_path
                if not src_path or not os.path.exists(src_path):
                    self.log_msg.emit(f"Skipping (File not found): {inp.original_title}", "WARNING")
                    error_count += 1
                else:
                    try:
                        file_name = Path(src_path).name
                        dest_path = target_dir / file_name
                        self.progress_updated.emit(success_count + error_count, file_name)
                        shutil.copy2(src_path, dest_path)
                        success_count += 1
                    except Exception as e:
                        self.log_msg.emit(f"Failed to copy {inp.original_title}: {e}", "ERROR")
                        error_count += 1
        self.finished.emit(success_count, error_count)


# ── Export Widget ──────────────────────────────────────────────────────────────
class CategoryExportWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser_ref = None
        self.thread = None
        self.worker = None
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        info = QLabel("Factory Export — Copy Categories to Folders")
        info.setFont(QFont("Segoe UI Semibold", 12, QFont.Weight.DemiBold))
        info.setStyleSheet(f"color: {C['r_cyan']}; letter-spacing: 0.5px;")
        layout.addWidget(info)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C['border2']};")
        layout.addWidget(sep)

        lbl1 = QLabel("Select categories to export:")
        lbl1.setFont(QFont("Segoe UI", 9))
        lbl1.setStyleSheet(f"color: {C['dim']}; margin-top: 4px;")
        layout.addWidget(lbl1)

        self.cat_list = QListWidget()
        self.cat_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        layout.addWidget(self.cat_list)

        lbl2 = QLabel("Destination root folder:")
        lbl2.setFont(QFont("Segoe UI", 9))
        lbl2.setStyleSheet(f"color: {C['dim']};")
        layout.addWidget(lbl2)

        path_row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Select folder where subfolders will be created…")
        self.dest_edit.setFixedHeight(36)
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedHeight(36)
        btn_browse.clicked.connect(self._browse_dest)
        path_row.addWidget(self.dest_edit)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; border-radius: 3px; background: {C['bg3']}; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {C['r_blue']}, stop:0.5 {C['r_violet']}, stop:1 {C['r_pink']}); border-radius: 3px; }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_log = LogWidget()
        layout.addWidget(self.status_log)

        self.btn_export = QPushButton("  Start Export")
        self.btn_export.setFixedHeight(44)
        self.btn_export.setFont(QFont("Segoe UI Semibold", 10, QFont.Weight.DemiBold))
        self.btn_export.setStyleSheet(
            f"background: {C['ok']}; color: #000; font-weight: 700; "
            f"border: none; border-radius: 4px; letter-spacing: 0.5px;"
        )
        self.btn_export.clicked.connect(self._start_export)
        layout.addWidget(self.btn_export)

    def refresh_categories(self, categories):
        self.cat_list.clear()
        for cat in sorted(categories.values(), key=lambda x: x.index):
            if cat.index == 0: continue
            item = QListWidgetItem(f"  [{cat.index:02d}]  {cat.display_name}  ·  {len(cat.inputs)} items")
            item.setData(Qt.ItemDataRole.UserRole, cat.index)
            self.cat_list.addItem(item)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Root")
        if folder:
            self.dest_edit.setText(folder)

    def _start_export(self):
        selected_items = self.cat_list.selectedItems()
        dest = self.dest_edit.text()
        if not selected_items:
            QMessageBox.warning(self, "Export", "Please select at least one category.")
            return
        if not dest or not os.path.isdir(dest):
            QMessageBox.warning(self, "Export", "Please select a valid destination folder.")
            return
        selected_cats = [self.parser_ref.categories[i.data(Qt.ItemDataRole.UserRole)] for i in selected_items]
        total_files = sum(len(c.inputs) for c in selected_cats)
        if total_files == 0:
            QMessageBox.information(self, "Export", "Selected categories contain no files.")
            return
        self.btn_export.setEnabled(False)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_log.clear()
        self.thread = QThread()
        self.worker = ExportWorker(selected_cats, dest)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.log_msg.connect(self.status_log.log)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _on_progress(self, count, filename):
        self.progress_bar.setValue(count)
        self.status_log.log(f"Copying: {filename}")

    def _on_finished(self, success, errors):
        self.btn_export.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        msg = f"Export Complete!\n— Successfully copied: {success}\n— Failed / Missing: {errors}"
        self.status_log.log(msg, "SUCCESS" if errors == 0 else "WARNING")
        QMessageBox.information(self, "Export Finished", msg)


# ── Log Widget ─────────────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(130)
        self.setFont(QFont("Consolas", 8))
        self.setStyleSheet(
            f"background: {C['bg']}; color: {C['text2']}; "
            f"border: 1px solid {C['border']}; border-radius: 4px; padding: 4px;"
        )

    def log(self, msg: str, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        col = {
            "INFO":    C['r_cyan'],
            "SUCCESS": C['r_green'],
            "WARNING": C['r_orange'],
            "ERROR":   C['r_red'],
        }.get(level, C['text'])
        self.append(
            f'<span style="color:{C["dim2"]}">[{ts}]</span> '
            f'<span style="color:{col};font-weight:600">{level}</span>'
            f'<span style="color:{C["text2"]}"> — {msg}</span>'
        )
        self.moveCursor(QTextCursor.MoveOperation.End)


# ── Folder Import Widget ───────────────────────────────────────────────────────
class FolderImportWidget(QWidget):
    import_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        queue_gb = QGroupBox("Folder Queue  —  imports into the selected category")
        queue_gb.setFont(QFont("Segoe UI", 9))
        queue_l = QVBoxLayout(queue_gb)
        queue_l.setSpacing(8)

        self.preview = QListWidget()
        self.preview.setFont(QFont("Consolas", 9))
        queue_l.addWidget(self.preview)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("  Add Folder to Queue")
        btn_add.setFixedHeight(34)
        btn_add.clicked.connect(self._add_folder_to_queue)
        btn_clr = QPushButton("  Clear Queue")
        btn_clr.setFixedHeight(34)
        btn_clr.clicked.connect(self._clear_queue)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_clr)
        btn_row.addStretch()
        queue_l.addLayout(btn_row)
        layout.addWidget(queue_gb)

        self.btn_import = QPushButton("  Start Bulk Import  (Headers @ 200px)")
        self.btn_import.setFixedHeight(48)
        self.btn_import.setFont(QFont("Segoe UI Semibold", 11, QFont.Weight.DemiBold))
        self.btn_import.setStyleSheet(
            f"background: {C['ok']}; color: #000; border: none; border-radius: 4px; "
            f"font-weight: 700; letter-spacing: 0.5px;"
        )
        self.btn_import.clicked.connect(self._emit_import)
        layout.addWidget(self.btn_import)

    def _add_folder_to_queue(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            p = Path(folder)
            files = FileScanner.scan(folder, recursive=False)
            files.sort()
            self.queue.append((p.name, files))
            item = QListWidgetItem(f"  [{p.name}]   →   {len(files)} files")
            item.setForeground(QColor(C['r_green']))
            self.preview.addItem(item)

    def _clear_queue(self):
        self.queue = []
        self.preview.clear()

    def _emit_import(self):
        if not self.queue:
            QMessageBox.warning(self, "Empty", "Add folders to the queue first.")
            return
        self.import_requested.emit(self.queue)
        self._clear_queue()


class FactoryResetWidget(QWidget):
    reset_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        group = QGroupBox("Production Management  &  Factory Reset")
        group.setFont(QFont("Segoe UI", 9))
        gl = QVBoxLayout(group)
        gl.setSpacing(10)

        desc = QLabel(
            "Use these tools to bulk-delete inputs or reset the entire vMix session.\n"
            "Destructive operations cannot be undone — save your file first."
        )
        desc.setFont(QFont("Segoe UI", 9))
        desc.setStyleSheet(f"color: {C['dim']}; margin-bottom: 6px; line-height: 1.5;")
        desc.setWordWrap(True)
        gl.addWidget(desc)

        self.btn_clear_cat = QPushButton("  Clear All Inputs in Current Category")
        self.btn_clear_cat.setFixedHeight(42)
        self.btn_clear_cat.setFont(QFont("Segoe UI", 10))
        self.btn_clear_cat.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_yellow']}; border: 1px solid {C['r_yellow']}; "
            f"border-radius: 4px; text-align: left; padding-left: 16px;"
        )
        self.btn_clear_cat.clicked.connect(lambda: self.reset_triggered.emit("current"))

        self.btn_wipe_all = QPushButton("  Wipe ALL Inputs  (Globally)")
        self.btn_wipe_all.setFixedHeight(42)
        self.btn_wipe_all.setFont(QFont("Segoe UI", 10))
        self.btn_wipe_all.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_orange']}; border: 1px solid {C['r_orange']}; "
            f"border-radius: 4px; text-align: left; padding-left: 16px;"
        )
        self.btn_wipe_all.clicked.connect(lambda: self.reset_triggered.emit("all"))

        self.btn_factory = QPushButton("  Full Factory Reset  —  Wipe All + Reset Names")
        self.btn_factory.setFixedHeight(42)
        self.btn_factory.setFont(QFont("Segoe UI", 10))
        self.btn_factory.setStyleSheet(
            f"background: {C['r_red']}; color: #fff; border: none; "
            f"border-radius: 4px; font-weight: 700; text-align: left; padding-left: 16px;"
        )
        self.btn_factory.clicked.connect(lambda: self.reset_triggered.emit("session"))

        for b in [self.btn_clear_cat, self.btn_wipe_all, self.btn_factory]:
            gl.addWidget(b)

        layout.addWidget(group)
        layout.addStretch()


# ── Category Import Widget ─────────────────────────────────────────────────────
class CategoryImportWidget(QWidget):
    structure_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._structure = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QLabel(
            "Select a root folder — each subfolder becomes a category, "
            "and files inside become inputs."
        )
        info.setWordWrap(True)
        info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet(f"color:{C['dim']}; margin-bottom:4px;")
        layout.addWidget(info)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select root folder…")
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(36)
        btn_b = QPushButton("Browse…")
        btn_b.setFixedHeight(36)
        btn_b.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(btn_b)
        layout.addLayout(path_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Category / Input', 'Type', 'Count'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 60)
        self.tree.setFont(QFont("Segoe UI", 9))
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        self.lbl = QLabel("No folder selected")
        self.lbl.setFont(QFont("Segoe UI", 9))
        self.lbl.setStyleSheet(f"color: {C['dim']};")
        btn_imp = QPushButton("  Import All Categories")
        btn_imp.setFixedHeight(38)
        btn_imp.setFont(QFont("Segoe UI Semibold", 10, QFont.Weight.DemiBold))
        btn_imp.setStyleSheet(
            f"background: {C['r_blue']}; color: #fff; border: none; border-radius: 4px; "
            f"font-weight: 700; padding: 0 16px;"
        )
        btn_imp.clicked.connect(self._emit)
        btn_row.addWidget(self.lbl)
        btn_row.addStretch()
        btn_row.addWidget(btn_imp)
        layout.addLayout(btn_row)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if f:
            self.path_edit.setText(f)
            self._scan(f)

    def _scan(self, folder):
        self._structure = FileScanner.subfolders(folder)
        self.tree.clear()
        total = 0
        icons = {'Video': '▶', 'Image': '◼', 'Audio': '♪', 'Unknown': '•'}
        type_colors = {'Video': C['r_blue'], 'Image': C['r_green'], 'Audio': C['r_violet'], 'Unknown': C['dim']}
        for name, files in self._structure:
            ci = QTreeWidgetItem([f"  {name}", "Category", str(len(files))])
            ci.setForeground(0, QColor(C['r_cyan']))
            ci.setFont(0, QFont("Segoe UI Semibold", 10, QFont.Weight.DemiBold))
            for fp in files[:20]:
                ftype = FileScanner.detect(fp)
                fi = QTreeWidgetItem(ci, [f"  {icons.get(ftype,'•')} {Path(fp).name}", ftype, ""])
                fi.setForeground(0, QColor(C['text2']))
                fi.setForeground(1, QColor(type_colors.get(ftype, C['dim'])))
            if len(files) > 20:
                QTreeWidgetItem(ci, [f"  … +{len(files)-20} more files", "", ""])
            self.tree.addTopLevelItem(ci)
            ci.setExpanded(True)
            total += len(files)
        self.lbl.setText(f"{len(self._structure)} categories  ·  {total} files total")

    def _emit(self):
        if self._structure:
            self.structure_ready.emit(self._structure)


# ── Category Transform Widget ──────────────────────────────────────────────────
class CategoryTransformWidget(QWidget):
    request_swap = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Category Interchanger")
        title.setFont(QFont("Segoe UI Semibold", 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {C['r_violet']}; letter-spacing: 0.5px;")
        layout.addWidget(title)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C['border2']};")
        layout.addWidget(sep)

        desc = QLabel(
            "Select one category from each list, then execute the swap.\n"
            "All inputs inside will be moved to their new slot automatically."
        )
        desc.setWordWrap(True)
        desc.setFont(QFont("Segoe UI", 9))
        desc.setStyleSheet(f"color:{C['dim']}; margin-bottom:6px;")
        layout.addWidget(desc)

        swap_box = QHBoxLayout()
        swap_box.setSpacing(12)

        left_wrap = QVBoxLayout()
        lbl_a = QLabel("FROM SLOT")
        lbl_a.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_a.setStyleSheet(f"color: {C['r_blue']}; letter-spacing: 1px;")
        self.list_a = QListWidget()
        self.list_a.setFont(QFont("Segoe UI", 9))
        left_wrap.addWidget(lbl_a)
        left_wrap.addWidget(self.list_a)

        mid_col = QVBoxLayout()
        mid_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid_icon = QLabel("⇌")
        mid_icon.setFont(QFont("Arial", 22))
        mid_icon.setStyleSheet(f"color: {C['r_yellow']}; margin: 0 4px;")
        mid_col.addStretch()
        mid_col.addWidget(mid_icon, 0, Qt.AlignmentFlag.AlignCenter)
        mid_col.addStretch()

        right_wrap = QVBoxLayout()
        lbl_b = QLabel("TO SLOT")
        lbl_b.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_b.setStyleSheet(f"color: {C['r_pink']}; letter-spacing: 1px;")
        self.list_b = QListWidget()
        self.list_b.setFont(QFont("Segoe UI", 9))
        right_wrap.addWidget(lbl_b)
        right_wrap.addWidget(self.list_b)

        swap_box.addLayout(left_wrap)
        swap_box.addLayout(mid_col)
        swap_box.addLayout(right_wrap)
        layout.addLayout(swap_box)

        self.btn_swap = QPushButton("  Execute Swap  &  Reorganize")
        self.btn_swap.setFixedHeight(46)
        self.btn_swap.setFont(QFont("Segoe UI Semibold", 11, QFont.Weight.DemiBold))
        self.btn_swap.setStyleSheet(
            f"background: {C['r_violet']}; color: #fff; border: none; border-radius: 4px; "
            f"font-weight: 700; letter-spacing: 0.5px;"
        )
        self.btn_swap.clicked.connect(self._on_swap_clicked)
        layout.addWidget(self.btn_swap)

    def refresh_lists(self, categories):
        self.list_a.clear()
        self.list_b.clear()
        items = [cat for cat in categories.values() if cat.index != 0]
        colors = [C['r_red'], C['r_orange'], C['r_yellow'], C['r_green'],
                  C['r_cyan'], C['r_blue'], C['r_violet'], C['r_pink']]
        for i, cat in enumerate(sorted(items, key=lambda x: x.index)):
            txt = f"  [{cat.index:02d}]  {cat.display_name}  ({len(cat.inputs)} inputs)"
            col = QColor(colors[i % len(colors)])

            item_a = QListWidgetItem(txt)
            item_a.setData(Qt.ItemDataRole.UserRole, cat.index)
            item_a.setForeground(col)
            self.list_a.addItem(item_a)

            item_b = QListWidgetItem(txt)
            item_b.setData(Qt.ItemDataRole.UserRole, cat.index)
            item_b.setForeground(col)
            self.list_b.addItem(item_b)

    def _on_swap_clicked(self):
        sel_a = self.list_a.currentItem()
        sel_b = self.list_b.currentItem()
        if not sel_a or not sel_b:
            QMessageBox.warning(self, "Selection Required", "Please select a category from both lists.")
            return
        idx_a = sel_a.data(Qt.ItemDataRole.UserRole)
        idx_b = sel_b.data(Qt.ItemDataRole.UserRole)
        if idx_a == idx_b:
            QMessageBox.warning(self, "Invalid Swap", "Cannot swap a category with itself.")
            return
        self.request_swap.emit(idx_a, idx_b)


# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        icon_file = "app_icon.ico"
        icon_path = resource_path(icon_file)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        if platform.system() == "Windows":
            myappid = f"mycompany.vmixmanager.{APP_VERSION}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        self.parser = VmixParser()
        self.current_cat: Optional[VmixCategory] = None
        self.modified = False
        self._build_ui()
        self._apply_style()
        self._connect()
        self.parser.create_new()
        self._refresh_categories()
        self.log("vMix Manager ready.", "SUCCESS")

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setMinimumSize(1100, 700)
        self.resize(1360, 820)
        cw = QWidget()
        self.setCentralWidget(cw)
        ml = QVBoxLayout(cw)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        self._build_toolbar()
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(self._build_cat_panel())
        sp.addWidget(self._build_right_panel())
        sp.setSizes([240, 920])
        sp.setStretchFactor(0, 0)
        sp.setStretchFactor(1, 1)
        sp.setHandleWidth(1)
        ml.addWidget(sp, 1)
        ml.addWidget(self._build_log_panel())
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet(
            f"background: {C['bg']}; color: {C['dim']}; border-top: 1px solid {C['border']}; font-size: 9px;"
        )

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.setFixedHeight(46)
        self.addToolBar(tb)

        # App brand label
        brand = QLabel()
        brand.setText(
            f'<span style="font-family:Segoe UI;font-size:13px;font-weight:700;letter-spacing:1px;">'
            f'<span style="color:{C["r_red"]}">v</span>'
            f'<span style="color:{C["r_orange"]}">M</span>'
            f'<span style="color:{C["r_yellow"]}">i</span>'
            f'<span style="color:{C["r_green"]}">x</span>'
            f'<span style="color:{C["text2"]}"> </span>'
            f'<span style="color:{C["r_cyan"]}">M</span>'
            f'<span style="color:{C["r_blue"]}">a</span>'
            f'<span style="color:{C["r_violet"]}">n</span>'
            f'<span style="color:{C["r_pink"]}">a</span>'
            f'<span style="color:{C["r_red"]}">g</span>'
            f'<span style="color:{C["r_orange"]}">e</span>'
            f'<span style="color:{C["r_yellow"]}">r</span>'
            f'</span>'
        )
        brand.setContentsMargins(14, 0, 16, 0)
        tb.addWidget(brand)

        # Thin vertical rule
        sep_w = QWidget()
        sep_w.setFixedSize(1, 24)
        sep_w.setStyleSheet(f"background: {C['border2']};")
        tb.addWidget(sep_w)
        tb.addWidget(QLabel("  "))

        self.act_new     = QAction("New",    self); self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_open    = QAction("Open",   self); self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_save    = QAction("Save",   self); self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_saveas  = QAction("Save As…", self); self.act_saveas.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_expjson = QAction("Export JSON", self)
        self.act_expcsv  = QAction("Export CSV",  self)

        for a in [self.act_new, self.act_open, self.act_save, self.act_saveas]:
            tb.addAction(a)
        tb.addSeparator()
        for a in [self.act_expjson, self.act_expcsv]:
            tb.addAction(a)
        tb.addSeparator()

        search_lbl = QLabel("  Search  ")
        search_lbl.setFont(QFont("Segoe UI", 9))
        search_lbl.setStyleSheet(f"color: {C['dim']};")
        tb.addWidget(search_lbl)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter inputs…")
        self.search.setFixedWidth(220)
        self.search.setFixedHeight(30)
        self.search.setClearButtonEnabled(True)
        self.search.setFont(QFont("Segoe UI", 9))
        tb.addWidget(self.search)

        tb.addSeparator()
        self.file_lbl = QLabel("  No file loaded")
        self.file_lbl.setFont(QFont("Segoe UI", 9))
        self.file_lbl.setStyleSheet(f"color:{C['r_cyan']}; padding: 0 12px;")
        tb.addWidget(self.file_lbl)

    def _handle_factory_reset(self, mode: str):
        if mode == "current" and self.current_cat:
            if QMessageBox.question(self, "Confirm", f"Empty {self.current_cat.display_name}?") == QMessageBox.StandardButton.Yes:
                self.current_cat.inputs = []
        elif mode == "all":
            if QMessageBox.question(self, "Confirm", "Wipe EVERY input in this file?") == QMessageBox.StandardButton.Yes:
                for c in self.parser.categories.values(): c.inputs = []
        elif mode == "session":
            if QMessageBox.question(self, "Confirm", "FACTORY RESET? (Wipe everything + default names)") == QMessageBox.StandardButton.Yes:
                self.parser.create_new()
        self._refresh_categories()
        self._refresh_inputs()
        self.log(f"Reset action '{mode}' completed.", "WARNING")

    def _on_folder_bulk_import(self, folder_data: list):
        if not self.current_cat:
            QMessageBox.warning(self, "No Category Selected", "Please select a category from the left panel first.")
            return
        cat_idx = self.current_cat.index
        cat_name = self.current_cat.display_name
        added_count = 0
        for folder_name, file_paths in folder_data:
            header_xml = (
                f'<items><item name="Message.Text" version="2">'
                f'<Font Name="Arial" Size="214" FillColor="#FFFFFFFF" Style="Normal" '
                f'Weight="Bold" Stretch="Normal" LineSpacing="0" />'
                f'<value>{folder_name}</value></item></items>'
            )
            header_inp = VmixInput(
                key=str(uuid.uuid4()),
                original_title=folder_name,
                input_type=9000,
                category=cat_idx,
                file_path=r"C:\Program Files (x86)\vMix\titles\GT Text\Text Middle Centre Left Right Sharp.gtzip",
                xml_payload=header_xml
            )
            self.parser.categories[cat_idx].inputs.append(header_inp)
            added_count += 1
            for fp in file_paths:
                self.parser.add_input(cat_idx, fp)
                added_count += 1
        self.parser.reorder(cat_idx)
        self._refresh_inputs()
        self._refresh_categories()
        self._mark_modified()
        self.tabs.setCurrentIndex(0)
        self.log(f"Imported {len(folder_data)} folders to Category '{cat_name}'", "SUCCESS")

    def _rename_input_inline(self):
        row = self.tbl.currentRow()
        if row >= 0:
            item = self.tbl.item(row, 1)
            self.tbl.editItem(item)

    def _replace_input_file(self):
        row = self.tbl.currentRow()
        if row < 0: return
        ki = self.tbl.item(row, 5)
        key = ki.data(Qt.ItemDataRole.UserRole)
        inp = next((i for i in self.current_cat.inputs if i.key == key), None)
        if not inp: return
        new_file, _ = QFileDialog.getOpenFileName(self, "Replace Media File", "", "All Files (*)")
        if new_file:
            inp.file_path = os.path.normpath(new_file)
            inp.original_title = Path(new_file).name
            self._mark_modified()
            self._refresh_inputs()
            self.log(f"Replaced file for '{inp.original_title}'", "SUCCESS")

    def _tbl_context_menu(self, pos):
        item = self.tbl.itemAt(pos)
        if not item: return
        m = QMenu(self)
        act_ren = m.addAction("  Rename Title")
        act_ren.triggered.connect(self._rename_input_inline)
        act_rep = m.addAction("  Replace File  (Browse)")
        act_rep.triggered.connect(self._replace_input_file)
        m.addSeparator()
        act_open = m.addAction("  Open in Explorer")
        path = self.tbl.item(self.tbl.currentRow(), 3).text()
        act_open.triggered.connect(lambda: self._open_file_system(path))
        m.addSeparator()
        act_rem = m.addAction("  Remove Input")
        act_rem.triggered.connect(self._remove_inputs)
        m.exec(self.tbl.mapToGlobal(pos))

    def _on_cat_visibility_toggled(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx == 0: return
        is_checked = (item.checkState() == Qt.CheckState.Checked)
        if idx in self.parser.categories:
            self.parser.categories[idx].enabled = is_checked
            self._mark_modified()
            state = "VISIBLE" if is_checked else "HIDDEN (vMix Tab)"
            self.log(f"Category '{self.parser.categories[idx].display_name}' set to {state}")

    def _handle_category_swap(self, idx_a, idx_b):
        if self.parser.swap_categories(idx_a, idx_b):
            self._mark_modified()
            self._refresh_categories()
            self.log(f"Swapped data between slot {idx_a} and {idx_b} safely.")

    def _build_cat_panel(self) -> QWidget:
        p = QWidget()
        p.setMinimumWidth(210)
        p.setMaximumWidth(290)
        p.setStyleSheet(f"background: {C['bg2']}; border-right: 1px solid {C['border']};")
        l = QVBoxLayout(p)
        l.setContentsMargins(10, 12, 10, 10)
        l.setSpacing(8)

        # Panel header
        hdr_row = QHBoxLayout()
        hdr = QLabel("CATEGORIES")
        hdr.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C['dim']}; letter-spacing: 2px;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        l.addLayout(hdr_row)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C['border']};")
        l.addWidget(sep)

        self.cat_list = QListWidget()
        self.cat_list.setFont(QFont("Segoe UI", 10))
        self.cat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cat_list.customContextMenuRequested.connect(self._cat_context_menu)
        l.addWidget(self.cat_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.btn_add_cat = QPushButton("+")
        self.btn_add_cat.setFixedSize(30, 28)
        self.btn_add_cat.setToolTip("Add category")
        self.btn_add_cat.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_green']}; border: 1px solid {C['border2']}; "
            f"border-radius: 3px; font-size: 14px; font-weight: 700;"
        )
        self.btn_ren_cat = QPushButton("✎")
        self.btn_ren_cat.setFixedSize(30, 28)
        self.btn_ren_cat.setToolTip("Rename category")
        self.btn_ren_cat.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_yellow']}; border: 1px solid {C['border2']}; border-radius: 3px;"
        )
        self.btn_del_cat = QPushButton("✕")
        self.btn_del_cat.setFixedSize(30, 28)
        self.btn_del_cat.setToolTip("Delete category")
        self.btn_del_cat.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_red']}; border: 1px solid {C['border2']}; border-radius: 3px;"
        )
        for b in [self.btn_add_cat, self.btn_ren_cat, self.btn_del_cat]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        l.addLayout(btn_row)

        self.cat_stat = QLabel("")
        self.cat_stat.setFont(QFont("Segoe UI", 8))
        self.cat_stat.setStyleSheet(f"color:{C['dim2']}; font-size:8px; margin-top: 2px;")
        l.addWidget(self.cat_stat)
        return p

    def _build_right_panel(self) -> QWidget:
        p = QWidget()
        l = QVBoxLayout(p)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        self.tabs = QTabWidget()
        l.addWidget(self.tabs)

        self.tabs.addTab(self._build_input_tab(), "  Inputs  ")

        self.transform_w = CategoryTransformWidget()
        self.transform_w.request_swap.connect(self._handle_category_swap)
        self.tabs.addTab(self.transform_w, "  Transform  ")

        self.folder_w = FolderImportWidget()
        self.folder_w.import_requested.connect(self._on_folder_bulk_import)
        self.tabs.addTab(self.folder_w, "  Folder Import  ")

        self.tabs.addTab(self._build_file_tab(), "  File Import  ")

        self.reset_w = FactoryResetWidget()
        self.reset_w.reset_triggered.connect(self._handle_factory_reset)
        self.tabs.addTab(self.reset_w, "  Factory Reset  ")

        self.catimport_w = CategoryImportWidget()
        self.catimport_w.structure_ready.connect(self._on_cat_structure)
        self.tabs.addTab(self.catimport_w, "  Category Import  ")

        self.export_w = CategoryExportWidget()
        self.export_w.parser_ref = self.parser
        self.tabs.addTab(self.export_w, "  Factory Export  ")

        return p

    def _build_input_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(12, 12, 12, 8)
        l.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        self.lbl_cat = QLabel("Select a category")
        self.lbl_cat.setFont(QFont("Segoe UI Semibold", 12, QFont.Weight.DemiBold))
        self.lbl_cat.setStyleSheet(f"color: {C['text']}; letter-spacing: 0.3px;")

        self.lbl_cnt = QLabel("")
        self.lbl_cnt.setFont(QFont("Segoe UI", 9))
        self.lbl_cnt.setStyleSheet(f"color: {C['dim']}; margin-left: 6px;")

        self.btn_add_inp = QPushButton("  Add Files")
        self.btn_add_inp.setFixedHeight(32)
        self.btn_add_inp.setFont(QFont("Segoe UI", 9))
        self.btn_add_inp.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_green']}; border: 1px solid {C['r_green']}; "
            f"border-radius: 3px; padding: 0 10px;"
        )
        self.btn_add_inp.clicked.connect(self._add_inputs_dialog)

        self.btn_rem_inp = QPushButton("  Remove")
        self.btn_rem_inp.setFixedHeight(32)
        self.btn_rem_inp.setFont(QFont("Segoe UI", 9))
        self.btn_rem_inp.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_red']}; border: 1px solid {C['r_red']}; "
            f"border-radius: 3px; padding: 0 10px;"
        )
        self.btn_rem_inp.clicked.connect(self._remove_inputs)

        self.btn_mov_inp = QPushButton("  Move To…")
        self.btn_mov_inp.setFixedHeight(32)
        self.btn_mov_inp.setFont(QFont("Segoe UI", 9))
        self.btn_mov_inp.setStyleSheet(
            f"background: {C['bg3']}; color: {C['r_cyan']}; border: 1px solid {C['r_cyan']}; "
            f"border-radius: 3px; padding: 0 10px;"
        )
        self.btn_mov_inp.clicked.connect(self._move_inputs)

        hdr.addWidget(self.lbl_cat)
        hdr.addWidget(self.lbl_cnt)
        hdr.addStretch()
        for b in [self.btn_add_inp, self.btn_rem_inp, self.btn_mov_inp]:
            hdr.addWidget(b)
        l.addLayout(hdr)

        # Thin separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C['border']};")
        l.addWidget(sep)

        # Table
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(['#', 'Title', 'Type', 'File Path', '⌂', 'Key'])
        self.tbl.setItemDelegateForColumn(1, BigEditorDelegate(self.tbl))
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._tbl_context_menu)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tbl.setSortingEnabled(True)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(44)

        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);  self.tbl.setColumnWidth(0, 48)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);  self.tbl.setColumnWidth(2, 76)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed);  self.tbl.setColumnWidth(4, 44)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive); self.tbl.setColumnWidth(5, 110)

        l.addWidget(self.tbl)
        return w

    def _build_file_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(10)

        info = QLabel("Select individual files to add to the currently selected category.")
        info.setFont(QFont("Segoe UI", 9))
        info.setStyleSheet(f"color:{C['dim']};")
        l.addWidget(info)

        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Consolas", 9))
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        l.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_b = QPushButton("  Browse Files")
        btn_b.setFixedHeight(34)
        btn_b.clicked.connect(self._browse_files)
        btn_c = QPushButton("  Clear")
        btn_c.setFixedHeight(34)
        btn_c.clicked.connect(self.file_list.clear)
        btn_a = QPushButton("  Add to Category")
        btn_a.setFixedHeight(34)
        btn_a.setFont(QFont("Segoe UI Semibold", 9, QFont.Weight.DemiBold))
        btn_a.setStyleSheet(
            f"background: {C['r_blue']}; color: #fff; border: none; border-radius: 3px; "
            f"font-weight: 700; padding: 0 14px;"
        )
        btn_a.clicked.connect(self._add_listed_files)
        btn_row.addWidget(btn_b)
        btn_row.addWidget(btn_c)
        btn_row.addStretch()
        btn_row.addWidget(btn_a)
        l.addLayout(btn_row)
        return w

    def _build_log_panel(self) -> QWidget:
        p = QWidget()
        p.setMaximumHeight(148)
        p.setStyleSheet(f"background: {C['bg']}; border-top: 1px solid {C['border']};")
        pl = QVBoxLayout(p)
        pl.setContentsMargins(10, 6, 10, 6)
        pl.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("ACTIVITY LOG")
        hdr.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C['dim2']}; letter-spacing: 2px;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        pl.addLayout(hdr_row)

        self.log_w = LogWidget()
        pl.addWidget(self.log_w)
        return p

    def _open_file_system(self, file_path):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File does not exist:\n{file_path}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", file_path])
            else:
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            self.log(f"Could not open file: {e}", "ERROR")

    # ── Connections ────────────────────────────────────────────────────────────
    def _connect(self):
        self.act_new.triggered.connect(self._new)
        self.act_open.triggered.connect(self._open)
        self.act_save.triggered.connect(self._save)
        self.act_saveas.triggered.connect(self._save_as)
        self.act_expjson.triggered.connect(self._export_json)
        self.act_expcsv.triggered.connect(self._export_csv)
        self.cat_list.currentItemChanged.connect(self._on_cat_changed)
        self.cat_list.itemDoubleClicked.connect(self._rename_category)
        self.btn_add_cat.clicked.connect(self._add_category)
        self.btn_ren_cat.clicked.connect(self._rename_category)
        self.btn_del_cat.clicked.connect(self._delete_category)
        self.search.textChanged.connect(self._filter_inputs)
        self.tbl.itemChanged.connect(self._on_tbl_item_changed)
        self.cat_list.itemChanged.connect(self._on_cat_visibility_toggled)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def log(self, msg, level="INFO"): self.log_w.log(msg, level)

    def _mark_modified(self):
        self.modified = True
        title = f"{APP_NAME}  v{APP_VERSION}"
        if self.parser.file_path:
            title += f"  —  {Path(self.parser.file_path).name}  ●"
        self.setWindowTitle(title)

    def _current_cat_idx(self) -> Optional[int]:
        item = self.cat_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _get_selected_inputs(self) -> List[VmixInput]:
        if not self.current_cat: return []
        rows = sorted(set(i.row() for i in self.tbl.selectedItems()))
        result = []
        for r in rows:
            ki = self.tbl.item(r, 4)
            if ki:
                key = ki.text()
                for inp in self.current_cat.inputs:
                    if inp.key == key: result.append(inp); break
        return result

    # ── Category ops ───────────────────────────────────────────────────────────
    def _refresh_categories(self):
        self.cat_list.blockSignals(True)
        prev_idx = self._current_cat_idx()
        self.cat_list.clear()

        # Rainbow colors cycle for category items
        rb = [C['r_red'], C['r_orange'], C['r_yellow'], C['r_green'],
              C['r_cyan'], C['r_blue'], C['r_violet'], C['r_pink']]

        for i, cat in enumerate(sorted(self.parser.categories.values(), key=lambda c: c.index)):
            count_str = f"  ({cat.count()})" if cat.count() > 0 else ""
            display_text = f"  {cat.display_name}{count_str}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cat.index)

            if cat.index == 0:
                item.setForeground(QColor(C['text']))
                item.setFont(QFont("Segoe UI Semibold", 10, QFont.Weight.DemiBold))
            else:
                col = QColor(rb[i % len(rb)]) if cat.enabled else QColor(C['dim2'])
                item.setForeground(col)
                item.setFont(QFont("Segoe UI", 10))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if cat.enabled else Qt.CheckState.Unchecked)

            self.cat_list.addItem(item)
            if cat.index == prev_idx:
                self.cat_list.setCurrentItem(item)

        self.cat_list.blockSignals(False)
        self.transform_w.refresh_lists(self.parser.categories)
        self.export_w.refresh_categories(self.parser.categories)

    def _on_cat_changed(self, cur, _):
        if cur is None:
            self.current_cat = None
            self.tbl.setRowCount(0)
            return
        idx = cur.data(Qt.ItemDataRole.UserRole)
        self.current_cat = self.parser.categories.get(idx)
        self._refresh_inputs()

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            try:
                cat = self.parser.add_category(name.strip())
                self._refresh_categories()
                self._mark_modified()
                self.log(f"Added category [{cat.index}] '{cat.display_name}'", "SUCCESS")
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _rename_category(self, *_):
        idx = self._current_cat_idx()
        if idx is None or idx == 0: return
        cat = self.parser.categories[idx]
        curr_display = "" if cat.name == "Empty Cat" else cat.name
        name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=curr_display)
        if ok:
            new_name = name.strip()
            if not new_name:
                cat.name = "Empty Cat"
                cat.enabled = False
                self.log(f"Category {idx} cleared and disabled.")
            else:
                cat.name = new_name
                if not cat.enabled:
                    cat.enabled = True
                self.log(f"Renamed category {idx} to '{new_name}'")
            self._refresh_categories()
            self._mark_modified()

    def _delete_category(self):
        idx = self._current_cat_idx()
        if idx is None: return
        cat = self.parser.categories[idx]
        if cat.count() > 0:
            other = {str(c.index): c.display_name for c in self.parser.categories.values() if c.index != idx}
            if not other:
                QMessageBox.warning(self, "Error", "Cannot delete the only category.")
                return
            choices = list(other.keys())
            choice, ok = QInputDialog.getItem(self, "Move Inputs", f"Move {cat.count()} inputs to:",
                                               [f"[{k}] {other[k]}" for k in choices], 0, False)
            if not ok: return
            move_to = int(choices[[f"[{k}] {other[k]}" for k in choices].index(choice)])
        else:
            r = QMessageBox.question(self, "Delete", f"Delete category '{cat.display_name}'?")
            if r != QMessageBox.StandardButton.Yes: return
            move_to = -1
        self.parser.remove_category(idx, move_to if move_to != -1 else idx)
        self.current_cat = None
        self._refresh_categories()
        self._mark_modified()
        self.log(f"Deleted category [{idx}] '{cat.display_name}'", "WARNING")

    def _cat_context_menu(self, pos):
        item = self.cat_list.itemAt(pos)
        if not item: return
        m = QMenu(self)
        m.addAction("  Rename", self._rename_category)
        m.addAction("  Delete", self._delete_category)
        m.exec(self.cat_list.mapToGlobal(pos))

    # ── Input ops ──────────────────────────────────────────────────────────────
    def _refresh_inputs(self):
        if not self.current_cat:
            self.tbl.setRowCount(0)
            self.lbl_cat.setText("Select a category")
            self.lbl_cnt.setText("")
            return

        self.lbl_cat.setText(f"  {self.current_cat.display_name}")
        self.lbl_cnt.setText(f"— {self.current_cat.count()} inputs")

        self.tbl.blockSignals(True)
        self.tbl.setSortingEnabled(False)

        flt = self.search.text().lower()
        inputs = [i for i in self.current_cat.inputs
                  if not flt or flt in i.original_title.lower() or flt in i.file_path.lower()]

        self.tbl.setRowCount(len(inputs))

        type_colors = {
            'Video': C['r_blue'], 'Image': C['r_green'],
            'Audio': C['r_violet'], 'Title': C['r_yellow'],
        }

        for r, inp in enumerate(inputs):
            # Col 0: Number
            num_item = QTableWidgetItem(str(r + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setForeground(QColor(C['dim']))
            num_item.setFont(QFont("Consolas", 9))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 0, num_item)

            # Col 1: Title
            title_item = QTableWidgetItem(inp.original_title)
            title_item.setFont(QFont("Segoe UI", 10))
            title_item.setForeground(QColor(C['text']))
            self.tbl.setItem(r, 1, title_item)

            # Col 2: Type
            ti = QTableWidgetItem(inp.type_name)
            ti.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ti.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            col = type_colors.get(inp.type_name, C['dim'])
            ti.setForeground(QColor(col))
            ti.setFlags(ti.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, ti)

            # Col 3: File Path
            fp_item = QTableWidgetItem(inp.file_path)
            fp_item.setFont(QFont("Consolas", 8))
            fp_item.setForeground(QColor(C['dim']))
            self.tbl.setItem(r, 3, fp_item)

            # Col 4: Open button
            btn_open = QPushButton("⌂")
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setFont(QFont("Segoe UI", 11))
            btn_open.setStyleSheet(
                f"QPushButton {{ border: none; background: transparent; color: {C['r_cyan']}; }}"
                f"QPushButton:hover {{ color: white; }}"
            )
            btn_open.clicked.connect(lambda ch, p=inp.file_path: self._open_file_system(p))
            self.tbl.setCellWidget(r, 4, btn_open)

            # Col 5: Key
            ki = QTableWidgetItem(inp.key[:12] + "…" if len(inp.key) > 12 else inp.key)
            ki.setData(Qt.ItemDataRole.UserRole, inp.key)
            ki.setFont(QFont("Consolas", 7))
            ki.setForeground(QColor(C['dim2']))
            ki.setFlags(ki.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 5, ki)

        self.tbl.setSortingEnabled(True)
        self.tbl.blockSignals(False)

    def _filter_inputs(self): self._refresh_inputs()

    def _on_tbl_item_changed(self, item):
        if item.column() not in (1, 3): return
        r = item.row()
        ki = self.tbl.item(r, 4)
        if not ki: return
        key = ki.data(Qt.ItemDataRole.UserRole) or ki.text().replace("…", "")
        inp = next((i for i in (self.current_cat.inputs if self.current_cat else []) if i.key.startswith(key[:12])), None)
        if not inp: return
        if item.column() == 1: inp.original_title = item.text()
        elif item.column() == 3: inp.file_path = item.text()
        self._mark_modified()

    def _add_inputs_dialog(self):
        if not self.current_cat:
            QMessageBox.warning(self, "No Category", "Please select a category first.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Media Files", "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav *.aac *.flac);;All Files (*)")
        if files: self._add_files_to_current(files)

    def _add_files_to_current(self, entries: List[str]):
        if not self.current_cat:
            QMessageBox.warning(self, "No Category", "Select a category first.")
            return
        added = 0
        for path in entries:
            path = os.path.normpath(path.strip())
            if os.path.isdir(path):
                files = FileScanner.scan(path, recursive=False)
                for fp in files:
                    self.parser.add_input(self.current_cat.index, fp)
                    added += 1
            elif os.path.isfile(path):
                self.parser.add_input(self.current_cat.index, path)
                added += 1
            else:
                self.parser.add_input_title_only(self.current_cat.index, path)
                added += 1
        self._refresh_inputs()
        self._refresh_categories()
        self._mark_modified()
        self.log(f"Added {added} input(s) to '{self.current_cat.display_name}'", "SUCCESS")

    def _remove_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        r = QMessageBox.question(self, "Remove", f"Remove {len(inputs)} input(s)?")
        if r != QMessageBox.StandardButton.Yes: return
        for inp in inputs: self.parser.remove_input(inp)
        self.parser.reorder(self.current_cat.index)
        self._refresh_inputs()
        self._refresh_categories()
        self._mark_modified()
        self.log(f"Removed {len(inputs)} input(s)", "WARNING")

    def _move_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        choices = {str(c.index): c.display_name for c in self.parser.categories.values()
                   if c.index != self.current_cat.index}
        if not choices:
            QMessageBox.information(self, "Move", "No other categories available.")
            return
        keys = list(choices.keys())
        labels = [f"[{k}] {choices[k]}" for k in keys]
        choice, ok = QInputDialog.getItem(self, "Move Inputs", "Move to:", labels, 0, False)
        if not ok: return
        target = int(keys[labels.index(choice)])
        for inp in inputs:
            self.parser.remove_input(inp)
            inp.category = target
            inp.position = max((i.position for i in self.parser.categories[target].inputs), default=-1) + 1
            self.parser.categories[target].inputs.append(inp)
        self._refresh_inputs()
        self._refresh_categories()
        self._mark_modified()
        self.log(f"Moved {len(inputs)} input(s) to [{target}]", "SUCCESS")

    # ── Import handlers ────────────────────────────────────────────────────────
    def _on_folder_files(self, files): self._add_files_to_current(files); self.tabs.setCurrentIndex(0)
    def _on_script_entries(self, entries): self._add_files_to_current(entries); self.tabs.setCurrentIndex(0)

    def _on_cat_structure(self, structure: List[Tuple[str, List[str]]]):
        added_cats, added_inputs = 0, 0
        for folder_name, files in structure:
            existing = next((c for c in self.parser.categories.values()
                             if c.display_name.lower() == folder_name.lower()), None)
            if existing:
                cat = existing
            else:
                try:
                    cat = self.parser.add_category(folder_name)
                    added_cats += 1
                except ValueError:
                    self.log(f"Category limit reached, skipping '{folder_name}'", "WARNING")
                    continue
            for fp in files:
                self.parser.add_input(cat.index, fp)
                added_inputs += 1
        self._refresh_categories()
        self._mark_modified()
        self.log(f"Imported {added_cats} categories, {added_inputs} inputs", "SUCCESS")
        self.tabs.setCurrentIndex(0)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav);;All Files (*)")
        type_icons = {'Video': '▶', 'Image': '◼', 'Audio': '♪', 'Unknown': '•'}
        for fp in files:
            item = QListWidgetItem(f"  {type_icons.get(FileScanner.detect(fp), '•')}  {Path(fp).name}")
            item.setToolTip(fp)
            self.file_list.addItem(item)

    def _add_listed_files(self):
        files = [self.file_list.item(i).toolTip() for i in range(self.file_list.count())]
        if files:
            self._add_files_to_current(files)
            self.tabs.setCurrentIndex(0)

    # ── File operations ────────────────────────────────────────────────────────
    def _check_save(self) -> bool:
        if not self.modified: return True
        r = QMessageBox.question(self, "Unsaved Changes", "Save changes before proceeding?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Cancel: return False
        if r == QMessageBox.StandardButton.Save: return self._save()
        return True

    def _new(self):
        if not self._check_save(): return
        self.parser.create_new()
        self.current_cat = None
        self._refresh_categories()
        self.modified = False
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.file_lbl.setText("  New file")
        self.log("New production created", "SUCCESS")

    def _open(self):
        if not self._check_save(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open .vmix File", "", "vMix Files (*.vmix);;All Files (*)")
        if not path: return
        if self.parser.load(path):
            self.current_cat = None
            self._refresh_categories()
            self.modified = False
            self.setWindowTitle(f"{APP_NAME}  —  {Path(path).name}")
            self.file_lbl.setText(f"  {Path(path).name}")
            n = sum(c.count() for c in self.parser.categories.values())
            self.log(f"Loaded '{Path(path).name}'  —  {len(self.parser.categories)} categories, {n} inputs", "SUCCESS")
        else:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{path}")

    def _save(self) -> bool:
        if not self.parser.file_path: return self._save_as()
        if self.parser.save(self.parser.file_path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME}  —  {Path(self.parser.file_path).name}")
            self.log(f"Saved '{Path(self.parser.file_path).name}'", "SUCCESS")
            return True
        QMessageBox.critical(self, "Error", "Save failed.")
        return False

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save .vmix File", "", "vMix Files (*.vmix)")
        if not path: return False
        if not path.endswith('.vmix'): path += '.vmix'
        if self.parser.save(path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME}  —  {Path(path).name}")
            self.file_lbl.setText(f"  {Path(path).name}")
            self.log(f"Saved as '{Path(path).name}'", "SUCCESS")
            return True
        QMessageBox.critical(self, "Error", "Save failed.")
        return False

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if not path: return
        if not path.endswith('.json'): path += '.json'
        self.parser.export_json(path)
        self.log(f"Exported JSON: {Path(path).name}", "SUCCESS")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path: return
        if not path.endswith('.csv'): path += '.csv'
        self.parser.export_csv(path)
        self.log(f"Exported CSV: {Path(path).name}", "SUCCESS")

    def closeEvent(self, event):
        if self._check_save(): event.accept()
        else: event.ignore()

    def _apply_style(self):
        self.setStyleSheet(f"""
        /* ── Global Reset ─────────────────────────────────────────────── */
        QMainWindow, QWidget {{
            background: {C['bg']};
            color: {C['text']};
            font-family: "Segoe UI";
            font-size: 10px;
        }}

        /* ── Toolbar ──────────────────────────────────────────────────── */
        QToolBar {{
            background: {C['bg2']};
            border-bottom: 1px solid {C['border']};
            padding: 0 4px;
            spacing: 2px;
        }}
        QToolButton {{
            color: {C['text2']};
            background: transparent;
            border: 1px solid transparent;
            border-radius: 3px;
            padding: 5px 12px;
            font-family: "Segoe UI";
            font-size: 10px;
            letter-spacing: 0.3px;
        }}
        QToolButton:hover {{
            background: {C['bg3']};
            border-color: {C['border2']};
            color: {C['text']};
        }}
        QToolButton:pressed {{
            background: {C['bg4']};
        }}
        QToolBar::separator {{
            background: {C['border']};
            width: 1px;
            margin: 8px 4px;
        }}

        /* ── Category List ─────────────────────────────────────────────── */
        QListWidget {{
            background: {C['bg2']};
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            padding: 9px 8px;
            border-bottom: 1px solid {C['border']};
        }}
        QListWidget::item:selected {{
            background: {C['bg3']};
            border-left: 3px solid {C['r_blue']};
        }}
        QListWidget::item:hover:!selected {{
            background: {C['bg3']};
        }}

        /* ── Table ─────────────────────────────────────────────────────── */
        QTableWidget {{
            background: {C['bg2']};
            border: none;
            gridline-color: {C['border']};
            outline: none;
        }}
        QTableWidget::item {{
            padding: 4px 8px;
            border-bottom: 1px solid {C['border']};
        }}
        QTableWidget::item:selected,
        QTableWidget::item:selected:active,
        QTableWidget::item:selected:!active {{
            background-color: {C['bg3']} !important;
            color: {C['text']} !important;
            border-left: 2px solid {C['r_blue']};
        }}
        QTableWidget::item:alternate {{
            background: {C['alt']};
        }}
        QTableWidget::item:alternate:selected {{
            background-color: {C['bg3']} !important;
        }}
        QHeaderView {{
            background: {C['bg']};
        }}
        QHeaderView::section {{
            background: {C['bg']};
            color: {C['dim']};
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {C['border2']};
            border-right: 1px solid {C['border']};
            font-family: "Segoe UI";
            font-size: 8px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }}

        /* ── Tabs ──────────────────────────────────────────────────────── */
        QTabWidget::pane {{
            background: {C['bg2']};
            border: none;
            border-top: 1px solid {C['border']};
        }}
        QTabBar {{
            background: {C['bg']};
        }}
        QTabBar::tab {{
            background: {C['bg']};
            color: {C['dim']};
            padding: 9px 6px;
            margin-right: 1px;
            border-bottom: 2px solid transparent;
            font-family: "Segoe UI";
            font-size: 9px;
            letter-spacing: 0.3px;
        }}
        QTabBar::tab:selected {{
            background: {C['bg']};
            color: {C['text']};
            border-bottom: 2px solid {C['r_blue']};
        }}
        QTabBar::tab:hover:!selected {{
            color: {C['text2']};
            border-bottom: 2px solid {C['border2']};
        }}

        /* ── Buttons ───────────────────────────────────────────────────── */
        QPushButton {{
            background: {C['bg3']};
            color: {C['text2']};
            border: 1px solid {C['border2']};
            border-radius: 3px;
            padding: 6px 14px;
            font-family: "Segoe UI";
            font-size: 9px;
        }}
        QPushButton:hover {{
            background: {C['bg4']};
            color: {C['text']};
            border-color: {C['border3']};
        }}
        QPushButton:pressed {{
            background: {C['bg5']};
        }}
        QPushButton:disabled {{
            color: {C['dim2']};
            border-color: {C['border']};
        }}

        /* ── Inputs & Editors ──────────────────────────────────────────── */
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background: {C['bg4']};
            color: {C['text']};
            border: 1px solid {C['border2']};
            border-radius: 3px;
            padding: 5px 8px;
            font-family: "Segoe UI";
            selection-background-color: {C['r_blue']};
            selection-color: white;
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border-color: {C['border3']};
        }}
        QLineEdit::placeholder {{
            color: {C['dim2']};
        }}

        /* ── Group Box ─────────────────────────────────────────────────── */
        QGroupBox {{
            background: {C['bg2']};
            border: 1px solid {C['border']};
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 8px;
            color: {C['dim']};
            font-family: "Segoe UI";
            font-size: 8px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            left: 10px;
        }}

        /* ── Scrollbars ─────────────────────────────────────────────────── */
        QScrollBar:vertical {{
            background: {C['bg']};
            width: 6px;
            margin: 0;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {C['border2']};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {C['border3']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {C['bg']};
            height: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal {{
            background: {C['border2']};
            border-radius: 3px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}

        /* ── Context Menu ───────────────────────────────────────────────── */
        QMenu {{
            background: {C['bg3']};
            color: {C['text']};
            border: 1px solid {C['border2']};
            border-radius: 4px;
            padding: 4px 0;
            font-family: "Segoe UI";
            font-size: 10px;
        }}
        QMenu::item {{
            padding: 7px 20px;
        }}
        QMenu::item:selected {{
            background: {C['bg4']};
            color: {C['text']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {C['border']};
            margin: 4px 8px;
        }}

        /* ── Progress Bar ───────────────────────────────────────────────── */
        QProgressBar {{
            border: none;
            border-radius: 3px;
            background: {C['bg3']};
            text-align: center;
            color: {C['text']};
            font-size: 9px;
        }}
        QProgressBar::chunk {{
            background: {C['r_blue']};
            border-radius: 3px;
        }}

        /* ── Splitter ───────────────────────────────────────────────────── */
        QSplitter::handle {{
            background: {C['border']};
        }}
        QSplitter::handle:hover {{
            background: {C['r_blue']};
        }}

        /* ── Tree Widget ────────────────────────────────────────────────── */
        QTreeWidget {{
            background: {C['bg2']};
            border: 1px solid {C['border']};
            border-radius: 3px;
            outline: none;
            font-family: "Segoe UI";
        }}
        QTreeWidget::item {{
            padding: 5px 4px;
        }}
        QTreeWidget::item:selected {{
            background: {C['bg3']};
            color: {C['text']};
        }}
        QTreeWidget::branch {{
            background: {C['bg2']};
        }}

        /* ── Input dialog / Modal ───────────────────────────────────────── */
        QDialog {{
            background: {C['bg2']};
            color: {C['text']};
        }}
        QInputDialog QLabel {{
            color: {C['text']};
        }}
        QMessageBox {{
            background: {C['bg2']};
            color: {C['text']};
        }}
        """)


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    # Dark palette to properly seed Fusion style before our QSS takes over
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(C['bg']))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(C['text']))
    palette.setColor(QPalette.ColorRole.Base,            QColor(C['bg2']))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(C['alt']))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(C['bg3']))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(C['text']))
    palette.setColor(QPalette.ColorRole.Text,            QColor(C['text']))
    palette.setColor(QPalette.ColorRole.Button,          QColor(C['bg3']))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(C['text']))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor('#FFFFFF'))
    palette.setColor(QPalette.ColorRole.Link,            QColor(C['r_blue']))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(C['r_blue']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#FFFFFF'))
    app.setPalette(palette)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())