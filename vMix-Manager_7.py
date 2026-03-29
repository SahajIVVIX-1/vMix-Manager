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
    QProgressBar, QStyledItemDelegate, QComboBox  # <--- ADD THIS
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QTimer, 
    QObject, QThread  # <--- ADD THESE
)
from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence, QIcon

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME, APP_VERSION = "vMix Manager", "6"

VIDEO_EXTS = {'.mp4','.avi','.mov','.mkv','.wmv','.flv','.m4v','.webm','.ts','.mts'}
IMAGE_EXTS = {'.jpg','.jpeg','.png','.bmp','.gif','.tiff','.tga','.webp'}
AUDIO_EXTS = {'.mp3','.wav','.aac','.flac','.ogg','.wma','.m4a'}
ALL_MEDIA  = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

# Change 2 to 0 for Video
INPUT_TYPES = {1:"Image", 0:"Video", 3:"Audio", 6:"Desktop", 7:"NDI", 12:"Title", 20:"Camera"}

# Add this constant near the top of your file
DEF_CAT_NAMES = {
    0: "ALL", 1: "Red", 2: "Green", 3: "Orange", 4: "Purple", 5: "Aqua", 6: "Blue",
    7: "Custom1", 8: "Custom2", 9: "Custom3", 10: "Custom4", 11: "Custom5",
    12: "Custom6", 13: "Custom7", 14: "Custom8", 15: "Custom9", 16: "Custom10",
    17: "Custom11", 18: "Custom12", 19: "Custom13", 20: "Custom14", 21: "Custom15", 22: "Custom16"
}

# vMix internal mapping for the Category tabs
CAT_MAP = {
    1: "Red", 2: "Green", 3: "Orange", 4: "Purple", 5: "Aqua", 6: "Blue",
    7: "Custom1", 8: "Custom2", 9: "Custom3", 10: "Custom4", 11: "Custom5",
    12: "Custom6", 13: "Custom7", 14: "Custom8", 15: "Custom9", 16: "Custom10",
    17: "Custom11", 18: "Custom12", 19: "Custom13", 20: "Custom14", 21: "Custom15", 22: "Custom16"
}

CAT_ID_LOOKUP = {
    "All.Text": 0,      # ID 0 (All)
    "Red.Text": 1,      # ID 1
    "Green.Text": 2,    # ID 2
    "Orange.Text": 3,   # ID 3
    "Purple.Text": 4,   # ID 4
    "Aqua.Text": 5,     # ID 5
    "Blue.Text": 6,     # ID 6
    "Custom1.Text": 7,  "Custom2.Text": 8,  "Custom3.Text": 9,  "Custom4.Text": 10,
    "Custom5.Text": 11, "Custom6.Text": 12, "Custom7.Text": 13, "Custom8.Text": 14,
    "Custom9.Text": 15, "Custom10.Text": 16, "Custom11.Text": 17, "Custom12.Text": 18,
    "Custom13.Text": 19, "Custom14.Text": 20, "Custom15.Text": 21, "Custom16.Text": 22
}

CAT_ENABLED_LOOKUP = {k.replace(".Text", ".Enabled"): v for k, v in CAT_ID_LOOKUP.items()}

C = {
    'bg':      '#1E1E2E', 'bg2':    '#2A2A3E', 'accent':  '#7C3AED',
    'text':    '#E0E0F0', 'dim':    '#A0A0C0', 'border':  '#3A3A5A',
    'ok':      '#10B981', 'warn':   '#F59E0B', 'err':     '#EF4444',
    'hi':      '#4C1D95', 'alt':    '#252538',
}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class VmixInput:
    key: str = ""
    original_title: str = ""
    input_type: int = 1
    category: int = 0
    position: int = 0
    file_path: str = ""
    xml_payload: str = ""  # <--- ADD THIS for GT Titles
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
        
        # 1. Extract existing custom names/enabled states from XML
        cs_node = self._orig_root.find('CategorySettings')
        if cs_node is not None:
            for child in cs_node:
                if child.tag in CAT_ID_LOOKUP:
                    name_map[CAT_ID_LOOKUP[child.tag]] = child.text
                if child.tag in CAT_ENABLED_LOOKUP:
                    enabled_map[CAT_ENABLED_LOOKUP[child.tag]] = (child.text == "1")

        # 2. Initialize all 23 slots with "Empty Cat" logic
        for i in range(23):
            raw_name = name_map.get(i, "")
            
            # Logic: If index > 0 and name is empty, set as "Empty Cat" and disable
            if i == 0:
                name = "ALL"
                is_enabled = True
            elif not raw_name or not raw_name.strip():
                name = "Empty Cat"
                is_enabled = False # Automatically set Enabled 0
            else:
                name = raw_name
                is_enabled = enabled_map.get(i, True) # Keep existing vMix state

            self.categories[i] = VmixCategory(index=i, name=name, enabled=is_enabled)

        # 3. Assign Inputs to their categories
        for el in self._orig_root:
            if el.tag != 'Input': continue
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
            xml_payload=a.get('XML', ''), # <--- ADD THIS
            extra_attrs={k:v for k,v in a.items() if k not in {'Key','OriginalTitle','Type','Category','Position', 'XML'}}
        )

    def swap_categories(self, idx_a: int, idx_b: int):
        if idx_a not in self.categories or idx_b not in self.categories: 
            return False
        
        # 1. Swap the names
        self.categories[idx_a].name, self.categories[idx_b].name = \
            self.categories[idx_b].name, self.categories[idx_a].name
            
        # 2. Swap the lists of inputs
        self.categories[idx_a].inputs, self.categories[idx_b].inputs = \
            self.categories[idx_b].inputs, self.categories[idx_a].inputs

        # 3. CRITICAL: Update the category ID stored inside every video object
        # This ensures the <Input Category="X"> attribute changes in the XML
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
            
            # 1. Rebuild Inputs with new Category IDs
            for cat in sorted(self.categories.values(), key=lambda c: c.index):
                for inp in sorted(cat.inputs, key=lambda x: x.position):
                    root.append(self._build_el(inp))
            
            # 2. Copy settings and UPDATE Category names
            if self._orig_root is not None:
                for el in self._orig_root:
                    if el.tag in ('Version', 'ZoomManager', 'Input'): continue
                    
                    new_el = copy.deepcopy(el)
                    if new_el.tag == 'CategorySettings':
                        for child in new_el:
                            # Handle Names
                            idx = CAT_ID_LOOKUP.get(child.tag)
                            if idx is not None and idx in self.categories:
                                cat = self.categories[idx]
                                # If it's our placeholder, save it as empty to vMix
                                child.text = "" if cat.name == "Empty Cat" else cat.name
                            
                            # Handle Enabled state
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
        # Add XML payload if it exists (for GT Titles)
        if inp.xml_payload:
            attrs['XML'] = inp.xml_payload
            
        attrs.update(inp.extra_attrs)
        el = ET.Element('Input', attrib=attrs)
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

# -- Helper for OS-safe folder names --
def sanitize_folder_name(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

class BigEditorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        # Make the editor taller and larger
        editor.setMinimumHeight(40) 
        editor.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        editor.setStyleSheet(f"background: {C['bg2']}; color: white; border: 2px solid {C['accent']}; padding: 5px;")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        # This makes the editor expand to the full size of the cell plus some extra height
        rect = option.rect
        rect.setHeight(40)
        editor.setGeometry(rect)

# ── Export Worker ──────────────────────────────────────────────────────────────
class ExportWorker(QObject):
    """Handles the heavy lifting of file copying in a background thread."""
    progress_updated = pyqtSignal(int, str)  # (current_count, file_name)
    finished = pyqtSignal(int, int)          # (total_success, total_errors)
    log_msg = pyqtSignal(str, str)           # (message, level)

    def __init__(self, categories: List[VmixCategory], destination_root: str):
        super().__init__()
        self.categories = categories
        self.destination_root = destination_root

    def run(self):
        success_count = 0
        error_count = 0
        
        # 1. Calculate total work
        total_files = sum(len(cat.inputs) for cat in self.categories)
        if total_files == 0:
            self.finished.emit(0, 0)
            return

        self.log_msg.emit(f"Starting export of {total_files} files...", "INFO")

        # 2. Process Categories
        for cat in self.categories:
            safe_name = sanitize_folder_name(cat.display_name)
            target_dir = Path(self.destination_root) / safe_name
            
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                self.log_msg.emit(f"Could not create folder {safe_name}: {e}", "ERROR")
                error_count += len(cat.inputs)
                continue

            # 3. Process individual files
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
        self.parser_ref = None # Will be set by MainWindow
        self.thread = None
        self.worker = None
        
        layout = QVBoxLayout(self)
        
        # Header
        info = QLabel("📤 Export Categories to Folders")
        info.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(info)
        
        # Category Selection List
        layout.addWidget(QLabel("1. Select categories to export:"))
        self.cat_list = QListWidget()
        self.cat_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cat_list.setStyleSheet(f"border: 1px solid {C['border']};")
        layout.addWidget(self.cat_list)
        
        # Path Selection
        layout.addWidget(QLabel("2. Destination Root Folder:"))
        path_row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Select folder where subfolders will be created...")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_dest)
        path_row.addWidget(self.dest_edit)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)
        
        # Progress Tracking
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {C['border']}; border-radius: 4px; text-align: center; }}
            QProgressBar::chunk {{ background-color: {C['accent']}; }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.status_log = LogWidget()
        layout.addWidget(self.status_log)
        
        # Export Button
        self.btn_export = QPushButton("🚀 Start Export")
        self.btn_export.setFixedHeight(45)
        self.btn_export.setStyleSheet(f"background:{C['ok']}; color:white; font-weight:bold;")
        self.btn_export.clicked.connect(self._start_export)
        layout.addWidget(self.btn_export)

    def refresh_categories(self, categories):
        self.cat_list.clear()
        # Filter out empty or "All" categories if desired, or keep all
        for cat in sorted(categories.values(), key=lambda x: x.index):
            if cat.index == 0: continue # Skip 'ALL' virtual category
            item = QListWidgetItem(f"[{cat.index}] {cat.display_name} ({len(cat.inputs)} items)")
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

        # Prepare data
        selected_cats = [self.parser_ref.categories[i.data(Qt.ItemDataRole.UserRole)] for i in selected_items]
        total_files = sum(len(c.inputs) for c in selected_cats)
        
        if total_files == 0:
            QMessageBox.information(self, "Export", "Selected categories contain no files.")
            return

        # UI State
        self.btn_export.setEnabled(False)
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_log.clear()
        
        # Thread Setup
        self.thread = QThread()
        self.worker = ExportWorker(selected_cats, dest)
        self.worker.moveToThread(self.thread)
        
        # Connections
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
        msg = f"Export Complete!\n- Successfully copied: {success}\n- Failed/Missing: {errors}"
        self.status_log.log(msg, "SUCCESS" if errors == 0 else "WARNING")
        QMessageBox.information(self, "Export Finished", msg)

# ── Log Widget ─────────────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True); self.setMaximumHeight(120)
        self.setFont(QFont("Consolas", 9))

    def log(self, msg: str, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        col = {"INFO":"#87CEEB","SUCCESS":C['ok'],"WARNING":C['warn'],"ERROR":C['err']}.get(level,"#E0E0F0")
        self.append(f'<span style="color:#888">[{ts}]</span> <span style="color:{col}"><b>{level}</b></span>: {msg}')
        self.moveCursor(QTextCursor.MoveOperation.End)

# ── Folder Import Widget ───────────────────────────────────────────────────────
class FolderImportWidget(QWidget):
    # Signal sends: (target_category_index, list_of_tuples_folder_name_and_files)
    import_requested = pyqtSignal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = [] # Stores list of (folder_name, [file_paths])
        
        layout = QVBoxLayout(self)
        
        # 1. Category Selection
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Target Category:"))
        self.combo_cat = QComboBox()
        cat_row.addWidget(self.combo_cat, 1)
        layout.addLayout(cat_row)

        # 2. Queue View
        layout.addWidget(QLabel("Folder Queue (Headers will be created for each):"))
        self.preview = QListWidget()
        layout.addWidget(self.preview)
        
        # 3. Queue Controls
        btn_row = QHBoxLayout()
        btn_add = QPushButton("📁 Add Folder to Queue")
        btn_add.clicked.connect(self._add_folder_to_queue)
        btn_clr = QPushButton("🗑️ Clear Queue")
        btn_clr.clicked.connect(self._clear_queue)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_clr)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # 4. Final Import Button
        self.btn_import = QPushButton("🚀 Start Import (Header + Sorted Files)")
        self.btn_import.setFixedHeight(45)
        self.btn_import.setStyleSheet(f"background:{C['accent']}; color:white; font-weight:bold;")
        self.btn_import.clicked.connect(self._emit_import)
        layout.addWidget(self.btn_import)

    def refresh_categories(self, categories):
        """Updates the dropdown with current category names."""
        self.combo_cat.clear()
        for cat in sorted(categories.values(), key=lambda x: x.index):
            self.combo_cat.addItem(f"[{cat.index}] {cat.display_name}", cat.index)

    def _add_folder_to_queue(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Add")
        if folder:
            p = Path(folder)
            # Scan and sort files immediately
            files = FileScanner.scan(folder, recursive=False)
            files.sort() # Ensure ascending order
            
            self.queue.append((p.name, files))
            self.preview.addItem(f"Header: [{p.name}] -> {len(files)} files")

    def _clear_queue(self):
        self.queue = []
        self.preview.clear()

    def _emit_import(self):
        if not self.queue:
            QMessageBox.warning(self, "Queue Empty", "Please add at least one folder to the queue.")
            return
        
        cat_idx = self.combo_cat.currentData()
        self.import_requested.emit(cat_idx, self.queue)
        self._clear_queue()

# ── Script Input Widget ────────────────────────────────────────────────────────
class ScriptInputWidget(QWidget):
    files_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        info = QLabel("Enter one path/title per line. Lines starting with # are comments. Numbered lines (1. path) are supported.")
        info.setWordWrap(True); info.setStyleSheet(f"color:{C['dim']};font-size:11px;")
        layout.addWidget(info)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("# Example:\n1. D:\\Videos\\intro.mp4\n2. D:\\Images\\bg.png\n# Or plain:\nD:\\Videos\\clip.mp4")
        self.editor.setFont(QFont("Consolas", 10)); layout.addWidget(self.editor)
        btn_row = QHBoxLayout()
        btn_clr = QPushButton("🗑️ Clear"); btn_clr.clicked.connect(self.editor.clear)
        btn_add = QPushButton("📦 Parse & Add"); btn_add.clicked.connect(self._parse)
        btn_add.setStyleSheet(f"background:{C['accent']};color:white;font-weight:bold;")
        btn_row.addWidget(btn_clr); btn_row.addStretch(); btn_row.addWidget(btn_add)
        layout.addLayout(btn_row)

    def _parse(self):
        self.categories = {}
        # 1. First, find and extract custom category names from CategorySettings
        cat_settings = self._orig_root.find('CategorySettings')
        custom_names = self._extract_category_names(cat_settings) if cat_settings is not None else {}
        
        # 2. Assign names to category objects
        for i in range(23): # 0 to 22
            name = custom_names.get(i, DEF_CAT_NAMES.get(i, f"Category {i}"))
            self.categories[i] = VmixCategory(index=i, name=name)

        # 3. Parse Inputs and put them in categories
        for el in self._orig_root:
            if el.tag != 'Input': continue
            inp = self._parse_input(el)
            ci = inp.category
            if ci in self.categories:
                self.categories[ci].inputs.append(inp)

        # Remove empty categories except the ones with custom names
        for i in list(self.categories.keys()):
            if i != 0 and not self.categories[i].inputs and i not in custom_names:
                del self.categories[i]

    def _extract_category_names(self, node: ET.Element) -> Dict[int, str]:
        """Maps XML tags like <Red.Text> to their numerical IDs."""
        names = {}
        # Mapping table based on vMix internal logic
        tag_to_id = {
            "Red.Text": 1, "Green.Text": 2, "Orange.Text": 3, 
            "Purple.Text": 4, "Aqua.Text": 5, "Blue.Text": 6
        }
        # Add Custom1-16 (mapped to 7-22)
        for i in range(1, 17):
            tag_to_id[f"Custom{i}.Text"] = i + 6

        for child in node:
            if child.tag in tag_to_id and child.text:
                names[tag_to_id[child.tag]] = child.text
        return names

# ── Category Import Widget ─────────────────────────────────────────────────────
class CategoryImportWidget(QWidget):
    structure_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent); self._structure = []
        layout = QVBoxLayout(self)
        info = QLabel("📂 Select a root folder. Each subfolder becomes a category, files inside become inputs.")
        info.setWordWrap(True); info.setStyleSheet(f"color:{C['dim']};font-size:11px;")
        layout.addWidget(info)
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText("Select root folder..."); self.path_edit.setReadOnly(True)
        btn_b = QPushButton("Browse..."); btn_b.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit); path_row.addWidget(btn_b); layout.addLayout(path_row)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(['Category / Input','Type','Count'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1,80); self.tree.setColumnWidth(2,60); layout.addWidget(self.tree)
        btn_row = QHBoxLayout()
        self.lbl = QLabel("No folder selected")
        btn_imp = QPushButton("🚀 Import All Categories"); btn_imp.clicked.connect(self._emit)
        btn_imp.setStyleSheet(f"background:{C['accent']};color:white;font-weight:bold;padding:8px 16px;")
        btn_row.addWidget(self.lbl); btn_row.addStretch(); btn_row.addWidget(btn_imp)
        layout.addLayout(btn_row)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if f: self.path_edit.setText(f); self._scan(f)

    def _scan(self, folder):
        self._structure = FileScanner.subfolders(folder)
        self.tree.clear(); total = 0
        icons = {'Video':'🎬','Image':'🖼️','Audio':'🎵','Unknown':'📄'}
        for name, files in self._structure:
            ci = QTreeWidgetItem([f"📁 {name}","Category",str(len(files))])
            ci.setForeground(0, QColor(C['accent'])); ci.setFont(0, QFont("Arial",10,QFont.Weight.Bold))
            for fp in files[:20]:
                ftype = FileScanner.detect(fp)
                QTreeWidgetItem(ci, [f"{icons.get(ftype,'📄')} {Path(fp).name}", ftype, ""])
            if len(files) > 20: QTreeWidgetItem(ci,[f"... +{len(files)-20} more","",""])
            self.tree.addTopLevelItem(ci); ci.setExpanded(True); total += len(files)
        self.lbl.setText(f"{len(self._structure)} categories, {total} files total")

    def _emit(self):
        if self._structure: self.structure_ready.emit(self._structure)

# ── Category Transform Widget ──────────────────────────────────────────────────
class CategoryTransformWidget(QWidget):
    request_swap = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        info = QLabel("🔄 Category Interchanger")
        info.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(info)

        desc = QLabel("Select two categories to swap their positions. All videos inside will move to the new position automatically.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C['dim']};")
        layout.addWidget(desc)

        # Selection Area
        swap_box = QHBoxLayout()
        
        self.list_a = QListWidget()
        self.list_b = QListWidget()
        
        swap_box.addWidget(self.list_a)
        mid_icon = QLabel("⇌")
        mid_icon.setFont(QFont("Arial", 24))
        swap_box.addWidget(mid_icon, 0, Qt.AlignmentFlag.AlignCenter)
        swap_box.addWidget(self.list_b)
        
        layout.addLayout(swap_box)

        self.btn_swap = QPushButton("🚀 Execute Swap & Reorganize")
        self.btn_swap.setFixedHeight(50)
        self.btn_swap.setStyleSheet(f"background:{C['accent']}; color:white; font-weight:bold; font-size:14px;")
        self.btn_swap.clicked.connect(self._on_swap_clicked)
        layout.addWidget(self.btn_swap)

    def refresh_lists(self, categories):
        self.list_a.clear()
        self.list_b.clear()
        # We don't swap Category 0 (ALL)
        items = [cat for cat in categories.values() if cat.index != 0]
        for cat in sorted(items, key=lambda x: x.index):
            txt = f"[{cat.index}] {cat.display_name} ({len(cat.inputs)} Items)"
            
            item_a = QListWidgetItem(txt)
            item_a.setData(Qt.ItemDataRole.UserRole, cat.index)
            self.list_a.addItem(item_a)
            
            item_b = QListWidgetItem(txt)
            item_b.setData(Qt.ItemDataRole.UserRole, cat.index)
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

class BigEditorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setMinimumHeight(40) 
        editor.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        editor.setStyleSheet(f"background: {C['bg2']}; color: white; border: 2px solid {C['accent']}; padding: 5px;")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        rect.setHeight(40) # Match height of row
        editor.setGeometry(rect)

# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        icon_file = "app_icon.ico" # Make sure your icon file is named this
        icon_path = resource_path(icon_file)
        
        # 1. Set the Window Icon
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        # 2. Windows Taskbar Fix (Prevents Windows from showing the default Python icon)
        if platform.system() == "Windows":
            myappid = f"mycompany.vmixmanager.{APP_VERSION}" # unique string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        # -----------------------------
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
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100, 700); self.resize(1280, 800)
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        self._build_toolbar()
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(self._build_cat_panel())
        sp.addWidget(self._build_right_panel())
        sp.setSizes([250,850]); sp.setStretchFactor(0,0); sp.setStretchFactor(1,1)
        ml.addWidget(sp, 1)
        ml.addWidget(self._build_log_panel())
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self):
        tb = QToolBar("Toolbar"); tb.setMovable(False)
        tb.setIconSize(QSize(18,18)); tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        self.act_new     = QAction("🆕 New",     self); self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_open    = QAction("📂 Open",    self); self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_save    = QAction("💾 Save",    self); self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_saveas  = QAction("💾 Save As…",self); self.act_saveas.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_expjson = QAction("📤 JSON",    self)
        self.act_expcsv  = QAction("📊 CSV",     self)
        for a in [self.act_new, self.act_open, self.act_save, self.act_saveas]: tb.addAction(a)
        tb.addSeparator()
        for a in [self.act_expjson, self.act_expcsv]: tb.addAction(a)
        tb.addSeparator()
        tb.addWidget(QLabel("🔍"))
        self.search = QLineEdit(); self.search.setPlaceholderText("Filter inputs…"); self.search.setMaximumWidth(200)
        self.search.setClearButtonEnabled(True); tb.addWidget(self.search)
        tb.addSeparator()
        self.file_lbl = QLabel("No file loaded"); self.file_lbl.setStyleSheet(f"color:{C['dim']};padding:0 8px;")
        tb.addWidget(self.file_lbl)

    def _on_folder_bulk_import(self, cat_idx: int, folder_data: list):
        """Processes the queue: Creates GT Header -> Adds Sorted Files."""
        added_count = 0
        
        for folder_name, file_paths in folder_data:
            # 1. Create the GT Title Header
            header_xml = f'<items><item name="Message.Text" version="2"><value>{folder_name}</value></item></items>'
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
            
            # 2. Add the sorted media files
            for fp in file_paths:
                self.parser.add_input(cat_idx, fp)
                added_count += 1
        
        self.parser.reorder(cat_idx)
        self._refresh_inputs()
        self._refresh_categories()
        self._mark_modified()
        self.tabs.setCurrentIndex(0) # Switch back to Input tab
        self.log(f"Imported {len(folder_data)} folders ({added_count} total items) to Category {cat_idx}", "SUCCESS")
    
    def _rename_input_inline(self):
        """Triggers the 'Big Editor' for the selected row's Title column."""
        row = self.tbl.currentRow()
        if row >= 0:
            item = self.tbl.item(row, 1) # Column 1 is Title
            self.tbl.editItem(item)

    def _replace_input_file(self):
        """Opens file browser to replace the file path of the selected input."""
        row = self.tbl.currentRow()
        if row < 0: return
        
        # Find the input object
        ki = self.tbl.item(row, 5) # Key column
        key = ki.data(Qt.ItemDataRole.UserRole)
        inp = next((i for i in self.current_cat.inputs if i.key == key), None)
        
        if not inp: return

        # Open File Browser
        new_file, _ = QFileDialog.getOpenFileName(self, "Replace Media File", "", "All Files (*)")
        
        if new_file:
            inp.file_path = os.path.normpath(new_file)
            # Optional: update title if it was default
            inp.original_title = Path(new_file).name 
            self._mark_modified()
            self._refresh_inputs()
            self.log(f"Replaced file for '{inp.original_title}'", "SUCCESS")

    def _tbl_context_menu(self, pos):
        item = self.tbl.itemAt(pos)
        if not item: return
        
        m = QMenu(self)
        # 1. Rename Option
        act_ren = m.addAction("✏️ Rename Title")
        act_ren.triggered.connect(self._rename_input_inline)
        
        # 2. Replace Option
        act_rep = m.addAction("🔄 Replace File (Browse)")
        act_rep.triggered.connect(self._replace_input_file)
        
        m.addSeparator()
        
        # 3. Open File
        act_open = m.addAction("📂 Open in Explorer")
        # Get path from column 3
        path = self.tbl.item(self.tbl.currentRow(), 3).text()
        act_open.triggered.connect(lambda: self._open_file_system(path))
        
        m.addSeparator()
        
        # 4. Remove Option
        act_rem = m.addAction("🗑️ Remove Input")
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
            # This line is key: it clears the sidebar and redraws it 
            # using the new names assigned to the category IDs.
            self._refresh_categories() 
            self.log(f"Swapped data between slot {idx_a} and {idx_b} safely.")
    
    def _build_cat_panel(self) -> QWidget:
        p = QWidget(); p.setMinimumWidth(200); p.setMaximumWidth(300)
        l = QVBoxLayout(p); l.setContentsMargins(8,8,4,8); l.setSpacing(6)
        hdr = QLabel("📋 Categories"); hdr.setFont(QFont("Arial",11,QFont.Weight.Bold)); l.addWidget(hdr)
        self.cat_list = QListWidget()
        self.cat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cat_list.customContextMenuRequested.connect(self._cat_context_menu)
        l.addWidget(self.cat_list)
        btn_row = QHBoxLayout()
        self.btn_add_cat = QPushButton("➕"); self.btn_add_cat.setMaximumWidth(36); self.btn_add_cat.setToolTip("Add category")
        self.btn_ren_cat = QPushButton("✏️"); self.btn_ren_cat.setMaximumWidth(36); self.btn_ren_cat.setToolTip("Rename category")
        self.btn_del_cat = QPushButton("🗑️"); self.btn_del_cat.setMaximumWidth(36); self.btn_del_cat.setToolTip("Delete category")
        for b in [self.btn_add_cat, self.btn_ren_cat, self.btn_del_cat]: btn_row.addWidget(b)
        btn_row.addStretch(); l.addLayout(btn_row)
        self.cat_stat = QLabel(""); self.cat_stat.setStyleSheet(f"color:{C['dim']};font-size:10px;"); l.addWidget(self.cat_stat)
        return p

    def _build_right_panel(self) -> QWidget:
        p = QWidget(); l = QVBoxLayout(p); l.setContentsMargins(4,8,8,8); l.setSpacing(8)
        self.tabs = QTabWidget(); l.addWidget(self.tabs)
        self.transform_w = CategoryTransformWidget()
        self.transform_w.request_swap.connect(self._handle_category_swap)
        self.tabs.addTab(self._build_input_tab(),   "📋 Inputs")
        self.tabs.addTab(self.transform_w,          "🔄 Transform")
        self.folder_w = FolderImportWidget()
        self.folder_w.import_requested.connect(self._on_folder_bulk_import)
        self.tabs.addTab(self.folder_w, "📁 Folder Import")
        self.tabs.addTab(self._build_file_tab(),    "🗂️ File Import")
        self.script_w = ScriptInputWidget(); self.script_w.files_ready.connect(self._on_script_entries)
        self.tabs.addTab(self.script_w, "📝 Script Input")
        self.catimport_w = CategoryImportWidget(); self.catimport_w.structure_ready.connect(self._on_cat_structure)
        self.tabs.addTab(self.catimport_w, "📂 Category Import")
        self.transform_w.refresh_lists(self.parser.categories)
        self.export_w = CategoryExportWidget()
        self.export_w.parser_ref = self.parser # Link to the parser
        self.tabs.addTab(self.export_w, "📤 Category Export")
        return p

    def _build_input_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        
        # ── Header Row (Label + Buttons) ──────────────────────────────────────
        hdr = QHBoxLayout()
        self.lbl_cat = QLabel("Select a category")
        self.lbl_cat.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        
        self.lbl_cnt = QLabel("")
        self.lbl_cnt.setStyleSheet(f"color:{C['dim']}; margin-left: 10px;")
        
        self.btn_add_inp = QPushButton("➕ Add Files")
        self.btn_add_inp.clicked.connect(self._add_inputs_dialog)
        
        self.btn_rem_inp = QPushButton("🗑️ Remove")
        self.btn_rem_inp.clicked.connect(self._remove_inputs)
        
        self.btn_mov_inp = QPushButton("📦 Move To…")
        self.btn_mov_inp.clicked.connect(self._move_inputs)
        
        hdr.addWidget(self.lbl_cat)
        hdr.addWidget(self.lbl_cnt)
        hdr.addStretch()
        for b in [self.btn_add_inp, self.btn_rem_inp, self.btn_mov_inp]:
            hdr.addWidget(b)
        l.addLayout(hdr)

        # ── Table Construction ────────────────────────────────────────────────
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(['#', 'Title', 'Type', 'File Path', 'Open', 'Key'])
        
        # 1. Apply the "Big Editor" for the Title Column (Index 1)
        # (Make sure the BigEditorDelegate class is defined in your script)
        self.tbl.setItemDelegateForColumn(1, BigEditorDelegate(self.tbl))

        # 2. General Table Settings
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._tbl_context_menu)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tbl.setSortingEnabled(True)
        self.tbl.setAlternatingRowColors(True)
        
        # 3. Row and Vertical Header Settings
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(45) # Taller rows for better readability

        # 4. Column Resizing (Enlarge all columns logic)
        hh = self.tbl.horizontalHeader()
        # Col 0: Index/Number
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(0, 50)
        
        # Col 1: Title (Auto-Stretch to take up most space)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Col 2: Type
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(2, 80)
        
        # Col 3: File Path (Stretch to take up remaining space)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        # Col 4: Open Button
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(4, 60)
        
        # Col 5: Key
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.tbl.setColumnWidth(5, 120)

        l.addWidget(self.tbl)
        return w

    def _build_file_tab(self) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w)
        info = QLabel("Select individual files to add to the currently selected category.")
        info.setStyleSheet(f"color:{C['dim']};"); l.addWidget(info)
        self.file_list = QListWidget(); self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        l.addWidget(self.file_list)
        btn_row = QHBoxLayout()
        btn_b = QPushButton("📂 Browse Files"); btn_b.clicked.connect(self._browse_files)
        btn_c = QPushButton("🗑️ Clear"); btn_c.clicked.connect(self.file_list.clear)
        btn_a = QPushButton("➕ Add to Category"); btn_a.clicked.connect(self._add_listed_files)
        btn_a.setStyleSheet(f"background:{C['accent']};color:white;font-weight:bold;")
        btn_row.addWidget(btn_b); btn_row.addWidget(btn_c); btn_row.addStretch(); btn_row.addWidget(btn_a)
        l.addLayout(btn_row)
        return w

    def _build_log_panel(self) -> QWidget:
        p = QGroupBox("📋 Activity Log"); p.setMaximumHeight(150)
        l = QVBoxLayout(p); l.setContentsMargins(4,4,4,4)
        self.log_w = LogWidget(); l.addWidget(self.log_w)
        return p

    def _open_file_system(self, file_path):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"File does not exist:\n{file_path}")
            return
        
        try:
            if platform.system() == "Windows":
                # Opens file with default app and selects it in Explorer
                os.startfile(file_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.run(["open", file_path])
            else: # Linux
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
        title = f"{APP_NAME} v{APP_VERSION}"
        if self.parser.file_path:
            title += f" — {Path(self.parser.file_path).name} *"
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
        
        for cat in sorted(self.parser.categories.values(), key=lambda c: c.index):
            display_text = f"{cat.display_name} ({cat.count()})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cat.index)
            if not cat.enabled:
                item.setForeground(QColor(C['dim']))
            else:
                item.setForeground(QColor(C['text']))
            # Add the Checkbox
            if cat.index > 0: # Category 0 (ALL) is usually always visible
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if cat.enabled else Qt.CheckState.Unchecked)
            
            self.cat_list.addItem(item)
            if cat.index == prev_idx:
                self.cat_list.setCurrentItem(item)
        
        self.cat_list.blockSignals(False)
        self.transform_w.refresh_lists(self.parser.categories)
        self.folder_w.refresh_categories(self.parser.categories)

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
                self._refresh_categories()
                self._mark_modified()
                self.log(f"Added category [{cat.index}] '{cat.display_name}'", "SUCCESS")
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _rename_category(self, *_):
        idx = self._current_cat_idx()
        if idx is None or idx == 0: return # Don't rename 'ALL'
        
        cat = self.parser.categories[idx]
        curr_display = "" if cat.name == "Empty Cat" else cat.name
        
        name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=curr_display)
        
        if ok:
            new_name = name.strip()
            if not new_name:
                cat.name = "Empty Cat"
                cat.enabled = False # Auto-disable if empty
                self.log(f"Category {idx} cleared and disabled.")
            else:
                cat.name = new_name
                # Optional: Auto-enable if the user just gave it a name
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
        self.current_cat = None; self._refresh_categories(); self._mark_modified()
        self.log(f"Deleted category [{idx}] '{cat.display_name}'", "WARNING")

    def _cat_context_menu(self, pos):
        item = self.cat_list.itemAt(pos)
        if not item: return
        m = QMenu(self)
        m.addAction("✏️ Rename", self._rename_category)
        m.addAction("🗑️ Delete", self._delete_category)
        m.exec(self.cat_list.mapToGlobal(pos))

    # ── Input ops ──────────────────────────────────────────────────────────────
    def _refresh_inputs(self):
        if not self.current_cat:
            self.tbl.setRowCount(0)
            self.lbl_cat.setText("Select a category")
            self.lbl_cnt.setText("")
            return

        # CHANGE THIS LINE: Remove .upper()
        self.lbl_cat.setText(f"     {self.current_cat.display_name}")
        self.lbl_cnt.setText(f"({self.current_cat.count()} inputs)")

        self.tbl.blockSignals(True)
        self.tbl.setSortingEnabled(False)
        
        flt = self.search.text().lower()
        inputs = [i for i in self.current_cat.inputs 
                  if not flt or flt in i.original_title.lower() or flt in i.file_path.lower()]
        
        self.tbl.setRowCount(len(inputs))
        
        for r, inp in enumerate(inputs):
            # 1. Input # (Position)
            num_item = QTableWidgetItem(str(r + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 0, num_item)

            # 2. Title
            self.tbl.setItem(r, 1, QTableWidgetItem(inp.original_title))

            # 3. Type
            ti = QTableWidgetItem(inp.type_name)
            ti.setFlags(ti.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, ti)

            # 4. File Path
            self.tbl.setItem(r, 3, QTableWidgetItem(inp.file_path))

            # 5. Open Button
            btn_open = QPushButton("📂")
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setStyleSheet("QPushButton { border:none; background:transparent; font-size:16px; }")
            btn_open.clicked.connect(lambda ch, p=inp.file_path: self._open_file_system(p))
            self.tbl.setCellWidget(r, 4, btn_open)

            # 6. Key
            ki = QTableWidgetItem(inp.key[:12]+"…" if len(inp.key)>12 else inp.key)
            ki.setData(Qt.ItemDataRole.UserRole, inp.key) # Important for identification
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
        key = ki.data(Qt.ItemDataRole.UserRole) or ki.text().replace("…","")
        inp = next((i for i in (self.current_cat.inputs if self.current_cat else []) if i.key.startswith(key[:12])), None)
        if not inp: return
        if item.column() == 1: inp.original_title = item.text()
        elif item.column() == 3: inp.file_path = item.text()
        self._mark_modified()

    def _add_inputs_dialog(self):
        if not self.current_cat:
            QMessageBox.warning(self, "No Category", "Please select a category first."); return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Media Files", "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav *.aac *.flac);;All Files (*)")
        if files: self._add_files_to_current(files)

    def _add_files_to_current(self, entries: List[str]):
        if not self.current_cat:
            QMessageBox.warning(self, "No Category", "Select a category first."); return
        added = 0
        for path in entries:
            path = os.path.normpath(path.strip())
            if os.path.isdir(path):
                # If path is a folder, scan for images/videos inside it
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
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Added {added} input(s) to '{self.current_cat.display_name}'", "SUCCESS")

    def _remove_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        r = QMessageBox.question(self, "Remove", f"Remove {len(inputs)} input(s)?")
        if r != QMessageBox.StandardButton.Yes: return
        for inp in inputs: self.parser.remove_input(inp)
        self.parser.reorder(self.current_cat.index)
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Removed {len(inputs)} input(s)", "WARNING")

    def _move_inputs(self):
        inputs = self._get_selected_inputs()
        if not inputs: return
        choices = {str(c.index): c.display_name for c in self.parser.categories.values()
                   if c.index != self.current_cat.index}
        if not choices: QMessageBox.information(self, "Move", "No other categories available."); return
        keys = list(choices.keys())
        labels = [f"[{k}] {choices[k]}" for k in keys]
        choice, ok = QInputDialog.getItem(self, "Move Inputs", "Move to:", labels, 0, False)
        if not ok: return
        target = int(keys[labels.index(choice)])
        for inp in inputs:
            self.parser.remove_input(inp)
            inp.category = target
            inp.position = max((i.position for i in self.parser.categories[target].inputs), default=-1)+1
            self.parser.categories[target].inputs.append(inp)
        self._refresh_inputs(); self._refresh_categories(); self._mark_modified()
        self.log(f"Moved {len(inputs)} input(s) to [{target}]", "SUCCESS")

    def _tbl_context_menu(self, pos):
        item = self.tbl.itemAt(pos)
        if not item: return
        m = QMenu(self)
        m.addAction("🗑️ Remove", self._remove_inputs)
        m.addAction("📦 Move To…", self._move_inputs)
        m.addSeparator()
        m.addAction("📋 Copy Path", lambda: (
            QApplication.clipboard().setText(self.tbl.item(self.tbl.currentRow(), 3).text()
                                              if self.tbl.item(self.tbl.currentRow(),3) else "")))
        m.exec(self.tbl.mapToGlobal(pos))

    # ── Import handlers ────────────────────────────────────────────────────────
    def _on_folder_files(self, files): self._add_files_to_current(files); self.tabs.setCurrentIndex(0)
    def _on_script_entries(self, entries): self._add_files_to_current(entries); self.tabs.setCurrentIndex(0)

    def _on_cat_structure(self, structure: List[Tuple[str, List[str]]]):
        added_cats, added_inputs = 0, 0
        for folder_name, files in structure:
            # Find or create category
            existing = next((c for c in self.parser.categories.values()
                             if c.display_name.lower() == folder_name.lower()), None)
            if existing:
                cat = existing
            else:
                try:
                    cat = self.parser.add_category(folder_name); added_cats += 1
                except ValueError:
                    self.log(f"Category limit reached, skipping '{folder_name}'", "WARNING"); continue
            for fp in files:
                self.parser.add_input(cat.index, fp); added_inputs += 1
        self._refresh_categories(); self._mark_modified()
        self.log(f"Imported {added_cats} categories, {added_inputs} inputs", "SUCCESS")
        self.tabs.setCurrentIndex(0)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "",
            "Media Files (*.mp4 *.avi *.mov *.mkv *.jpg *.jpeg *.png *.bmp *.gif *.mp3 *.wav);;All Files (*)")
        icons = {'Video':'🎬','Image':'🖼️','Audio':'🎵','Unknown':'📄'}
        for fp in files:
            item = QListWidgetItem(f"{icons.get(FileScanner.detect(fp),'📄')} {Path(fp).name}")
            item.setToolTip(fp); self.file_list.addItem(item)

    def _add_listed_files(self):
        files = [self.file_list.item(i).toolTip() for i in range(self.file_list.count())]
        if files: self._add_files_to_current(files); self.tabs.setCurrentIndex(0)

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
        self.parser.create_new(); self.current_cat = None
        self._refresh_categories(); self.modified = False
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}"); self.file_lbl.setText("New file")
        self.log("New production created", "SUCCESS")

    def _open(self):
        if not self._check_save(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open .vmix File", "", "vMix Files (*.vmix);;All Files (*)")
        if not path: return
        if self.parser.load(path):
            self.current_cat = None
            self._refresh_categories() # This will now also update your Transform tab
            self.modified = False
            self.setWindowTitle(f"{APP_NAME} — {Path(path).name}")
            self.file_lbl.setText(Path(path).name)
            n = sum(c.count() for c in self.parser.categories.values())
            self.log(f"Loaded '{Path(path).name}' — {len(self.parser.categories)} categories, {n} inputs", "SUCCESS")
        else:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{path}")

    def _save(self) -> bool:
        if not self.parser.file_path: return self._save_as()
        if self.parser.save(self.parser.file_path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME} — {Path(self.parser.file_path).name}")
            self.log(f"Saved '{Path(self.parser.file_path).name}'", "SUCCESS"); return True
        QMessageBox.critical(self, "Error", "Save failed."); return False

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save .vmix File", "", "vMix Files (*.vmix)")
        if not path: return False
        if not path.endswith('.vmix'): path += '.vmix'
        if self.parser.save(path):
            self.modified = False
            self.setWindowTitle(f"{APP_NAME} — {Path(path).name}")
            self.file_lbl.setText(Path(path).name)
            self.log(f"Saved as '{Path(path).name}'", "SUCCESS"); return True
        QMessageBox.critical(self, "Error", "Save failed."); return False

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if not path: return
        if not path.endswith('.json'): path += '.json'
        self.parser.export_json(path); self.log(f"Exported JSON: {Path(path).name}", "SUCCESS")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path: return
        if not path.endswith('.csv'): path += '.csv'
        self.parser.export_csv(path); self.log(f"Exported CSV: {Path(path).name}", "SUCCESS")

    def closeEvent(self, event):
        if self._check_save(): event.accept()
        else: event.ignore()

    def _apply_style(self):
        self.setStyleSheet(f"""
        QMainWindow, QWidget {{ 
            background: {C['bg']}; 
            color: {C['text']}; 
        }}
        QToolBar {{ 
            background: {C['bg2']}; 
            border-bottom: 1px solid {C['border']}; 
        }}
        QToolButton {{ 
            color: {C['text']}; 
            background: transparent; 
            border: 1px solid transparent; 
            border-radius: 4px; 
            padding: 4px 10px; 
        }}
        QToolButton:hover {{ 
            background: {C['hi']}; 
            border-color: {C['accent']}; 
        }}
        QListWidget {{ 
            background: {C['bg2']}; 
            border: 1px solid {C['border']}; 
            border-radius: 6px; 
            outline: none; 
        }}
        QListWidget::item {{ 
            padding: 8px 12px; 
            border-radius: 4px; 
            margin: 2px 4px; 
        }}
        QListWidget::item:selected {{ 
            background: {C['accent']}; 
            color: white; 
        }}

        /* --- TABLE SELECTION FIX START (Double Braces used here) --- */
        QTableWidget {{ 
            background: {C['bg2']}; 
            border: 1px solid {C['border']}; 
            gridline-color: {C['border']}; 
            outline: none; 
        }}
        QTableWidget::item {{ 
            padding: 6px 8px; 
        }}
        
        QTableWidget::item:selected, 
        QTableWidget::item:selected:active,
        QTableWidget::item:selected:!active {{ 
            background-color: {C['accent']} !important; 
            color: white !important; 
        }}

        QTableWidget::item:alternate {{ 
            background: {C['alt']}; 
        }}

        QTableWidget::item:alternate:selected {{ 
            background-color: {C['accent']} !important; 
            color: white !important; 
        }}
        /* --- TABLE SELECTION FIX END --- */

        QHeaderView::section {{ 
            background: {C['bg']}; 
            color: {C['text']}; 
            padding: 8px; 
            border: none; 
            border-bottom: 2px solid {C['accent']}; 
            font-weight: bold; 
        }}
        QTabWidget::pane {{ 
            background: {C['bg2']}; 
            border: 1px solid {C['border']}; 
            border-radius: 6px; 
        }}
        QTabBar::tab {{ 
            background: {C['bg']}; 
            color: {C['dim']}; 
            padding: 8px 16px; 
            margin-right: 2px; 
            border-radius: 6px 6px 0 0; 
        }}
        QTabBar::tab:selected {{ 
            background: {C['bg2']}; 
            color: {C['text']}; 
            border-top: 2px solid {C['accent']}; 
        }}
        QPushButton {{ 
            background: {C['bg2']}; 
            color: {C['text']}; 
            border: 1px solid {C['border']}; 
            border-radius: 4px; 
            padding: 6px 12px; 
        }}
        QPushButton:hover {{ 
            background: {C['hi']}; 
            border-color: {C['accent']}; 
        }}
        QLineEdit, QPlainTextEdit, QTextEdit {{ 
            background: {C['bg2']}; 
            color: {C['text']}; 
            border: 1px solid {C['border']}; 
            border-radius: 4px; 
            padding: 5px 8px; 
        }}
        QScrollBar:vertical {{ 
            background: {C['bg']}; 
            width: 8px; 
        }}
        QScrollBar::handle:vertical {{ 
            background: {C['border']}; 
            border-radius: 4px; 
        }}
        """)

# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
