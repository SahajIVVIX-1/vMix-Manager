#!/usr/bin/env python3
"""
vMix Script Manager
===================
A PyQt6 application for managing vMix .vmix production files.
"""

import sys, os, json, csv, uuid, copy, re, logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QToolBar, QLabel, QPushButton, QLineEdit, QPlainTextEdit,
    QFileDialog, QMessageBox, QInputDialog, QTabWidget, QGroupBox,
    QCheckBox, QHeaderView, QAbstractItemView, QTextEdit, QMenu,
    QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME, APP_VERSION = "vMix Script Manager", "1.0.0"

VIDEO_EXTS = {'.mp4','.avi','.mov','.mkv','.wmv','.flv','.m4v','.webm','.ts','.mts'}
IMAGE_EXTS = {'.jpg','.jpeg','.png','.bmp','.gif','.tiff','.tga','.webp'}
AUDIO_EXTS = {'.mp3','.wav','.aac','.flac','.ogg','.wma','.m4a'}
ALL_MEDIA  = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

# Change 2 to 0 for Video
INPUT_TYPES = {1:"Image", 0:"Video", 3:"Audio", 6:"Desktop", 7:"NDI", 12:"Title", 20:"Camera"}

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

C = {
    'bg':      '#1E1E2E', 'bg2':    '#2A2A3E', 'accent':  '#7C3AED',
    'text':    '#E0E0F0', 'dim':    '#A0A0C0', 'border':  '#3A3A5A',
    'ok':      '#10B981', 'warn':   '#F59E0B', 'err':     '#EF4444',
    'hi':      '#4C1D95', 'alt':    '#252538',
}

# ── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class VmixInput:
    key: str = ""
    original_title: str = ""
    input_type: int = 1
    category: int = 0
    position: int = 0
    file_path: str = ""
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
            logging.error(f"Load failed: {e}"); return False

    def _parse(self):
        self.categories = {}
        name_map = {}
        
        # 1. FIND CATEGORY NAMES FROM <CategorySettings>
        cs_node = self._orig_root.find('CategorySettings')
        if cs_node is not None:
            for child in cs_node:
                if child.tag in CAT_ID_LOOKUP and child.text:
                    name_map[CAT_ID_LOOKUP[child.tag]] = child.text

        # 2. PRE-INITIALIZE CATEGORIES 0-22
        for i in range(23):
            # If XML has a specific name (e.g. 1_Guruji_Special), use it.
            # Otherwise use a generic fallback.
            name = name_map.get(i)
            if not name:
                if i == 0: name = "ALL"
                else: name = f"Category {i}"
            self.categories[i] = VmixCategory(index=i, name=name)

        # 3. ASSIGN INPUTS
        for el in self._orig_root:
            if el.tag != 'Input': continue
            inp = self._parse_input(el)
            if inp.category in self.categories:
                self.categories[inp.category].inputs.append(inp)

        # 4. FILTER: Show only categories that have names OR have files
        for i in list(self.categories.keys()):
            if i == 0: continue # Always keep ALL
            has_files = len(self.categories[i].inputs) > 0
            has_custom_name = i in name_map and name_map[i].strip() != ""
            if not has_files and not has_custom_name:
                del self.categories[i]

    def _parse_input(self, el: ET.Element) -> VmixInput:
        a = el.attrib
        fp = (el.text or "").strip()
        it = int(a.get('Type','1'))
        return VmixInput(
            key=a.get('Key', str(uuid.uuid4())),
            original_title=a.get('OriginalTitle', Path(fp).name if fp else 'Unknown'),
            input_type=it,
            category=int(a.get('Category','0')),
            position=int(a.get('Position','0')),
            file_path=fp,
            state=a.get('State','1'), muted=a.get('Muted','True'),
            volume_f=a.get('VolumeF','1'), loop=a.get('Loop','False'),
            extra_attrs={k:v for k,v in a.items() if k not in {'Key','OriginalTitle','Type','Category','Position','State','Muted','VolumeF','Loop'}}
        )

    def save(self, path: str) -> bool:
        try:
            root = ET.Element('XML')
            ET.SubElement(root, 'Version').text = self.vmix_version
            ET.SubElement(root, 'ZoomManager')
            for cat in sorted(self.categories.values(), key=lambda c:c.index):
                for inp in sorted(cat.inputs, key=lambda x:x.position):
                    root.append(self._build_el(inp))
            if self._orig_root is not None:
                for el in self._orig_root:
                    if el.tag not in ('Version', 'ZoomManager', 'Input'):
                        root.append(copy.deepcopy(el))
            tree = ET.ElementTree(root)
            with open(path, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=False)
            self.file_path = path; return True
        except Exception as e:
            logging.error(f"Save failed: {e}"); return False

    def _build_el(self, inp: VmixInput) -> ET.Element:
        attrs = {
            'Type': str(inp.input_type), 'Position': str(inp.position), 'State': '1',
            'OriginalTitle': inp.original_title, 'Key': inp.key or str(uuid.uuid4()),
            'Loop': inp.loop, 'Muted': inp.muted, 'VolumeF': '1', 'AspectRatio': '100',
            'Category': str(inp.category), 'FrameDelay': '0', 'VideoShader_Alpha': '1',
            'VideoShader_White': '1', 'VideoShader_ClippingX2': '1', 'VideoShader_ClippingY2': '1',
            'Positions': self.default_pos
        }
        attrs.update(inp.extra_attrs)
        el = ET.Element('Input', attrib=attrs)
        if inp.file_path: el.text = inp.file_path.strip()
        return el

    def create_new(self):
        self.categories = {0: VmixCategory(index=0, name="ALL")}
        self._orig_root = None; self.file_path = ""

    def save(self, path: str) -> bool:
        try:
            root = ET.Element('XML')
            ET.SubElement(root, 'Version').text = self.vmix_version
            ET.SubElement(root, 'ZoomManager')
            
            # Add Inputs
            for cat in sorted(self.categories.values(), key=lambda c:c.index):
                for inp in sorted(cat.inputs, key=lambda x:x.position):
                    root.append(self._build_el(inp))
            
            # Copy all other settings (CategorSettings, AudioMaster, etc.)
            if self._orig_root is not None:
                for el in self._orig_root:
                    if el.tag not in ('Version', 'ZoomManager', 'Input'):
                        root.append(copy.deepcopy(el))
            
            # Write file
            tree = ET.ElementTree(root)
            with open(path, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=False)
            
            self.file_path = path
            return True
        except Exception as e:
            logging.error(f"Save failed: {e}"); return False

    def _build_el(self, inp: VmixInput) -> ET.Element:
        ext = Path(inp.file_path).suffix.lower()
        vmix_type = "0" if ext in VIDEO_EXTS else "1"
        
        attrs = {
            'Type': vmix_type,
            'Position': str(inp.position),
            'State': '1',
            'OriginalTitle': inp.original_title,
            'Key': inp.key or str(uuid.uuid4()),
            'Loop': inp.loop,
            'Muted': inp.muted,
            'VolumeF': '1',
            'AspectRatio': '100',
            'Category': str(inp.category),
            'FrameDelay': '0',
            # --- SHADER FIXES ---
            'VideoShader_Alpha': '1',
            'VideoShader_White': '1',
            'VideoShader_Saturation': '1',
            # CRITICAL: These must be 1, or the video is cropped to 0x0 size (Black)
            'VideoShader_ClippingX1': '0',
            'VideoShader_ClippingX2': '1', 
            'VideoShader_ClippingY1': '0',
            'VideoShader_ClippingY2': '1',
            # --- RENDERER FIX ---
            'Positions': self.default_pos
        }
        
        # This keeps any existing settings if you are editing a file
        attrs.update(inp.extra_attrs)
        
        el = ET.Element('Input', attrib=attrs)
        if inp.file_path:
            el.text = inp.file_path.strip()
        return el

    # --- Sidecar and Category Helpers (Existing) ---
    def _sidecar(self, path): return str(Path(path).with_suffix('.vmix_names.json'))
    def _load_names(self, path):
        sc = self._sidecar(path)
        if not os.path.exists(sc): return
        try:
            with open(sc) as f: data = json.load(f)
            for k, v in data.items():
                if int(k) in self.categories: self.categories[int(k)].name = v
        except: pass

    def _save_names(self, path):
        names = {str(c.index): c.name for c in self.categories.values() if c.name}
        if names:
            with open(self._sidecar(path),'w') as f: json.dump(names, f, indent=2)

    def add_category(self, name: str) -> VmixCategory:
        idx = next((i for i in range(100) if i not in self.categories), 0)
        cat = VmixCategory(index=idx, name=name)
        self.categories[idx] = cat; return cat

    def add_input(self, cat_idx: int, file_path: str, title: str = "") -> VmixInput:
        if cat_idx not in self.categories: raise ValueError(f"Category {cat_idx} missing")
        ext = Path(file_path).suffix.lower()
        it = 0 if ext in VIDEO_EXTS else 1
        pos = max((i.position for i in self.categories[cat_idx].inputs), default=-1) + 1
        inp = VmixInput(key=str(uuid.uuid4()), original_title=title or Path(file_path).name,
                        input_type=it, category=cat_idx, position=pos, file_path=file_path)
        self.categories[cat_idx].inputs.append(inp); return inp

    def remove_input(self, inp: VmixInput):
        cat = self.categories.get(inp.category)
        if cat:
            try: cat.inputs.remove(inp)
            except ValueError: pass

    def reorder(self, cat_idx: int):
        if cat_idx in self.categories:
            for i, inp in enumerate(self.categories[cat_idx].inputs): inp.position = i

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
    files_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent); self.found = []
        layout = QVBoxLayout(self)
        # Path row
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText("Select folder..."); self.path_edit.setReadOnly(True)
        btn_b = QPushButton("Browse..."); btn_b.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit); path_row.addWidget(btn_b)
        layout.addLayout(path_row)
        # Options
        opt = QHBoxLayout()
        self.cb_rec = QCheckBox("Recursive"); self.cb_vid = QCheckBox("Videos"); self.cb_vid.setChecked(True)
        self.cb_img = QCheckBox("Images"); self.cb_img.setChecked(True); self.cb_aud = QCheckBox("Audio"); self.cb_aud.setChecked(True)
        for w in [self.cb_rec, self.cb_vid, self.cb_img, self.cb_aud]: opt.addWidget(w)
        opt.addStretch(); layout.addLayout(opt)
        # Preview
        self.preview = QListWidget(); self.preview.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.preview)
        # Buttons
        btn_row = QHBoxLayout()
        self.lbl_count = QLabel("0 files")
        btn_scan = QPushButton("🔍 Scan"); btn_scan.clicked.connect(self._scan)
        btn_add = QPushButton("➕ Add to Category"); btn_add.clicked.connect(self._emit)
        btn_add.setStyleSheet(f"background:{C['accent']};color:white;font-weight:bold;")
        btn_row.addWidget(self.lbl_count); btn_row.addStretch(); btn_row.addWidget(btn_scan); btn_row.addWidget(btn_add)
        layout.addLayout(btn_row)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f: self.path_edit.setText(f); self._scan()

    def _scan(self):
        folder = self.path_edit.text()
        if not folder or not os.path.isdir(folder): return
        exts = set()
        if self.cb_vid.isChecked(): exts |= VIDEO_EXTS
        if self.cb_img.isChecked(): exts |= IMAGE_EXTS
        if self.cb_aud.isChecked(): exts |= AUDIO_EXTS
        self.found = FileScanner.scan(folder, self.cb_rec.isChecked(), exts)
        self.preview.clear()
        icons = {'Video':'🎬','Image':'🖼️','Audio':'🎵','Unknown':'📄'}
        for fp in self.found:
            item = QListWidgetItem(f"{icons.get(FileScanner.detect(fp),'📄')} {Path(fp).name}")
            item.setToolTip(fp); self.preview.addItem(item)
        self.lbl_count.setText(f"{len(self.found)} files")

    def _emit(self):
        sel = self.preview.selectedItems()
        files = [self.found[self.preview.row(i)] for i in sel] if sel else self.found
        if files: self.files_ready.emit(files)

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

# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser = VmixParser()
        self.current_cat: Optional[VmixCategory] = None
        self.modified = False
        self._build_ui()
        self._apply_style()
        self._connect()
        self.parser.create_new()
        self._refresh_categories()
        self.log("vMix Script Manager ready.", "SUCCESS")

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
        self.tabs.addTab(self._build_input_tab(),   "📋 Inputs")
        self.folder_w = FolderImportWidget(); self.folder_w.files_ready.connect(self._on_folder_files)
        self.tabs.addTab(self.folder_w, "📁 Folder Import")
        self.tabs.addTab(self._build_file_tab(),    "🗂️ File Import")
        self.script_w = ScriptInputWidget(); self.script_w.files_ready.connect(self._on_script_entries)
        self.tabs.addTab(self.script_w, "📝 Script Input")
        self.catimport_w = CategoryImportWidget(); self.catimport_w.structure_ready.connect(self._on_cat_structure)
        self.tabs.addTab(self.catimport_w, "📂 Category Import")
        return p

    def _build_input_tab(self) -> QWidget:
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0)
        hdr = QHBoxLayout()
        self.lbl_cat = QLabel("Select a category"); self.lbl_cat.setFont(QFont("Arial",10,QFont.Weight.Bold))
        self.lbl_cnt = QLabel(""); self.lbl_cnt.setStyleSheet(f"color:{C['dim']};")
        self.btn_add_inp = QPushButton("➕ Add Files"); self.btn_add_inp.clicked.connect(self._add_inputs_dialog)
        self.btn_rem_inp = QPushButton("🗑️ Remove");   self.btn_rem_inp.clicked.connect(self._remove_inputs)
        self.btn_mov_inp = QPushButton("📦 Move To…"); self.btn_mov_inp.clicked.connect(self._move_inputs)
        hdr.addWidget(self.lbl_cat); hdr.addWidget(self.lbl_cnt); hdr.addStretch()
        for b in [self.btn_add_inp, self.btn_rem_inp, self.btn_mov_inp]: hdr.addWidget(b)
        l.addLayout(hdr)
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5); self.tbl.setHorizontalHeaderLabels(['#','Title','Type','File Path','Key'])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._tbl_context_menu)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tbl.setSortingEnabled(True); self.tbl.verticalHeader().setVisible(False)
        self.tbl.setAlternatingRowColors(True)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.tbl.setColumnWidth(0,45); self.tbl.setColumnWidth(2,75); self.tbl.setColumnWidth(4,110)
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
            # Show the name from vMix and the count in your specific format
            display_text = f"{cat.display_name} ({cat.count()} Files)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cat.index)
            self.cat_list.addItem(item)
            
            if cat.index == prev_idx:
                self.cat_list.setCurrentItem(item)
        
        self.cat_list.blockSignals(False)
        if prev_idx is not None and prev_idx in self.parser.categories:
            self.current_cat = self.parser.categories[prev_idx]
            self._refresh_inputs()
            
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
        if idx is None: return
        cat = self.parser.categories[idx]
        name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=cat.display_name)
        if ok and name.strip():
            cat.name = name.strip()
            self._refresh_categories(); self._mark_modified()
            self.log(f"Renamed category {idx} to '{name.strip()}'")

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
            self.tbl.setRowCount(0); self.lbl_cat.setText("Select a category"); self.lbl_cnt.setText(""); return
        self.lbl_cat.setText(f"[{self.current_cat.index}] {self.current_cat.display_name}")
        self.lbl_cnt.setText(f"({self.current_cat.count()} inputs)")
        flt = self.search.text().lower()
        self.tbl.blockSignals(True); self.tbl.setSortingEnabled(False)
        inputs = [i for i in self.current_cat.inputs
                  if not flt or flt in i.original_title.lower() or flt in i.file_path.lower()]
        self.tbl.setRowCount(len(inputs))
        for r, inp in enumerate(inputs):
            self.tbl.setItem(r, 0, QTableWidgetItem(str(inp.position)))
            self.tbl.setItem(r, 1, QTableWidgetItem(inp.original_title))
            ti = QTableWidgetItem(inp.type_name); ti.setFlags(ti.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, ti)
            pi = QTableWidgetItem(inp.file_path); pi.setToolTip(inp.file_path)
            self.tbl.setItem(r, 3, pi)
            ki = QTableWidgetItem(inp.key[:12]+"…" if len(inp.key)>12 else inp.key)
            ki.setFlags(ki.flags() & ~Qt.ItemFlag.ItemIsEditable); ki.setData(Qt.ItemDataRole.UserRole, inp.key)
            self.tbl.setItem(r, 4, ki)
        self.tbl.setSortingEnabled(True); self.tbl.blockSignals(False)

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
            self.current_cat = None; self._refresh_categories()
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

    # ── Style ──────────────────────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet(f"""
        QMainWindow,QWidget{{background:{C['bg']};color:{C['text']};}}
        QToolBar{{background:{C['bg2']};border-bottom:1px solid {C['border']};}}
        QToolButton{{color:{C['text']};background:transparent;border:1px solid transparent;border-radius:4px;padding:4px 10px;}}
        QToolButton:hover{{background:{C['hi']};border-color:{C['accent']};}}
        QToolButton:pressed{{background:{C['accent']};}}
        QListWidget{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;outline:none;}}
        QListWidget::item{{padding:8px 12px;border-radius:4px;margin:2px 4px;}}
        QListWidget::item:selected{{background:{C['accent']};color:white;}}
        QListWidget::item:hover:!selected{{background:{C['hi']};}}
        QTableWidget{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;gridline-color:{C['border']};outline:none;}}
        QTableWidget::item{{padding:6px 8px;}}
        QTableWidget::item:selected{{background:{C['accent']};color:white;}}
        QTableWidget::item:alternate{{background:{C['alt']};}}
        QHeaderView::section{{background:{C['bg']};color:{C['text']};padding:8px;border:none;border-bottom:2px solid {C['accent']};font-weight:bold;}}
        QTabWidget::pane{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;}}
        QTabBar::tab{{background:{C['bg']};color:{C['dim']};padding:8px 16px;margin-right:2px;border-radius:6px 6px 0 0;}}
        QTabBar::tab:selected{{background:{C['bg2']};color:{C['text']};border-top:2px solid {C['accent']};}}
        QTabBar::tab:hover:!selected{{background:{C['hi']};color:{C['text']};}}
        QPushButton{{background:{C['bg2']};color:{C['text']};border:1px solid {C['border']};border-radius:4px;padding:6px 12px;}}
        QPushButton:hover{{background:{C['hi']};border-color:{C['accent']};}}
        QPushButton:pressed{{background:{C['accent']};}}
        QLineEdit,QPlainTextEdit,QTextEdit{{background:{C['bg2']};color:{C['text']};border:1px solid {C['border']};border-radius:4px;padding:5px 8px;}}
        QLineEdit:focus,QPlainTextEdit:focus{{border-color:{C['accent']};}}
        QGroupBox{{border:1px solid {C['border']};border-radius:6px;margin-top:8px;padding-top:8px;font-weight:bold;}}
        QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;padding:0 8px;background:{C['bg']};}}
        QScrollBar:vertical{{background:{C['bg']};width:8px;border-radius:4px;}}
        QScrollBar::handle:vertical{{background:{C['border']};border-radius:4px;min-height:20px;}}
        QScrollBar::handle:vertical:hover{{background:{C['accent']};}}
        QScrollBar:horizontal{{background:{C['bg']};height:8px;border-radius:4px;}}
        QScrollBar::handle:horizontal{{background:{C['border']};border-radius:4px;min-width:20px;}}
        QStatusBar{{background:{C['bg2']};color:{C['dim']};border-top:1px solid {C['border']};}}
        QSplitter::handle{{background:{C['border']};width:2px;}}
        QCheckBox{{color:{C['text']};spacing:6px;}}
        QCheckBox::indicator{{width:16px;height:16px;border:1px solid {C['border']};border-radius:3px;background:{C['bg2']};}}
        QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}
        QTreeWidget{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;}}
        QTreeWidget::item:selected{{background:{C['accent']};}}
        QMenu{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;}}
        QMenu::item{{padding:6px 20px;}}
        QMenu::item:selected{{background:{C['accent']};}}
        QInputDialog,QMessageBox{{background:{C['bg']};color:{C['text']};}}
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
