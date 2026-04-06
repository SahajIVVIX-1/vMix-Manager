# 📺 vMix Manager
### Direct XML Production Engine & Batch Automation Suite

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-black.svg?style=for-the-badge&logo=python)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-black.svg?style=for-the-badge&logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)
[![vMix Compatibility](https://img.shields.io/badge/vMix-24+-orange.svg?style=for-the-badge)](https://www.vmix.com/)

**vMix Manager** is a specialized production utility designed for engineers who manage large-scale vMix sessions. Unlike the standard vMix interface, which requires manual input-by-input adjustments, vMix Manager operates directly on the `.vmix` XML schema. This allows for near-instantaneous batch operations, category migrations, and asset relinking that are impossible within the native vMix GUI.

---

## 💎 Design Philosophy
vMix Manager features a **Professional High-Contrast interface** utilizing the **Cambria typography** stack. The UI is designed for high-stress production environments, focusing on readability, minimal distraction (Pure Black & White), and robust activity logging.

---

## 🧠 Core Engine Modules

### 1. Direct XML Manipulation Engine
The software does not "control" vMix via API; instead, it parses the underlying XML structure of a `.vmix` file.
*   **Offline Editing:** Modify production files without having vMix open or consuming CPU/GPU resources.
*   **GUID Integrity:** Every cloned or imported input is assigned a fresh **UUID**, preventing "Key Collision" errors when vMix loads the file.
*   **Attribute Preservation:** All metadata including Volume, Mute states, Loop settings, and Position coordinates are preserved during category swaps.

### 2. Smart Folder Inhalation (Batch Import)
Designed for shows with hundreds of playback assets.
*   **Multi-Queueing:** Add dozens of folders to a staging list. 
*   **Automated Header Injection:** For every folder imported, the engine automatically creates a **GT Title Divider**.
*   **XML Payload Injection:** It injects a custom XML payload into the GT Title to force a **214px Bold Arial** font targeting the `Message.Text` field, ensuring dividers are visible on multiviewers.
*   **Template Path:** Automatically targets the native vMix path: `C:\Program Files (x86)\vMix\titles\GT Text\Text Middle Centre Left Right Sharp.gtzip`.

### 3. Category Interchanger (The "Deep Swap")
Standard vMix only allows renaming categories. vMix Manager allows you to **physically move content** between slots.
*   **Slot Mapping:** Supports the standard vMix architecture (Slots 1–6 and Custom Slots 50–65).
*   **The Swap Logic:** When swapping Category A and Category B, the engine iterates through all Input objects and rewrites their `Category` attribute while maintaining their internal `Position` order.

### 4. Category Cloning & Relinking
Import structures from existing `.vmix` files or folder trees.
*   **Status Verification:** Automatically scans paths and marks assets with ✅ (Found) or ❌ (Missing).
*   **Root Relinking:** If a project has moved to a different drive, use "Relink Root" to batch-update all file paths to a new directory while keeping the category structure intact.

---

## 🛠 Feature Deep Dive

| Feature | Description | Use Case |
| :--- | :--- | :--- |
| **Header Title Gen** | Injects GT Titles as dividers between folder batches. | Organizing a 4-hour awards show with 20 categories. |
| **Factory Export** | Copies all physical files from a category into a new folder on disk. | Consolidating assets for a backup machine or external editor. |
| **Wipe Logic** | Three tiers: Clear Category, Wipe All Inputs, or Factory Reset. | Preparing a "Daily Clean" session from a complex template. |
| **Drag-Drop Reorder** | Manually reorder inputs in a table and save the new XML sequence. | Sorting playback items without fighting the vMix GUI scroll. |
| **Activity Logging** | Real-time timestamped log of all XML operations. | Debugging missing files or tracking batch progress. |

---

## 🚀 Getting Started

### Prerequisites
*   **Windows 10/11** (Optimized for Windows Taskbar integration).
*   **Python 3.10+**
*   **vMix 24+** (Recommended for GT Title compatibility).

### Installation
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/SahajIVVIX-1/vMix-Manager.git
    cd vMix-Manager
    ```
2.  **Install Dependencies:**
    ```bash
    pip install PyQt6
    ```
3.  **Run Application:**
    ```bash
    python vMix-Manager.py
    ```

---

## 📋 Usage Guide

1.  **Open Session:** Load your `.vmix` file via `File > Open`.
2.  **Organize Categories:** Use the sidebar to rename categories. Right-click to reset slots to "Empty Cat".
3.  **Batch Import:** 
    *   Go to **Folder Import**. 
    *   Add your "Stingers," "VTs," and "Sponsors" folders. 
    *   Click "Start Bulk Import." 
    *   Each group will appear in your current category separated by high-visibility text headers.
4.  **Transform:** Use the **Transform** tab to swap your "Red" category with "Custom 10" instantly.
5.  **Save:** Save the file and open it in vMix. All inputs will appear exactly as structured.

---

## 🏗 Build as Standalone (.exe)
To create a single-file executable for production machines:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "vMixManager" --icon=app_icon.ico vMix-Manager.py
```

---

## ⚖️ Disclaimer
vMix Manager is an independent tool and is not affiliated with, authorized, or endorsed by **StudioCoast Pty Ltd (vMix)**. Always create a backup of your `.vmix` files before performing bulk XML operations.

---

<div align="center">
Developed by <b>Sahaj Saliya</b><br>
<i>Empowering vMix Operators through specialized automation.</i>
</div>
