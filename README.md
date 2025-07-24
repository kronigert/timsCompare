# timsCompare

A Python desktop application for mass spectrometry users to load, view, compare, and export professional method reports from Bruker's .d method directories.

<img width="1920" height="1032" alt="timsCompare" src="https://github.com/user-attachments/assets/18922ecd-cd2a-48dc-aff0-08947203ba78" />

---

## About The Project

**timsCompare** is a desktop application developed for mass spectrometry users to efficiently analyze instrument method files. Built with Python and customtkinter, it provides an intuitive graphical interface to parse, visualize, and compare metadata from Bruker's `.d` method directories.

The application specializes in handling various acquisition modes, including PASEF, dia-PASEF, bbCID, MRM, and more. It correctly parses multi-segment methods, allowing for detailed analysis of experiments where parameters change over time.

### Key Features

* **Side-by-Side Comparison:** Load multiple `.d` folders and compare their parameters in a clear, tabular format.
* **Multi-Segment Analysis:** Automatically parses and displays methods with multiple timed segments.
* **Graphical Visualization:** Generates plots of scan geometries for PASEF, dia-PASEF, and diagonal-PASEF methods.
* **Professional Method Reports:** Export detailed, multi-page PDF reports with a clean two-column layout, perfect for documentation or publications.
* **Data Export:** Export scan window tables (e.g., dia-PASEF windows, PASEF polygons) to CSV/TXT files.
* **Modern UI:** A clean, icon-driven user interface with light and dark modes.

---

## Getting Started

### Prerequisites

This application is built with Python 3. You will need to have Python installed on your system.

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your_username/timsCompare.git
    cd timsCompare
    ```
2.  **Install the required packages:**
    It is recommended to use a virtual environment.
    ```sh
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

    # Install dependencies
    pip install -r requirements.txt
    ```

---

## Usage

To run the application, execute the `main.py` script from the root of the project directory:

```sh
python main.py
```

### Loading Data

* **Drag and Drop:** Simply drag one or more `.d` folders from your file explorer directly onto the application window.
* **File Menu:** Use the "Add Data" button to open a file dialog and select the `.d` folders you wish to analyze.

### Generating Reports

1.  Load one or more datasets.
2.  From the "File" dropdown at the bottom of the window, select the dataset you want to generate a report for.
3.  Click the "Export" button and choose "Method Report...".
4.  In the report dialog, select the segments and parameters you wish to include.
5.  Choose your export format (PDF or CSV) and click "Generate Report".

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
