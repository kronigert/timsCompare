# timsCompare

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Latest Release](https://img.shields.io/github/v/release/kronigert/timsCompare?label=latest%20release)](https://github.com/kronigert/timsCompare/releases)

A desktop application for mass spectrometry users to load, view, compare, and export  methods from Bruker's .d or .m method directories.

<img width="1918" height="1028" alt="Method_Comparison" src="https://github.com/user-attachments/assets/6e0a8091-bf04-4a2f-a876-1d1b1a8ef655" />

---

## About The Project

**timsCompare** is a desktop application developed for mass spectrometry users to efficiently analyze instrument method files. Built with Python and customtkinter, it provides an intuitive graphical interface to parse, visualize, and compare metadata from Bruker's `.d` and `.m` method directories.

The application can handle various acquisition modes, including PASEF, dia-PASEF, diagonal-PASEF, and more.

### Key Features

* **Side-by-Side Comparison:** Load multiple methods and compare their parameters in a clear, tabular format that highlights differences.
* **View Management:** Temporarily add extra parameters with the "Add Parameters" dialog, or instantly revert to your customized layout with the "Reset View" button.
* **Session Management:** Save your current workspace (loaded files, active segments, and view settings) into a portable `.tcs` snapshot file. Open projects later without needing access to the original raw data folders.
* **Unified Reporting:** Generate documentation using the Report Wizard:
    * **Method Reports:** Detailed one-file-per-page PDF/CSV reports.
    * **Comparison Reports:** Side-by-side comparison matrix (PDF/CSV) of all selected files.
* **Multi-Segment Analysis:** Automatically parses and displays methods with multiple segments. Includes a "Compare Segments" mode to view all segments of a single file side-by-side.
* **Graphical Visualization:** Generates plots of isolation schemes for PASEF, dia-PASEF, and diagonal-PASEF methods.
* **Data Export:** Export scan window tables (e.g., dia-PASEF windows, diagonal-PASEF, PASEF polygons) to text files for import into timsControl.
* **Customizable Default View:** Configure preferred default parameters for each acquisition mode via the "Manage Views" window.

---

## Getting Started

The recommended way to use timsCompare is to download the pre-compiled installer via the release page.

### Installation

1.  **Download:** Go to the [**Releases Page**](https://github.com/kronigert/timsCompare/releases) and download the `timsCompare_Setup_vX.X.zip` file from the latest release.
2.  **Extract:** Unzip the downloaded file and run the installer.
3.  **Run:** Open timsCompare from the start menu or a shortcut to start the application.

---

## How to Use

### Loading Data

* **Drag and Drop:** Drag one or more `.d` / `.m` folders **or** a saved `.tcs` session file directly onto the application window.
* **Load Files Button:** Use the "Load Files" dropdown in the top toolbar to select data folders or open a saved session.

The parameter values of the loaded datasets are compared, and differences are highlighted in bold text.

### Adding Parameters

After loading your data, you can add more parameters to the comparison table:

1.  Click the **Add Parameters** button in the top toolbar.
2.  In the new window, search or scroll to find the parameters you wish to add.
3.  Select the desired parameters using the checkboxes.
4.  Click **Apply** to add them to the main view.

<img width="1202" height="732" alt="Parameters" src="https://github.com/user-attachments/assets/5416521b-e424-43f5-831e-84d40c373be3" />

### Session Management

timsCompare allows you to save your current work as a "Snapshot":

1.  Load your data and configure your view (add parameters, select segments).
2.  Click the **Save Session** button.
3.  This creates a `.tcs` file which embeds all necessary metadata and scan geometry.
4.  You can send this file to colleagues or open it later to resume analysis, even if you no longer have access to the original raw data drives.

### Generating Reports

The **Report Wizard** handles both batch documentation and comparison overviews.

1.  Load your datasets.
2.  Click the **Export** button and select **Report Wizard**.
3.  **Select Datasets:** Choose which loaded files to include.
4.  **Select Parameters:** The current view is selected by default, but you can customize it here.
5.  **Output Settings:**
    * **Report Type:** Choose between **Method Report** (individual file details) or **Comparison Report** (side-by-side comparison table).
    * **Format:** PDF or CSV.
    * **Options:** Toggle Plots, Filename Headers, or export All Segments vs. Active Segment.

### Exporting Scan Windows

This feature is available for PASEF, dia-PASEF, and diagonal-PASEF methods and allows you to save the scan window definitions to a text file.

1.  Load the dataset containing the scan windows you wish to export.
2.  In the bottom-left corner of the window, select the correct dataset from the **File** dropdown menu.
3.  Click the **Export** button and select **Windows** from the menu.
4.  A save dialog will open, allowing you to choose a location and name for the exported `.txt` file.
5. Exported diagonal-PASEF and dia-PASEF windows can directly be imported into timsControl. For PASEF methods, the polygon has to be created manually in timsControl using the x,y coordinates from the exported .txt

### Customizing the Default View

You can change the default set of parameters that are loaded for each scan mode:

1.  Click the **Manage Views** button in the top toolbar.
2.  In the new window, select the **Scan Mode** (e.g., "General", "dia-PASEF") you wish to edit.
3.  Use the **Group** and **Search** filters to find parameters in the "Available Parameters" list.
4.  Use the `>` and `<` buttons (or double-click) to move parameters to the "Default View Parameters" list.
5.  Reorder the parameters in the right-hand list using **drag-and-drop** or the **Up/Down** buttons.
6.  Click **Save Changes**. The application will now use this new layout as the default for that scan mode (a restart may be required).

---
## Disclaimer

timsCompare is an independent, third-party tool and is not an official Bruker product, nor is it affiliated with or supported by Bruker. If you encounter bugs or wrong values being displayed, please let me know via the [**Issues** section](https://github.com/kronigert/timsCompare/issues).

## License

Distributed under the MIT License. See `LICENSE` for more information.
