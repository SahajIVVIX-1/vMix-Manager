<div align="center">

# 📺 vMix Manager
### Advanced Batch Automation & Lifecycle Management for vMix Productions

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-7C3AED.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![vMix Compatibility](https://img.shields.io/badge/vMix-24+-orange.svg)](https://www.vmix.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**vMix Manager** is a high-performance production utility that bypasses the limitations of the vMix GUI for large-scale asset management. By performing direct XML manipulation on `.vmix` session files, it allows production engineers to handle hundreds of inputs through automated queuing, intelligent sorting, and deep category restructuring.

</div>

---

## 🚀 Key Features

### 📁 Smart Folder Grouping & Inhalation
Overhaul your workflow with a modern Folder Import system designed for massive projects:
*   **Multi-Folder Queuing:** Stage multiple directories in a staging list before committing changes to the project.
*   **Automated Header Injection:** The tool automatically generates a **GT Title Input (Type 9000)** at the top of every imported folder.
*   **High-Visibility Dividers:** Headers are pre-configured with a **200px font size** targeting the `Message.Text` field, making your groupings instantly readable on multiview monitors.
*   **Logical Sorting:** Media files are automatically sorted in **ascending alphabetical/numerical order** to maintain your desired sequence.

### 🔄 Deep Category Transformation
Move past simple name changes. The **Category Interchanger** performs a "Deep Swap":
*   **Input Migration:** It updates the internal `Category` attribute of every individual Input object, ensuring content physically moves to the new tab.
*   **23-Slot Management:** All vMix category slots (0-22) are kept visible and accessible, even when empty.
*   **Safe Swapping:** Swap entire category content without losing any vMix-specific metadata (Gain, EQ, or Positions).

### 🛠️ Production Lifecycle (Factory Reset)
A dedicated tab for bulk cleanup and project sanitization:
*   **Category Purge:** Instantly empty all inputs from the currently selected category.
*   **Global Asset Wipe:** Delete every input in the entire production file while keeping your naming structure.
*   **Full Factory Reset:** Revert the session to a clean slate with default vMix names and zero inputs.

---

## 🖥️ UI Workflow

1.  **Targeting:** Select your desired category from the left-hand sidebar.
2.  **Queueing:** Use the **Folder Import** tab to add one or multiple folders to the queue.
3.  **Import:** Click "Start Bulk Import." The script builds the GT Title XML payloads and stages your media.
4.  **Verification:** Monitor the **Activity Log**, which uses your **Custom Category Names** for clear, real-time feedback.

---

## ⚙️ Technical Specifications

*   **XML Core:** Built using `xml.etree.ElementTree` to parse and reconstruct vMix-compliant production schemas.
*   **GT Title Engine:** Injects custom `<Font>` and `<value>` tags into the Input attribute string to force font scaling and text visibility.
*   **Threading:** Implementation of `QThread` and `pyqtSignal` ensures heavy file operations (like Category Exports) never lock the UI.

---

## 📦 Installation & Setup

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

## 🛠️ Build as Executable
To package vMix Manager as a standalone Windows application:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --icon "app_icon.ico" --add-data "app_icon.ico;." vMix-Manager.py
```

<div align="center">

**Developed by [Sahaj Saliya](https://github.com/SahajIVVIX-1)**

*Disclaimer: This project is not affiliated with StudioCoast Pty Ltd. Always backup your `.vmix` files before performing bulk operations.*

</div>
