# SQL ↔ CSV Converter

A PyQt6 desktop application for importing SQLite databases, viewing table data, and converting between SQL and CSV formats.

## Features

- **Open SQLite databases** — Load `.db`, `.sqlite`, and `.sqlite3` files
- **Browse tables** — Select tables from the database in a sidebar
- **View table data** — Display table contents in an interactive, sortable grid
- **Import CSV** — Load CSV files into the grid viewer
- **Export to CSV** — Save the current table view as a CSV file
- **Import CSV into existing database** — Insert grid data into a table within an already-open database
- **Build database from CSV** — Create a brand new SQLite database directly from a CSV file
- **Preview CSV** — View the CSV representation of the current data before exporting
- **Threaded operations** — Database queries run in background threads to keep the UI responsive

## Requirements

- Python 3.8+
- PyQt6 (install via pip)

## Prerequisites: Install Python3

Python is usually pre-installed. Open your terminal and type `python3 --version`.
**Debian/Ubuntu**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```
**Fedora/RHEL**
```bash
sudo dnf install python3 python3-pip python3-virtualenv
```
**Arch Linux**
```bash
sudo pacman -S python python-pip python-virtualenv
```


## Installation

Clone or navigate to the project directory
```bash
cd SQLlite_CSV
```
Create a virtual environment (recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies
```bash
pip install -r requirements.txt
```

## Usage

```bash
cd SQLlite_CSV
source .venv/bin/activate    # if using a virtual environment
python3 SQLlite_CSV.py
```

### Controls

| Button | Action |
|--------|--------|
| 📂 Open SQL Database | Open a `.db`, `.sqlite`, or `.sqlite3` file |
| 📥 Import CSV | Load a CSV file into the grid (no database required) |
| 📤 Export to CSV | Save the current grid data as a CSV file |
| 📤 Import CSV to DB | Insert grid data into a table in the currently open database |
| 📦 Build DB from CSV | Create a new SQLite database from a CSV file |
| 👁️ Preview CSV | Preview the CSV-formatted data in a dialog |
| 🗑️ Clear State | Close the database, clear grid and table list |

### Workflow examples

**Database → CSV:** Open a database → select a table → Export to CSV

**CSV → Database (new):** Build DB from CSV → select CSV → choose save location → enter table name

**CSV → Database (existing):** Import CSV → Import CSV to DB → enter table name

**Browse data:** Open a database → click tables in the sidebar → view data in the grid

## Project structure

```
SQLlite_CSV/
├── SQLlite_CSV.py           # Main application
├── requirements.txt     # Python dependencies
└── README.md
```

## License

MIT
