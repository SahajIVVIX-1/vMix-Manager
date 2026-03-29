"""
Helper script: embeds app_icon.ico as base64 into vMix-Manager.py
and fixes both window-title-bar icon and taskbar icon.
Run once from the vMIx directory:  python _embed_icon.py
"""
import base64, re, sys

b64 = open('icon_b64.txt').read().strip()
src = open('vMix-Manager.py', 'r', encoding='utf-8').read()

# ── 1. Add QPixmap to the PyQt6.QtGui import ──────────────────────────────────
old_import = "from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence, QIcon, QPalette"
new_import = "from PyQt6.QtGui import QFont, QColor, QAction, QTextCursor, QKeySequence, QIcon, QPalette, QPixmap"
src = src.replace(old_import, new_import, 1)

# ── 2. Add APP_ICON_B64 constant + helper after 'import ctypes' line ───────────
icon_block = (
    "\n"
    "# ── Embedded App Icon (base64 — zero external dependency) ────────────────────\n"
    "import base64 as _b64\n"
    "from PyQt6.QtCore import QByteArray\n"
    "APP_ICON_B64 = (\n"
)
# Break the b64 string into 80-char chunks for readability
chunks = [b64[i:i+80] for i in range(0, len(b64), 80)]
icon_block += "\n".join(f'    "{c}"' for c in chunks) + "\n)\n\n"
icon_block += (
    "def _get_app_icon():\n"
    "    raw = _b64.b64decode(APP_ICON_B64)\n"
    "    pm  = QPixmap()\n"
    "    pm.loadFromData(QByteArray(raw), 'ICO')\n"
    "    return QIcon(pm)\n"
    "\n"
)

if 'APP_ICON_B64' not in src:
    src = src.replace('import ctypes\n', 'import ctypes\n' + icon_block, 1)
    print("✓ Embedded icon block inserted")
else:
    print("! Icon block already present — skipping insertion")

# ── 3. Fix MainWindow.__init__ — replace old file-based icon loading ───────────
old_win = (
    '        icon_path = os.path.join(os.path.abspath("."), "app_icon.ico")\n'
    '        if os.path.exists(icon_path):\n'
    '            self.setWindowIcon(QIcon(icon_path))\n'
    '        if platform.system() == "Windows":\n'
    '            try:\n'
    '                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(\n'
    '                    f"mycompany.vmixmanager.{APP_VERSION}"\n'
    '                )\n'
    '            except Exception:\n'
    '                pass'
)
new_win = (
    '        # AppUserModelID must be set BEFORE showing window for taskbar icon\n'
    '        if platform.system() == "Windows":\n'
    '            try:\n'
    '                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(\n'
    '                    f"sevaapp.vmixmanager.{APP_VERSION}"\n'
    '                )\n'
    '            except Exception:\n'
    '                pass\n'
    '        # Load icon from embedded base64 — no external file needed\n'
    '        self.setWindowIcon(_get_app_icon())'
)
if old_win in src:
    src = src.replace(old_win, new_win, 1)
    print("✓ MainWindow icon loading fixed")
else:
    print("! Could not find old icon block in MainWindow — check manually")

# ── 4. Fix entry point — set icon on QApplication for taskbar ─────────────────
old_entry = '    w = MainWindow()\n    w.show()'
new_entry = (
    '    # Set app-level icon — required for taskbar icon on Windows\n'
    '    app.setWindowIcon(_get_app_icon())\n'
    '    w = MainWindow()\n'
    '    w.show()'
)
if old_entry in src:
    src = src.replace(old_entry, new_entry, 1)
    print("✓ Entry point app.setWindowIcon fixed")
else:
    print("! Could not find entry point block — check manually")

open('vMix-Manager.py', 'w', encoding='utf-8').write(src)
print("\n✅ All done! Rebuild the EXE with: pyinstaller vMix-Manager.spec")
