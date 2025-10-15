# timsCompare

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Latest Release](https://img.shields.io/github/v/release/kronigert/timsCompare?label=latest%20release)](https://github.com/kronigert/timsCompare/releases)

A desktop application for mass spectrometry users to load, view, compare, and export  methods from Bruker's .d or .m method directories.

<img width="1920" height="1032" alt="Method_Comparison" src="https://github.com/user-attachments/assets/f34704e9-850a-4619-9179-c17e8eadc1e9" />

---

## About The Project

**timsCompare** is a desktop application developed for mass spectrometry users to efficiently analyze instrument method files. Built with Python and customtkinter, it provides an intuitive graphical interface to parse, visualize, and compare metadata from Bruker's `.d` and `.m` method directories.

The application can handle various acquisition modes, including PASEF, dia-PASEF, diagonal-PASEF, and more.

### Key Features

* **Side-by-Side Comparison:** Load multiple methods and compare their parameters in a clear, tabular format that highlights differences.
* **Multi-Segment Analysis:** Automatically parses and displays methods with multiple segments.
* **Graphical Visualization:** Generates plots of isolation schemes for PASEF, dia-PASEF, and diagonal-PASEF methods.
* **Method Reports:** Export detailed, multi-page PDF or CSV reports with a clean two-column layout for documentation or publications.
* **Data Export:** Export scan window tables (e.g., dia-PASEF windows, diagonal-PASEF, PASEF polygons) to text files. Exported dia-PASEF and diagonal-PASEF windows can be directly imported into timsControl.

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

* **Drag and Drop:** Simply drag one or more `.d` or `.m` folders from your file explorer directly onto the application window.
* **Add Data Button:** Use the "Add Data" button to open a dialog and select the folders you wish to visualize.

The parameter values of the loaded datasets are being compared and differences are highlighted in bold text.

### Adding Parameters

After loading your data, you can add more parameters to the comparison table:

1.  Click the **Add Parameters** button in the top toolbar.
2.  In the new window, search or scroll to find the parameters you wish to add.
3.  Select the desired parameters using the checkboxes.
4.  Click **Apply** to add them to the main view.

<img width="1202" height="732" alt="Parameters" src="https://github.com/user-attachments/assets/5416521b-e424-43f5-831e-84d40c373be3" />

### Generating Reports

1.  Load a dataset.
2.  Select the desired file from the dropdown menu at the bottom of the window.
3.  Click the "Export" button and choose "Method Report...".
4.  In the report dialog, customize the parameters and segments you wish to include.
5.  Choose your export format (PDF or CSV) and click "Generate Report".

<img width="666" height="938" alt="Method_Report" src="https://github.com/user-attachments/assets/83fb7067-5700-4294-ac1e-0f6aafdfc288" />

### Exporting Scan Windows

This feature is available for PASEF, dia-PASEF, and diagonal-PASEF methods and allows you to save the scan window definitions to a text file.

1.  Load the dataset containing the scan windows you wish to export.
2.  In the bottom-left corner of the window, select the correct dataset from the **File** dropdown menu.
3.  Click the **Export** button and select **Windows** from the menu.
4.  A save dialog will open, allowing you to choose a location and name for the exported `.txt` file.
5. Exported diagonal-PASEF and dia-PASEF windows can directly be imported into timsControl. For PASEF methods, the polygon has to be created manually in timsControl using the x,y coordinates from the exported .txt

---
## Disclaimer

timsCompare is an independent, third-party tool and is not an official Bruker product, nor is it affiliated with or supported by Bruker. If you encounter bugs or wrong values being displayed, please let me know via the [**Issues** section](https://github.com/kronigert/timsCompare/issues).

## License

Distributed under the MIT License. See `LICENSE` for more information.
