#!/usr/bin/env python3
"""
vMix Script Manager
===================
A PyQt6 application for managing vMix .vmix production files.
Professional Black & White — Cambria typography.
"""

import sys, os, json, csv, uuid, copy, re, logging, shutil, subprocess, platform
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom
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
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QObject, QThread
from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence, QIcon, QPalette

# ── Constants ──────────────────────────────────────────────────────────────────
APP_NAME, APP_VERSION = "vMix Manager", "6"

VIDEO_EXTS = {'.mp4','.avi','.mov','.mkv','.wmv','.flv','.m4v','.webm','.ts','.mts'}
IMAGE_EXTS = {'.jpg','.jpeg','.png','.bmp','.gif','.tiff','.tga','.webp'}
AUDIO_EXTS = {'.mp3','.wav','.aac','.flac','.ogg','.wma','.m4a'}
ALL_MEDIA  = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

INPUT_TYPES = {1:"Image", 0:"Video", 3:"Audio", 6:"Desktop", 7:"NDI", 12:"Title", 20:"Camera"}

DEF_CAT_NAMES = {
    0:"ALL", 1:"Red", 2:"Green", 3:"Orange", 4:"Purple", 5:"Aqua", 6:"Blue",
    7:"Custom1", 8:"Custom2", 9:"Custom3", 10:"Custom4", 11:"Custom5",
    12:"Custom6", 13:"Custom7", 14:"Custom8", 15:"Custom9", 16:"Custom10",
    17:"Custom11", 18:"Custom12", 19:"Custom13", 20:"Custom14", 21:"Custom15", 22:"Custom16"
}

CAT_MAP = {
    1:"Red", 2:"Green", 3:"Orange", 4:"Purple", 5:"Aqua", 6:"Blue",
    7:"Custom1", 8:"Custom2", 9:"Custom3", 10:"Custom4", 11:"Custom5",
    12:"Custom6", 13:"Custom7", 14:"Custom8", 15:"Custom9", 16:"Custom10",
    17:"Custom11", 18:"Custom12", 19:"Custom13", 20:"Custom14", 21:"Custom15", 22:"Custom16"
}

CAT_ID_LOOKUP = {
    "All.Text":0, "Red.Text":1, "Green.Text":2, "Orange.Text":3, "Purple.Text":4,
    "Aqua.Text":5, "Blue.Text":6,
    "Custom1.Text":7,  "Custom2.Text":8,  "Custom3.Text":9,  "Custom4.Text":10,
    "Custom5.Text":11, "Custom6.Text":12, "Custom7.Text":13, "Custom8.Text":14,
    "Custom9.Text":15, "Custom10.Text":16,"Custom11.Text":17,"Custom12.Text":18,
    "Custom13.Text":19,"Custom14.Text":20,"Custom15.Text":21,"Custom16.Text":22
}
CAT_ENABLED_LOOKUP = {k.replace(".Text",".Enabled"):v for k,v in CAT_ID_LOOKUP.items()}

# ── Pure Black & White Palette ─────────────────────────────────────────────────
C = {
    'bg':      '#0C0C0C',
    'bg2':     '#141414',
    'bg3':     '#1E1E1E',
    'bg4':     '#272727',
    'bg5':     '#303030',
    'text':    '#F4F4F4',
    'text2':   '#D0D0D0',
    'dim':     '#909090',
    'dim2':    '#505050',
    'bd':      '#282828',
    'bd2':     '#3C3C3C',
    'bd3':     '#606060',
    'accent':  '#FFFFFF',
    'acc2':    '#E0E0E0',
    'ok':      '#D4D4D4',
    'warn':    '#A8A8A8',
    'err':     '#888888',
    'hi':      '#242424',
    'alt':     '#111111',
}

# ── Cambria font helpers ───────────────────────────────────────────────────────
def F(size: int, bold: bool = False, italic: bool = False) -> QFont:
    f = QFont("Cambria", size)
    f.setBold(bold)
    f.setItalic(italic)
    return f

def F_MONO(size: int) -> QFont:
    return QFont("Courier New", size)


# ── Data Models ────────────────────────────────────────────────────────────────
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
        name_map, enabled_map = {}, {}
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
                name, is_enabled = "ALL", True
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
            extra_attrs={k:v for k,v in a.items() if k not in {'Key','OriginalTitle','Type','Category','Position','XML'}}
        )

    def swap_categories(self, idx_a: int, idx_b: int):
        if idx_a not in self.categories or idx_b not in self.categories: return False
        self.categories[idx_a].name, self.categories[idx_b].name = \
            self.categories[idx_b].name, self.categories[idx_a].name
        self.categories[idx_a].inputs, self.categories[idx_b].inputs = \
            self.categories[idx_b].inputs, self.categories[idx_a].inputs
        for inp in self.categories[idx_a].inputs: inp.category = idx_a
        for inp in self.categories[idx_b].inputs: inp.category = idx_b
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
                    if el.tag in ('Version','ZoomManager','Input'): continue
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
            'Type':str(inp.input_type), 'Position':str(inp.position), 'State':'1',
            'OriginalTitle':inp.original_title, 'Key':inp.key,
            'Category':str(inp.category), 'AspectRatio':'100',
            'VideoShader_Alpha':'1', 'VideoShader_White':'1',
            'VideoShader_ClippingX2':'1', 'VideoShader_ClippingY2':'1',
            'Positions':self.default_pos
        }
        if hasattr(inp, 'xml_payload') and inp.xml_payload:
            attrs['XML'] = inp.xml_payload
        attrs.update(inp.extra_attrs)
        el = ET.Element('Input', attrib={k:str(v) for k,v in attrs.items() if v is not None})
        if inp.file_path: el.text = inp.file_path
        return el

    def create_new(self):
        self.categories = {i: VmixCategory(index=i, name="" if i>0 else "ALL") for i in range(23)}
        self._orig_root = None
        self.file_path = ""

    def add_category(self, name: str) -> VmixCategory:
        idx = next((i for i in range(1,23) if not self.categories[i].name), 1)
        self.categories[idx].name = name
        return self.categories[idx]

    def add_input(self, cat_idx: int, file_path: str):
        pos = len(self.categories[cat_idx].inputs)
        inp = VmixInput(
            key=str(uuid.uuid4()), original_title=Path(file_path).name,
            input_type=0 if Path(file_path).suffix.lower() in VIDEO_EXTS else 1,
            category=cat_idx, position=pos, file_path=file_path
        )
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


# ── Delegate ───────────────────────────────────────────────────────────────────
class BigEditorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setMinimumHeight(46)
        editor.setFont(F(12))
        editor.setStyleSheet(
            f"background:{C['bg4']};color:{C['text']};"
            f"border:2px solid {C['bd3']};border-radius:2px;padding:4px 10px;"
        )
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect; rect.setHeight(46); editor.setGeometry(rect)


# ── Export Worker ──────────────────────────────────────────────────────────────
class ExportWorker(QObject):
    progress_updated = pyqtSignal(int, str)
    finished         = pyqtSignal(int, int)
    log_msg          = pyqtSignal(str, str)

    def __init__(self, categories, destination_root):
        super().__init__()
        self.categories       = categories
        self.destination_root = destination_root

    def run(self):
        success_count = error_count = 0
        total_files = sum(len(cat.inputs) for cat in self.categories)
        if total_files == 0:
            self.finished.emit(0, 0); return
        self.log_msg.emit(f"Starting export of {total_files} files...", "INFO")
        for cat in self.categories:
            safe_name  = sanitize_folder_name(cat.display_name)
            target_dir = Path(self.destination_root) / safe_name
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                self.log_msg.emit(f"Could not create folder {safe_name}: {e}", "ERROR")
                error_count += len(cat.inputs); continue
            for inp in cat.inputs:
                src_path = inp.file_path
                if not src_path or not os.path.exists(src_path):
                    self.log_msg.emit(f"Skipping (not found): {inp.original_title}", "WARNING")
                    error_count += 1
                else:
                    try:
                        dest_path = target_dir / Path(src_path).name
                        self.progress_updated.emit(success_count + error_count, Path(src_path).name)
                        shutil.copy2(src_path, dest_path)
                        success_count += 1
                    except Exception as e:
                        self.log_msg.emit(f"Failed: {inp.original_title}: {e}", "ERROR")
                        error_count += 1
        self.finished.emit(success_count, error_count)


# ── Log Widget ─────────────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(130)
        self.setFont(F_MONO(10))

    def log(self, msg: str, level="INFO"):
        ts  = datetime.now().strftime("%H:%M:%S")
        col = {"INFO":C['text2'],"SUCCESS":C['accent'],"WARNING":C['warn'],"ERROR":C['dim']}.get(level, C['text2'])
        self.append(
            f'<span style="color:{C["dim2"]}">[{ts}]</span>&nbsp;'
            f'<span style="color:{col};font-weight:bold">{level}</span>'
            f'<span style="color:{C["text2"]}"> &mdash; {msg}</span>'
        )
        self.moveCursor(QTextCursor.MoveOperation.End)


# ── Export Widget ──────────────────────────────────────────────────────────────
class CategoryExportWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser_ref = None
        self.thread = self.worker = None
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 22, 22, 22)
        l.setSpacing(16)

        hdr = QLabel("Factory Export")
        hdr.setFont(F(17, bold=True))
        hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        sub = QLabel("Copy selected categories to organised subfolders on disk.")
        sub.setFont(F(12, italic=True))
        sub.setStyleSheet(f"color:{C['dim']};")
        l.addWidget(sub)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        lbl1 = QLabel("Select categories to export:")
        lbl1.setFont(F(12, bold=True))
        lbl1.setStyleSheet(f"color:{C['text2']};")
        l.addWidget(lbl1)

        self.cat_list = QListWidget()
        self.cat_list.setFont(F(12))
        self.cat_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        l.addWidget(self.cat_list)

        lbl2 = QLabel("Destination root folder:")
        lbl2.setFont(F(12, bold=True))
        lbl2.setStyleSheet(f"color:{C['text2']};")
        l.addWidget(lbl2)

        path_row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setFont(F(12))
        self.dest_edit.setFixedHeight(40)
        self.dest_edit.setPlaceholderText("Browse to select destination folder...")
        btn_browse = QPushButton("Browse...")
        btn_browse.setFont(F(12)); btn_browse.setFixedHeight(40)
        btn_browse.clicked.connect(self._browse_dest)
        path_row.addWidget(self.dest_edit); path_row.addWidget(btn_browse)
        l.addLayout(path_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar{{border:none;background:{C['bg3']};border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:2px;}}"
        )
        self.progress_bar.hide()
        l.addWidget(self.progress_bar)

        self.status_log = LogWidget()
        l.addWidget(self.status_log)

        self.btn_export = QPushButton("Start Export")
        self.btn_export.setFont(F(14, bold=True))
        self.btn_export.setFixedHeight(48)
        self.btn_export.setStyleSheet(
            f"background:{C['accent']};color:#000000;border:none;border-radius:3px;"
        )
        self.btn_export.clicked.connect(self._start_export)
        l.addWidget(self.btn_export)

    def refresh_categories(self, categories):
        self.cat_list.clear()
        for cat in sorted(categories.values(), key=lambda x: x.index):
            if cat.index == 0: continue
            item = QListWidgetItem(f"  [{cat.index:02d}]   {cat.display_name}   ({len(cat.inputs)} items)")
            item.setFont(F(12)); item.setData(Qt.ItemDataRole.UserRole, cat.index)
            self.cat_list.addItem(item)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Root")
        if folder: self.dest_edit.setText(folder)

    def _start_export(self):
        selected_items = self.cat_list.selectedItems()
        dest = self.dest_edit.text()
        if not selected_items:
            QMessageBox.warning(self, "Export", "Please select at least one category."); return
        if not dest or not os.path.isdir(dest):
            QMessageBox.warning(self, "Export", "Please select a valid destination folder."); return
        selected_cats = [self.parser_ref.categories[i.data(Qt.ItemDataRole.UserRole)] for i in selected_items]
        total_files = sum(len(c.inputs) for c in selected_cats)
        if total_files == 0:
            QMessageBox.information(self, "Export", "Selected categories contain no files."); return
        self.btn_export.setEnabled(False)
        self.progress_bar.setMaximum(total_files); self.progress_bar.setValue(0)
        self.progress_bar.show(); self.status_log.clear()
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
        self.progress_bar.setValue(count); self.status_log.log(f"Copying: {filename}")

    def _on_finished(self, success, errors):
        self.btn_export.setEnabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        msg = f"Export Complete\n  Successfully copied : {success}\n  Failed / Missing   : {errors}"
        self.status_log.log(msg, "SUCCESS" if errors == 0 else "WARNING")
        QMessageBox.information(self, "Export Finished", msg)


# ── Folder Import Widget ───────────────────────────────────────────────────────
class FolderImportWidget(QWidget):
    import_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 22, 22, 22); l.setSpacing(16)

        hdr = QLabel("Folder Import")
        hdr.setFont(F(17, bold=True)); hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        sub = QLabel("Queue folders — each becomes a header + media block in the selected category.")
        sub.setFont(F(12, italic=True)); sub.setStyleSheet(f"color:{C['dim']};"); sub.setWordWrap(True)
        l.addWidget(sub)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        queue_gb = QGroupBox("Folder Queue")
        queue_gb.setFont(F(11, bold=True))
        queue_l = QVBoxLayout(queue_gb); queue_l.setSpacing(10)

        self.preview = QListWidget(); self.preview.setFont(F(12))
        queue_l.addWidget(self.preview)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Folder to Queue")
        btn_add.setFont(F(12)); btn_add.setFixedHeight(38)
        btn_add.clicked.connect(self._add_folder_to_queue)
        btn_clr = QPushButton("Clear Queue")
        btn_clr.setFont(F(12)); btn_clr.setFixedHeight(38)
        btn_clr.clicked.connect(self._clear_queue)
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_clr); btn_row.addStretch()
        queue_l.addLayout(btn_row)
        l.addWidget(queue_gb)

        self.btn_import = QPushButton("Start Bulk Import  (Headers @ 200 px)")
        self.btn_import.setFont(F(14, bold=True)); self.btn_import.setFixedHeight(52)
        self.btn_import.setStyleSheet(
            f"background:{C['accent']};color:#000000;border:none;border-radius:3px;"
        )
        self.btn_import.clicked.connect(self._emit_import)
        l.addWidget(self.btn_import)

    def _add_folder_to_queue(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            p = Path(folder); files = FileScanner.scan(folder, recursive=False); files.sort()
            self.queue.append((p.name, files))
            item = QListWidgetItem(f"  {p.name}  —  {len(files)} files")
            item.setFont(F(12)); self.preview.addItem(item)

    def _clear_queue(self): self.queue = []; self.preview.clear()

    def _emit_import(self):
        if not self.queue:
            QMessageBox.warning(self, "Empty Queue", "Add folders to the queue first."); return
        self.import_requested.emit(self.queue); self._clear_queue()


# ── Factory Reset Widget ───────────────────────────────────────────────────────
class FactoryResetWidget(QWidget):
    reset_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 22, 22, 22); l.setSpacing(16)

        hdr = QLabel("Production Management")
        hdr.setFont(F(17, bold=True)); hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        sub = QLabel(
            "Bulk-delete inputs or reset the entire vMix session.\n"
            "Destructive operations cannot be undone — save your file first."
        )
        sub.setFont(F(12, italic=True)); sub.setStyleSheet(f"color:{C['dim']};"); sub.setWordWrap(True)
        l.addWidget(sub)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        group = QGroupBox("Reset Actions")
        group.setFont(F(11, bold=True))
        gl = QVBoxLayout(group); gl.setSpacing(12)

        self.btn_clear_cat = QPushButton("Clear All Inputs in Current Category")
        self.btn_clear_cat.setFont(F(13)); self.btn_clear_cat.setFixedHeight(46)
        self.btn_clear_cat.setStyleSheet(
            f"background:{C['bg3']};color:{C['text']};border:1px solid {C['bd2']};"
            f"border-radius:3px;text-align:left;padding-left:20px;"
        )
        self.btn_clear_cat.clicked.connect(lambda: self.reset_triggered.emit("current"))

        self.btn_wipe_all = QPushButton("Wipe ALL Inputs  (Globally)")
        self.btn_wipe_all.setFont(F(13)); self.btn_wipe_all.setFixedHeight(46)
        self.btn_wipe_all.setStyleSheet(
            f"background:{C['bg3']};color:{C['text2']};border:1px solid {C['bd3']};"
            f"border-radius:3px;text-align:left;padding-left:20px;"
        )
        self.btn_wipe_all.clicked.connect(lambda: self.reset_triggered.emit("all"))

        self.btn_factory = QPushButton("Full Factory Reset  —  Wipe All + Reset Names")
        self.btn_factory.setFont(F(13, bold=True)); self.btn_factory.setFixedHeight(46)
        self.btn_factory.setStyleSheet(
            f"background:{C['dim2']};color:{C['text']};border:1px solid {C['dim']};"
            f"border-radius:3px;text-align:left;padding-left:20px;"
        )
        self.btn_factory.clicked.connect(lambda: self.reset_triggered.emit("session"))

        for b in [self.btn_clear_cat, self.btn_wipe_all, self.btn_factory]:
            gl.addWidget(b)

        l.addWidget(group); l.addStretch()


# ── Category Import Widget ─────────────────────────────────────────────────────
class CategoryImportWidget(QWidget):
    structure_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._structure = []
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 22, 22, 22); l.setSpacing(14)

        hdr = QLabel("Category Import")
        hdr.setFont(F(17, bold=True)); hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        info = QLabel(
            "Select a root folder. Each subfolder becomes a category; files inside become inputs."
        )
        info.setFont(F(12, italic=True)); info.setStyleSheet(f"color:{C['dim']};"); info.setWordWrap(True)
        l.addWidget(info)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setFont(F(12))
        self.path_edit.setFixedHeight(40); self.path_edit.setPlaceholderText("Select root folder...")
        self.path_edit.setReadOnly(True)
        btn_b = QPushButton("Browse..."); btn_b.setFont(F(12)); btn_b.setFixedHeight(40)
        btn_b.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit); path_row.addWidget(btn_b)
        l.addLayout(path_row)

        self.tree = QTreeWidget(); self.tree.setFont(F(11))
        self.tree.setHeaderLabels(['Category / File', 'Type', 'Count'])
        self.tree.header().setFont(F(10, bold=True))
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 90); self.tree.setColumnWidth(2, 60)
        l.addWidget(self.tree)

        btn_row2 = QHBoxLayout()
        self.lbl = QLabel("No folder selected")
        self.lbl.setFont(F(11, italic=True)); self.lbl.setStyleSheet(f"color:{C['dim']};")
        btn_imp = QPushButton("Import All Categories")
        btn_imp.setFont(F(13, bold=True)); btn_imp.setFixedHeight(42)
        btn_imp.setStyleSheet(
            f"background:{C['accent']};color:#000000;border:none;border-radius:3px;padding:0 22px;"
        )
        btn_imp.clicked.connect(self._emit)
        btn_row2.addWidget(self.lbl); btn_row2.addStretch(); btn_row2.addWidget(btn_imp)
        l.addLayout(btn_row2)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if f: self.path_edit.setText(f); self._scan(f)

    def _scan(self, folder):
        self._structure = FileScanner.subfolders(folder)
        self.tree.clear(); total = 0
        for name, files in self._structure:
            ci = QTreeWidgetItem([f"  {name}", "Category", str(len(files))])
            ci.setFont(0, F(12, bold=True)); ci.setFont(1, F(11)); ci.setFont(2, F(11))
            ci.setForeground(0, QColor(C['text'])); ci.setForeground(1, QColor(C['dim']))
            for fp in files[:20]:
                ftype = FileScanner.detect(fp)
                fi = QTreeWidgetItem(ci, [f"    {Path(fp).name}", ftype, ""])
                fi.setFont(0, F(11)); fi.setFont(1, F(10))
                fi.setForeground(0, QColor(C['text2'])); fi.setForeground(1, QColor(C['dim']))
            if len(files) > 20:
                more = QTreeWidgetItem(ci, [f"    ... and {len(files)-20} more", "", ""])
                more.setFont(0, F(10, italic=True)); more.setForeground(0, QColor(C['dim2']))
            self.tree.addTopLevelItem(ci); ci.setExpanded(True); total += len(files)
        self.lbl.setText(f"{len(self._structure)} categories  —  {total} files total")

    def _emit(self):
        if self._structure: self.structure_ready.emit(self._structure)


# ── Category Transform Widget ──────────────────────────────────────────────────
class CategoryTransformWidget(QWidget):
    request_swap = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 22, 22, 22); l.setSpacing(16)

        hdr = QLabel("Category Interchanger")
        hdr.setFont(F(17, bold=True)); hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        desc = QLabel(
            "Select one category from each column, then execute the swap. "
            "All inputs will be relocated to their new slot automatically."
        )
        desc.setFont(F(12, italic=True)); desc.setStyleSheet(f"color:{C['dim']};"); desc.setWordWrap(True)
        l.addWidget(desc)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        cols = QHBoxLayout(); cols.setSpacing(18)

        left_col = QVBoxLayout()
        lbl_a = QLabel("FROM SLOT")
        lbl_a.setFont(F(9, bold=True)); lbl_a.setStyleSheet(f"color:{C['dim']};letter-spacing:2px;")
        self.list_a = QListWidget(); self.list_a.setFont(F(12))
        left_col.addWidget(lbl_a); left_col.addWidget(self.list_a)

        mid_col = QVBoxLayout(); mid_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid_icon = QLabel("⇌"); mid_icon.setFont(F(22))
        mid_icon.setStyleSheet(f"color:{C['dim']};")
        mid_col.addStretch(); mid_col.addWidget(mid_icon, 0, Qt.AlignmentFlag.AlignCenter); mid_col.addStretch()

        right_col = QVBoxLayout()
        lbl_b = QLabel("TO SLOT")
        lbl_b.setFont(F(9, bold=True)); lbl_b.setStyleSheet(f"color:{C['dim']};letter-spacing:2px;")
        self.list_b = QListWidget(); self.list_b.setFont(F(12))
        right_col.addWidget(lbl_b); right_col.addWidget(self.list_b)

        cols.addLayout(left_col); cols.addLayout(mid_col); cols.addLayout(right_col)
        l.addLayout(cols)

        self.btn_swap = QPushButton("Execute Swap")
        self.btn_swap.setFont(F(14, bold=True)); self.btn_swap.setFixedHeight(52)
        self.btn_swap.setStyleSheet(
            f"background:{C['accent']};color:#000000;border:none;border-radius:3px;"
        )
        self.btn_swap.clicked.connect(self._on_swap_clicked)
        l.addWidget(self.btn_swap)

    def refresh_lists(self, categories):
        self.list_a.clear(); self.list_b.clear()
        for cat in sorted([c for c in categories.values() if c.index != 0], key=lambda x: x.index):
            txt = f"  [{cat.index:02d}]   {cat.display_name}   ({len(cat.inputs)} inputs)"
            ia = QListWidgetItem(txt); ia.setFont(F(12)); ia.setData(Qt.ItemDataRole.UserRole, cat.index)
            ib = QListWidgetItem(txt); ib.setFont(F(12)); ib.setData(Qt.ItemDataRole.UserRole, cat.index)
            self.list_a.addItem(ia); self.list_b.addItem(ib)

    def _on_swap_clicked(self):
        sel_a = self.list_a.currentItem(); sel_b = self.list_b.currentItem()
        if not sel_a or not sel_b:
            QMessageBox.warning(self, "Selection Required", "Please select a category from both columns."); return
        idx_a = sel_a.data(Qt.ItemDataRole.UserRole)
        idx_b = sel_b.data(Qt.ItemDataRole.UserRole)
        if idx_a == idx_b:
            QMessageBox.warning(self, "Invalid", "Cannot swap a category with itself."); return
        self.request_swap.emit(idx_a, idx_b)


# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = os.path.join(os.path.abspath("."), "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        if platform.system() == "Windows":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    f"mycompany.vmixmanager.{APP_VERSION}"
                )
            except Exception:
                pass

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
        self.setMinimumSize(1150, 720); self.resize(1400, 860)
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        self._build_toolbar()
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(self._build_cat_panel())
        sp.addWidget(self._build_right_panel())
        sp.setSizes([260, 940]); sp.setStretchFactor(0,0); sp.setStretchFactor(1,1)
        sp.setHandleWidth(1)
        ml.addWidget(sp, 1)
        ml.addWidget(self._build_log_panel())
        self.statusBar().showMessage("Ready")
        self.statusBar().setFont(F(10))
        self.statusBar().setStyleSheet(
            f"background:{C['bg2']};color:{C['dim']};border-top:1px solid {C['bd']};"
        )

    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False)
        tb.setIconSize(QSize(16,16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        tb.setFixedHeight(52)
        self.addToolBar(tb)

        brand = QLabel("   vMix Manager   ")
        brand.setFont(F(16, bold=True))
        brand.setStyleSheet(f"color:{C['text']};letter-spacing:1px;")
        tb.addWidget(brand)

        rule = QWidget(); rule.setFixedSize(1, 28)
        rule.setStyleSheet(f"background:{C['bd2']};")
        tb.addWidget(rule)
        tb.addWidget(QLabel("   "))

        self.act_new     = QAction("New",       self); self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_open    = QAction("Open",      self); self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_save    = QAction("Save",      self); self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_saveas  = QAction("Save As...",self); self.act_saveas.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_expjson = QAction("Export JSON", self)
        self.act_expcsv  = QAction("Export CSV",  self)

        for a in [self.act_new, self.act_open, self.act_save, self.act_saveas]: tb.addAction(a)
        tb.addSeparator()
        for a in [self.act_expjson, self.act_expcsv]: tb.addAction(a)
        tb.addSeparator()

        lbl_s = QLabel("  Search  ")
        lbl_s.setFont(F(12)); lbl_s.setStyleSheet(f"color:{C['dim']};")
        tb.addWidget(lbl_s)

        self.search = QLineEdit()
        self.search.setFont(F(12))
        self.search.setPlaceholderText("Filter inputs...")
        self.search.setFixedWidth(240); self.search.setFixedHeight(34)
        self.search.setClearButtonEnabled(True)
        tb.addWidget(self.search)

        tb.addSeparator()
        self.file_lbl = QLabel("  No file loaded  ")
        self.file_lbl.setFont(F(11, italic=True))
        self.file_lbl.setStyleSheet(f"color:{C['dim']};")
        tb.addWidget(self.file_lbl)

    # ── Category Panel ─────────────────────────────────────────────────────────
    def _build_cat_panel(self) -> QWidget:
        p = QWidget(); p.setMinimumWidth(230); p.setMaximumWidth(310)
        p.setStyleSheet(f"background:{C['bg2']};border-right:1px solid {C['bd']};")
        l = QVBoxLayout(p); l.setContentsMargins(14, 16, 14, 14); l.setSpacing(12)

        hdr = QLabel("CATEGORIES")
        hdr.setFont(F(9, bold=True))
        hdr.setStyleSheet(f"color:{C['dim2']};letter-spacing:3px;")
        l.addWidget(hdr)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd']};")
        l.addWidget(sep)

        self.cat_list = QListWidget(); self.cat_list.setFont(F(13))
        self.cat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cat_list.customContextMenuRequested.connect(self._cat_context_menu)
        l.addWidget(self.cat_list)

        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        self.btn_add_cat = QPushButton("+")
        self.btn_add_cat.setFixedSize(34, 32); self.btn_add_cat.setFont(F(15, bold=True))
        self.btn_add_cat.setToolTip("Add category")
        self.btn_ren_cat = QPushButton("E")
        self.btn_ren_cat.setFixedSize(34, 32); self.btn_ren_cat.setFont(F(12))
        self.btn_ren_cat.setToolTip("Rename category")
        self.btn_del_cat = QPushButton("X")
        self.btn_del_cat.setFixedSize(34, 32); self.btn_del_cat.setFont(F(12, bold=True))
        self.btn_del_cat.setToolTip("Delete category")
        for b in [self.btn_add_cat, self.btn_ren_cat, self.btn_del_cat]: btn_row.addWidget(b)
        btn_row.addStretch(); l.addLayout(btn_row)

        self.cat_stat = QLabel("")
        self.cat_stat.setFont(F(9, italic=True))
        self.cat_stat.setStyleSheet(f"color:{C['dim2']};")
        l.addWidget(self.cat_stat)
        return p

    # ── Right Panel ────────────────────────────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        self.tabs = QTabWidget(); l.addWidget(self.tabs)

        self.tabs.addTab(self._build_input_tab(),    "  Inputs  ")

        self.transform_w = CategoryTransformWidget()
        self.transform_w.request_swap.connect(self._handle_category_swap)
        self.tabs.addTab(self.transform_w,           "  Transform  ")

        self.folder_w = FolderImportWidget()
        self.folder_w.import_requested.connect(self._on_folder_bulk_import)
        self.tabs.addTab(self.folder_w,              "  Folder Import  ")

        self.tabs.addTab(self._build_file_tab(),     "  File Import  ")

        self.reset_w = FactoryResetWidget()
        self.reset_w.reset_triggered.connect(self._handle_factory_reset)
        self.tabs.addTab(self.reset_w,               "  Factory Reset  ")

        self.catimport_w = CategoryImportWidget()
        self.catimport_w.structure_ready.connect(self._on_cat_structure)
        self.tabs.addTab(self.catimport_w,           "  Category Import  ")

        self.export_w = CategoryExportWidget()
        self.export_w.parser_ref = self.parser
        self.tabs.addTab(self.export_w,              "  Factory Export  ")

        return p

    # ── Inputs Tab ─────────────────────────────────────────────────────────────
    def _build_input_tab(self) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w)
        l.setContentsMargins(18, 16, 18, 12); l.setSpacing(12)

        hdr = QHBoxLayout(); hdr.setSpacing(10)
        self.lbl_cat = QLabel("Select a category")
        self.lbl_cat.setFont(F(16, bold=True))
        self.lbl_cat.setStyleSheet(f"color:{C['text']};")
        self.lbl_cnt = QLabel("")
        self.lbl_cnt.setFont(F(12, italic=True))
        self.lbl_cnt.setStyleSheet(f"color:{C['dim']};")

        self.btn_add_inp = QPushButton("Add Files")
        self.btn_add_inp.setFont(F(12)); self.btn_add_inp.setFixedHeight(36)
        self.btn_add_inp.clicked.connect(self._add_inputs_dialog)

        self.btn_rem_inp = QPushButton("Remove")
        self.btn_rem_inp.setFont(F(12)); self.btn_rem_inp.setFixedHeight(36)
        self.btn_rem_inp.clicked.connect(self._remove_inputs)

        self.btn_mov_inp = QPushButton("Move To...")
        self.btn_mov_inp.setFont(F(12)); self.btn_mov_inp.setFixedHeight(36)
        self.btn_mov_inp.clicked.connect(self._move_inputs)

        hdr.addWidget(self.lbl_cat); hdr.addWidget(self.lbl_cnt); hdr.addStretch()
        for b in [self.btn_add_inp, self.btn_rem_inp, self.btn_mov_inp]: hdr.addWidget(b)
        l.addLayout(hdr)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd']};")
        l.addWidget(sep)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(['#', 'Title', 'Type', 'File Path', 'Open', 'Key'])
        self.tbl.horizontalHeader().setFont(F(10, bold=True))
        self.tbl.setFont(F(12))
        self.tbl.setItemDelegateForColumn(1, BigEditorDelegate(self.tbl))
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._tbl_context_menu)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tbl.setSortingEnabled(True)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(50)

        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);       self.tbl.setColumnWidth(0, 54)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);       self.tbl.setColumnWidth(2, 82)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed);       self.tbl.setColumnWidth(4, 56)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive); self.tbl.setColumnWidth(5, 125)

        l.addWidget(self.tbl)
        return w

    # ── File Tab ───────────────────────────────────────────────────────────────
    def _build_file_tab(self) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w)
        l.setContentsMargins(22, 22, 22, 22); l.setSpacing(14)

        hdr = QLabel("File Import")
        hdr.setFont(F(17, bold=True)); hdr.setStyleSheet(f"color:{C['text']};")
        l.addWidget(hdr)

        info = QLabel("Select individual files to add to the currently selected category.")
        info.setFont(F(12, italic=True)); info.setStyleSheet(f"color:{C['dim']};")
        l.addWidget(info)

        sep = QLabel(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{C['bd2']};")
        l.addWidget(sep)

        self.file_list = QListWidget(); self.file_list.setFont(F(12))
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        l.addWidget(self.file_list)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_b = QPushButton("Browse Files"); btn_b.setFont(F(12)); btn_b.setFixedHeight(38)
        btn_b.clicked.connect(self._browse_files)
        btn_c = QPushButton("Clear"); btn_c.setFont(F(12)); btn_c.setFixedHeight(38)
        btn_c.clicked.connect(self.file_list.clear)
        btn_a = QPushButton("Add to Category"); btn_a.setFont(F(12, bold=True)); btn_a.setFixedHeight(38)
        btn_a.setStyleSheet(
            f"background:{C['accent']};color:#000000;border:none;border-radius:3px;padding:0 20px;"
        )
        btn_a.clicked.connect(self._add_listed_files)
        btn_row.addWidget(btn_b); btn_row.addWidget(btn_c); btn_row.addStretch(); btn_row.addWidget(btn_a)
        l.addLayout(btn_row)
        return w

    # ── Log Panel ──────────────────────────────────────────────────────────────
    def _build_log_panel(self) -> QWidget:
        p = QWidget(); p.setMaximumHeight(152)
        p.setStyleSheet(f"background:{C['bg']};border-top:1px solid {C['bd']};")
        pl = QVBoxLayout(p); pl.setContentsMargins(16, 8, 16, 8); pl.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("ACTIVITY LOG")
        hdr.setFont(F(8, bold=True)); hdr.setStyleSheet(f"color:{C['dim2']};letter-spacing:3px;")
        hdr_row.addWidget(hdr); hdr_row.addStretch()
        pl.addLayout(hdr_row)

        self.log_w = LogWidget(); pl.addWidget(self.log_w)
        return p

    # ── Handlers ───────────────────────────────────────────────────────────────
    def _handle_factory_reset(self, mode: str):
        if mode == "current" and self.current_cat:
            if QMessageBox.question(self,"Confirm",f"Empty '{self.current_cat.display_name}'?") == QMessageBox.StandardButton.Yes:
                self.current_cat.inputs = []
        elif mode == "all":
            if QMessageBox.question(self,"Confirm","Wipe every input in this file?") == QMessageBox.StandardButton.Yes:
                for c in self.parser.categories.values(): c.inputs = []
        elif mode == "session":
            if QMessageBox.question(self,"Confirm","Full factory reset — wipe everything and reset all names?") == QMessageBox.StandardButton.Yes:
                self.parser.create_new()
        self._refresh_categories(); self._refresh_inputs()
        self.log(f"Reset action '{mode}' completed.", "WARNING")

    def _on_folder_bulk_import(self, folder_data: list):
        if not self.current_cat:
            QMessageBox.warning(self,"No Category Selected","Please select a category from the left panel first."); return
        cat_idx  = self.current_cat.index
        cat_name = self.current_cat.display_name
        added    = 0
        for folder_name, file_paths in folder_data:
            header_xml = (
                f'<items><item name="Message.Text" version="2">'
                f'<Font Name="Arial" Size="214" FillColor="#FFFFFFFF" Style="Normal" '
                f'Weight="Bold" Stretch="Normal" LineSpacing="0" />'
                f'<value>{folder_name}</value></item></items>'
            )
            header_inp = VmixInput(
                key=str(uuid.uuid4()), original_title=folder_name, input_type=9000,
                category=cat_idx,
                file_path=r"C:\Program Files (x86)\vMix\titles\GT Text\Text Middle Centre Left Right Sharp.gtzip",
                xml_payload=header_xml
            )
            self.parser.categories[cat_idx].inputs.append(header_inp); added += 1
            for fp in file_paths:
                self.parser.add_input(cat_idx, fp); added += 1
        self.parser.reorder(cat_idx)
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.tabs.setCurrentIndex(0)
        self.log(f"Imported {len(folder_data)} folders into '{cat_name}'", "SUCCESS")

    def _rename_input_inline(self):
        row = self.tbl.currentRow()
        if row >= 0: self.tbl.editItem(self.tbl.item(row, 1))

    def _replace_input_file(self):
        row = self.tbl.currentRow()
        if row < 0: return
        ki  = self.tbl.item(row, 5)
        key = ki.data(Qt.ItemDataRole.UserRole)
        inp = next((i for i in self.current_cat.inputs if i.key == key), None)
        if not inp: return
        new_file, _ = QFileDialog.getOpenFileName(self, "Replace Media File", "", "All Files (*)")
        if new_file:
            inp.file_path = os.path.normpath(new_file)
            inp.original_title = Path(new_file).name
            self._mark_modified(); self._refresh_inputs()
            self.log(f"Replaced file for '{inp.original_title}'", "SUCCESS")

    def _tbl_context_menu(self, pos):
        if not self.tbl.itemAt(pos): return
        m = QMenu(self); m.setFont(F(12))
        m.addAction("Rename Title",          self._rename_input_inline)
        m.addAction("Replace File (Browse)", self._replace_input_file)
        m.addSeparator()
        act_open = m.addAction("Open in Explorer")
        path = self.tbl.item(self.tbl.currentRow(), 3).text()
        act_open.triggered.connect(lambda: self._open_file_system(path))
        m.addSeparator()
        m.addAction("Remove Input", self._remove_inputs)
        m.exec(self.tbl.mapToGlobal(pos))

    def _on_cat_visibility_toggled(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx == 0: return
        is_checked = (item.checkState() == Qt.CheckState.Checked)
        if idx in self.parser.categories:
            self.parser.categories[idx].enabled = is_checked
            self._mark_modified()
            self.log(f"Category '{self.parser.categories[idx].display_name}' -> {'VISIBLE' if is_checked else 'HIDDEN'}")

    def _handle_category_swap(self, idx_a, idx_b):
        if self.parser.swap_categories(idx_a, idx_b):
            self._mark_modified(); self._refresh_categories()
            self.log(f"Swapped slot {idx_a} with slot {idx_b}.")

    def _open_file_system(self, file_path):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File not found:\n{file_path}"); return
        try:
            if platform.system() == "Windows": os.startfile(file_path)
            elif platform.system() == "Darwin": subprocess.run(["open", file_path])
            else: subprocess.run(["xdg-open", file_path])
        except Exception as e:
            self.log(f"Could not open file: {e}", "ERROR")

    # ── Signal wiring ──────────────────────────────────────────────────────────
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
        t = f"{APP_NAME}  v{APP_VERSION}"
        if self.parser.file_path: t += f"  -  {Path(self.parser.file_path).name}  *"
        self.setWindowTitle(t)

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

    # ── Category operations ────────────────────────────────────────────────────
    def _refresh_categories(self):
        self.cat_list.blockSignals(True)
        prev_idx = self._current_cat_idx()
        self.cat_list.clear()
        for cat in sorted(self.parser.categories.values(), key=lambda c: c.index):
            count_str = f"  ({cat.count()})" if cat.count() > 0 else ""
            item = QListWidgetItem(f"  {cat.display_name}{count_str}")
            item.setFont(F(13, bold=(cat.index == 0)))
            item.setData(Qt.ItemDataRole.UserRole, cat.index)
            if cat.index == 0:
                item.setForeground(QColor(C['text']))
            else:
                item.setForeground(QColor(C['text'] if cat.enabled else C['dim2']))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if cat.enabled else Qt.CheckState.Unchecked)
            self.cat_list.addItem(item)
            if cat.index == prev_idx: self.cat_list.setCurrentItem(item)
        self.cat_list.blockSignals(False)
        self.transform_w.refresh_lists(self.parser.categories)
        self.export_w.refresh_categories(self.parser.categories)

    def _on_cat_changed(self, cur, _):
        if cur is None: self.current_cat = None; self.tbl.setRowCount(0); return
        idx = cur.data(Qt.ItemDataRole.UserRole)
        self.current_cat = self.parser.categories.get(idx)
        self._refresh_inputs()

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            try:
                cat = self.parser.add_category(name.strip())
                self._refresh_categories(); self._mark_modified()
                self.log(f"Added category [{cat.index}] '{cat.display_name}'", "SUCCESS")
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _rename_category(self, *_):
        idx = self._current_cat_idx()
        if idx is None or idx == 0: return
        cat = self.parser.categories[idx]
        curr = "" if cat.name == "Empty Cat" else cat.name
        name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=curr)
        if ok:
            new_name = name.strip()
            if not new_name:
                cat.name = "Empty Cat"; cat.enabled = False
                self.log(f"Category {idx} cleared and disabled.")
            else:
                cat.name = new_name
                if not cat.enabled: cat.enabled = True
                self.log(f"Renamed category {idx} to '{new_name}'")
            self._refresh_categories(); self._mark_modified()

    def _delete_category(self):
        idx = self._current_cat_idx()
        if idx is None: return
        cat = self.parser.categories[idx]
        if cat.count() > 0:
            other = {str(c.index): c.display_name for c in self.parser.categories.values() if c.index != idx}
            if not other:
                QMessageBox.warning(self, "Error", "Cannot delete the only category."); return
            choices = list(other.keys())
            choice, ok = QInputDialog.getItem(self, "Move Inputs",
                f"Move {cat.count()} inputs to:",
                [f"[{k}] {other[k]}" for k in choices], 0, False)
            if not ok: return
            move_to = int(choices[[f"[{k}] {other[k]}" for k in choices].index(choice)])
        else:
            r = QMessageBox.question(self, "Delete", f"Delete category '{cat.display_name}'?")
            if r != QMessageBox.StandardButton.Yes: return
            move_to = -1
        self.parser.remove_category(idx, move_to if move_to != -1 else idx)
        self.current_cat = None; self._refresh_categories(); self._mark_modified()
        self.log(f"Deleted category [{idx}] '{cat.display_name}'", "WARNING")

    def _cat_context_menu(self, pos):
        if not self.cat_list.itemAt(pos): return
        m = QMenu(self); m.setFont(F(12))
        m.addAction("Rename", self._rename_category)
        m.addAction("Delete", self._delete_category)
        m.exec(self.cat_list.mapToGlobal(pos))

    # ── Input operations ───────────────────────────────────────────────────────
    def _refresh_inputs(self):
        if not self.current_cat:
            self.tbl.setRowCount(0)
            self.lbl_cat.setText("Select a category"); self.lbl_cnt.setText(""); return

        self.lbl_cat.setText(f"  {self.current_cat.display_name}")
        self.lbl_cnt.setText(f"  —  {self.current_cat.count()} inputs")

        self.tbl.blockSignals(True); self.tbl.setSortingEnabled(False)
        flt = self.search.text().lower()
        inputs = [i for i in self.current_cat.inputs
                  if not flt or flt in i.original_title.lower() or flt in i.file_path.lower()]
        self.tbl.setRowCount(len(inputs))

        for r, inp in enumerate(inputs):
            # Col 0 — number
            ni = QTableWidgetItem(str(r + 1))
            ni.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ni.setFont(F_MONO(10)); ni.setForeground(QColor(C['dim']))
            ni.setFlags(ni.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 0, ni)

            # Col 1 — title
            ti = QTableWidgetItem(inp.original_title)
            ti.setFont(F(12)); ti.setForeground(QColor(C['text']))
            self.tbl.setItem(r, 1, ti)

            # Col 2 — type
            tyi = QTableWidgetItem(inp.type_name)
            tyi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tyi.setFont(F(10, bold=True)); tyi.setForeground(QColor(C['text2']))
            tyi.setFlags(tyi.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, tyi)

            # Col 3 — path
            pi = QTableWidgetItem(inp.file_path)
            pi.setFont(F_MONO(9)); pi.setForeground(QColor(C['dim']))
            self.tbl.setItem(r, 3, pi)

            # Col 4 — open button
            btn_open = QPushButton("O")
            btn_open.setFont(F(12, bold=True)); btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setStyleSheet(
                f"QPushButton{{border:none;background:transparent;color:{C['dim']};}}"
                f"QPushButton:hover{{color:{C['text']};}}"
            )
            btn_open.clicked.connect(lambda ch, pp=inp.file_path: self._open_file_system(pp))
            self.tbl.setCellWidget(r, 4, btn_open)

            # Col 5 — key
            ki = QTableWidgetItem(inp.key[:12]+"..." if len(inp.key)>12 else inp.key)
            ki.setData(Qt.ItemDataRole.UserRole, inp.key)
            ki.setFont(F_MONO(8)); ki.setForeground(QColor(C['dim2']))
            ki.setFlags(ki.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 5, ki)

        self.tbl.setSortingEnabled(True); self.tbl.blockSignals(False)

    def _filter_inputs(self): self._refresh_inputs()

    def _on_tbl_item_changed(self, item):
        if item.column() not in (1, 3): return
        r  = item.row()
        ki = self.tbl.item(r, 4)
        if not ki: return
        key = ki.data(Qt.ItemDataRole.UserRole) or ki.text().replace("...","")
        inp = next((i for i in (self.current_cat.inputs if self.current_cat else [])
                    if i.key.startswith(key[:12])), None)
        if not inp: return
        if item.column() == 1: inp.original_title = item.text()
        elif item.column() == 3: inp.file_path = item.text()
        self._mark_modified()

    def _add_inputs_dialog(self):
        if not self.current_cat:
            QMessageBox.warning(self,"No Category","Please select a category first."); return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Media Files", "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav *.aac *.flac);;All Files (*)")
        if files: self._add_files_to_current(files)

    def _add_files_to_current(self, entries: List[str]):
        if not self.current_cat:
            QMessageBox.warning(self,"No Category","Select a category first."); return
        added = 0
        for path in entries:
            path = os.path.normpath(path.strip())
            if os.path.isdir(path):
                for fp in FileScanner.scan(path, recursive=False):
                    self.parser.add_input(self.current_cat.index, fp); added += 1
            elif os.path.isfile(path):
                self.parser.add_input(self.current_cat.index, path); added += 1
            else:
                self.parser.add_input_title_only(self.current_cat.index, path); added += 1
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Added {added} input(s) to '{self.current_cat.display_name}'", "SUCCESS")

    def _remove_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        if QMessageBox.question(self,"Remove",f"Remove {len(inputs)} input(s)?") != QMessageBox.StandardButton.Yes: return
        for inp in inputs: self.parser.remove_input(inp)
        self.parser.reorder(self.current_cat.index)
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Removed {len(inputs)} input(s)", "WARNING")

    def _move_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        choices = {str(c.index): c.display_name for c in self.parser.categories.values()
                   if c.index != self.current_cat.index}
        if not choices:
            QMessageBox.information(self,"Move","No other categories available."); return
        keys = list(choices.keys())
        labels = [f"[{k}] {choices[k]}" for k in keys]
        choice, ok = QInputDialog.getItem(self,"Move Inputs","Move to:",labels,0,False)
        if not ok: return
        target = int(keys[labels.index(choice)])
        for inp in inputs:
            self.parser.remove_input(inp); inp.category = target
            inp.position = max((i.position for i in self.parser.categories[target].inputs), default=-1)+1
            self.parser.categories[target].inputs.append(inp)
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Moved {len(inputs)} input(s) to [{target}]", "SUCCESS")

    # ── Import handlers ────────────────────────────────────────────────────────
    def _on_folder_files(self, files): self._add_files_to_current(files); self.tabs.setCurrentIndex(0)
    def _on_script_entries(self, entries): self._add_files_to_current(entries); self.tabs.setCurrentIndex(0)

    def _on_cat_structure(self, structure: List[Tuple[str, List[str]]]):
        added_cats = added_inputs = 0
        for folder_name, files in structure:
            existing = next((c for c in self.parser.categories.values()
                             if c.display_name.lower() == folder_name.lower()), None)
            cat = existing
            if not existing:
                try: cat = self.parser.add_category(folder_name); added_cats += 1
                except ValueError:
                    self.log(f"Category limit reached, skipping '{folder_name}'", "WARNING"); continue
            for fp in files:
                self.parser.add_input(cat.index, fp); added_inputs += 1
        self._refresh_categories(); self._mark_modified()
        self.log(f"Imported {added_cats} categories, {added_inputs} inputs", "SUCCESS")
        self.tabs.setCurrentIndex(0)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self,"Select Files","",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav);;All Files (*)")
        for fp in files:
            item = QListWidgetItem(f"  {Path(fp).name}")
            item.setFont(F(12)); item.setToolTip(fp)
            self.file_list.addItem(item)

    def _add_listed_files(self):
        files = [self.file_list.item(i).toolTip() for i in range(self.file_list.count())]
        if files: self._add_files_to_current(files); self.tabs.setCurrentIndex(0)

    # ── File operations ────────────────────────────────────────────────────────
    def _check_save(self) -> bool:
        if not self.modified: return True
        r = QMessageBox.question(self,"Unsaved Changes","Save changes before proceeding?",
            QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Cancel: return False
        if r == QMessageBox.StandardButton.Save: return self._save()
        return True

    def _new(self):
        if not self._check_save(): return
        self.parser.create_new(); self.current_cat = None
        self._refresh_categories(); self.modified = False
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}"); self.file_lbl.setText("  New file")
        self.log("New production created.", "SUCCESS")

    def _open(self):
        if not self._check_save(): return
        path, _ = QFileDialog.getOpenFileName(self,"Open .vmix File","","vMix Files (*.vmix);;All Files (*)")
        if not path: return
        if self.parser.load(path):
            self.current_cat = None; self._refresh_categories(); self.modified = False
            self.setWindowTitle(f"{APP_NAME}  -  {Path(path).name}")
            self.file_lbl.setText(f"  {Path(path).name}")
            n = sum(c.count() for c in self.parser.categories.values())
            self.log(f"Loaded '{Path(path).name}'  -  {len(self.parser.categories)} categories, {n} inputs","SUCCESS")
        else:
            QMessageBox.critical(self,"Error",f"Failed to load:\n{path}")

    def _save(self) -> bool:
        if not self.parser.file_path: return self._save_as()
        if self.parser.save(self.parser.file_path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME}  -  {Path(self.parser.file_path).name}")
            self.log(f"Saved '{Path(self.parser.file_path).name}'","SUCCESS"); return True
        QMessageBox.critical(self,"Error","Save failed."); return False

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self,"Save .vmix File","","vMix Files (*.vmix)")
        if not path: return False
        if not path.endswith('.vmix'): path += '.vmix'
        if self.parser.save(path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME}  -  {Path(path).name}")
            self.file_lbl.setText(f"  {Path(path).name}")
            self.log(f"Saved as '{Path(path).name}'","SUCCESS"); return True
        QMessageBox.critical(self,"Error","Save failed."); return False

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self,"Export JSON","","JSON Files (*.json)")
        if not path: return
        if not path.endswith('.json'): path += '.json'
        self.parser.export_json(path); self.log(f"Exported JSON: {Path(path).name}","SUCCESS")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self,"Export CSV","","CSV Files (*.csv)")
        if not path: return
        if not path.endswith('.csv'): path += '.csv'
        self.parser.export_csv(path); self.log(f"Exported CSV: {Path(path).name}","SUCCESS")

    def closeEvent(self, event):
        if self._check_save(): event.accept()
        else: event.ignore()

    # ── Stylesheet ─────────────────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet(f"""
        /* ── Base ────────────────────────────────────────────────── */
        QMainWindow, QWidget {{
            background: {C['bg']};
            color: {C['text']};
            font-family: Cambria;
            font-size: 12px;
        }}

        /* ── Toolbar ─────────────────────────────────────────────── */
        QToolBar {{
            background: {C['bg2']};
            border-bottom: 1px solid {C['bd']};
            padding: 0 8px;
            spacing: 2px;
        }}
        QToolButton {{
            color: {C['text2']};
            background: transparent;
            border: 1px solid transparent;
            border-radius: 2px;
            padding: 7px 16px;
            font-family: Cambria;
            font-size: 12px;
        }}
        QToolButton:hover {{
            background: {C['bg3']};
            border-color: {C['bd2']};
            color: {C['text']};
        }}
        QToolButton:pressed {{ background: {C['bg4']}; }}
        QToolBar::separator {{
            background: {C['bd']};
            width: 1px;
            margin: 11px 8px;
        }}

        /* ── Sidebar List ────────────────────────────────────────── */
        QListWidget {{
            background: {C['bg2']};
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            padding: 11px 8px;
            border-bottom: 1px solid {C['bd']};
            font-family: Cambria;
            font-size: 13px;
        }}
        QListWidget::item:selected {{
            background: {C['hi']};
            color: {C['text']};
            border-left: 3px solid {C['accent']};
        }}
        QListWidget::item:hover:!selected {{ background: {C['bg3']}; }}

        /* ── Table ───────────────────────────────────────────────── */
        QTableWidget {{
            background: {C['bg2']};
            border: none;
            gridline-color: {C['bd']};
            outline: none;
            font-family: Cambria;
            font-size: 12px;
        }}
        QTableWidget::item {{
            padding: 6px 10px;
            border-bottom: 1px solid {C['bd']};
        }}
        QTableWidget::item:selected,
        QTableWidget::item:selected:active,
        QTableWidget::item:selected:!active {{
            background-color: {C['hi']} !important;
            color: {C['text']} !important;
            border-left: 2px solid {C['accent']};
        }}
        QTableWidget::item:alternate {{ background: {C['alt']}; }}
        QTableWidget::item:alternate:selected {{ background-color: {C['hi']} !important; }}
        QHeaderView {{ background: {C['bg']}; }}
        QHeaderView::section {{
            background: {C['bg']};
            color: {C['dim']};
            padding: 10px 10px;
            border: none;
            border-bottom: 1px solid {C['bd2']};
            border-right: 1px solid {C['bd']};
            font-family: Cambria;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
        }}

        /* ── Tabs ────────────────────────────────────────────────── */
        QTabWidget::pane {{
            background: {C['bg2']};
            border: none;
            border-top: 1px solid {C['bd']};
        }}
        QTabBar {{ background: {C['bg']}; }}
        QTabBar::tab {{
            background: {C['bg']};
            color: {C['dim']};
            padding: 11px 8px;
            margin-right: 1px;
            border-bottom: 2px solid transparent;
            font-family: Cambria;
            font-size: 11px;
        }}
        QTabBar::tab:selected {{
            color: {C['text']};
            border-bottom: 2px solid {C['accent']};
        }}
        QTabBar::tab:hover:!selected {{
            color: {C['text2']};
            border-bottom: 2px solid {C['bd2']};
        }}

        /* ── Buttons ─────────────────────────────────────────────── */
        QPushButton {{
            background: {C['bg3']};
            color: {C['text2']};
            border: 1px solid {C['bd2']};
            border-radius: 2px;
            padding: 7px 18px;
            font-family: Cambria;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {C['bg4']};
            color: {C['text']};
            border-color: {C['bd3']};
        }}
        QPushButton:pressed {{ background: {C['bg5']}; }}
        QPushButton:disabled {{ color: {C['dim2']}; border-color: {C['bd']}; }}

        /* ── Editors ─────────────────────────────────────────────── */
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background: {C['bg4']};
            color: {C['text']};
            border: 1px solid {C['bd2']};
            border-radius: 2px;
            padding: 6px 10px;
            font-family: Cambria;
            font-size: 12px;
            selection-background-color: {C['accent']};
            selection-color: #000000;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {C['bd3']};
        }}

        /* ── Group Box ───────────────────────────────────────────── */
        QGroupBox {{
            background: {C['bg2']};
            border: 1px solid {C['bd']};
            border-radius: 3px;
            margin-top: 16px;
            padding-top: 12px;
            color: {C['dim']};
            font-family: Cambria;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            left: 14px;
        }}

        /* ── Progress Bar ────────────────────────────────────────── */
        QProgressBar {{
            border: none;
            border-radius: 2px;
            background: {C['bg3']};
            font-family: Cambria;
            font-size: 10px;
        }}
        QProgressBar::chunk {{ background: {C['accent']}; border-radius: 2px; }}

        /* ── Scrollbars ──────────────────────────────────────────── */
        QScrollBar:vertical {{
            background: {C['bg']}; width: 7px; border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {C['bd2']}; border-radius: 3px; min-height: 26px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {C['bd3']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {C['bg']}; height: 7px; border-radius: 3px;
        }}
        QScrollBar::handle:horizontal {{
            background: {C['bd2']}; border-radius: 3px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        /* ── Context Menu ────────────────────────────────────────── */
        QMenu {{
            background: {C['bg3']};
            color: {C['text']};
            border: 1px solid {C['bd2']};
            padding: 4px 0;
            font-family: Cambria;
            font-size: 12px;
        }}
        QMenu::item {{ padding: 9px 24px; }}
        QMenu::item:selected {{ background: {C['bg4']}; }}
        QMenu::separator {{ height: 1px; background: {C['bd']}; margin: 4px 10px; }}

        /* ── Splitter ────────────────────────────────────────────── */
        QSplitter::handle {{ background: {C['bd']}; }}
        QSplitter::handle:hover {{ background: {C['bd3']}; }}

        /* ── Tree Widget ─────────────────────────────────────────── */
        QTreeWidget {{
            background: {C['bg2']};
            border: 1px solid {C['bd']};
            border-radius: 2px;
            outline: none;
            font-family: Cambria;
            font-size: 11px;
        }}
        QTreeWidget::item {{ padding: 7px 4px; }}
        QTreeWidget::item:selected {{ background: {C['hi']}; color: {C['text']}; }}
        QTreeWidget::branch {{ background: {C['bg2']}; }}

        /* ── Dialogs ─────────────────────────────────────────────── */
        QDialog {{ background: {C['bg2']}; color: {C['text']}; font-family: Cambria; }}
        QMessageBox {{ background: {C['bg2']}; color: {C['text']}; font-family: Cambria; }}
        QInputDialog QLabel {{ color: {C['text']}; font-family: Cambria; font-size: 13px; }}
        """)


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C['bg']))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C['bg2']))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C['alt']))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(C['bg3']))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C['bg3']))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C['text']))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor('#FFFFFF'))
    pal.setColor(QPalette.ColorRole.Link,            QColor(C['text2']))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C['hi']))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C['text']))
    app.setPalette(pal)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())