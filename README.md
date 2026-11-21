# SQL ↔ CSV Converter

A small tool for moving data between **SQLite databases** and **CSV files**.
Run it with a single bash command — no manual setup required.

## Setup
Clone Repo
```bash
git clone https://github.com/ensur3d/SQLlite-CSV.git
```
Navigate to dir after cloning
```bash
cd SQLlite-CSV.git
```
Make sure the script is executable
```bash
chmod +x run.sh
```
## Quick start

```bash
./run.sh
```

That's it. On the first run `run.sh` creates a virtual environment in `.venv/`,
installs the one dependency (PyQt6), and launches the desktop app. Later runs
skip the install step and start immediately.

## What it does

- **Open SQLite databases** — load `.db`, `.sqlite`, and `.sqlite3` files (with validation)
- **Browse tables** — pick a table from the sidebar
- **View table data** — interactive, sortable grid
- **Import CSV** — load a CSV into the grid (no database required)
- **Export to CSV** — save the current view as CSV
- **Import CSV into an existing database** — insert grid data into a table of an open database
- **Build a database from CSV** — create a brand-new SQLite database from a CSV file
- **Preview CSV** — see the exact CSV that will be exported, before saving
- **Automatic type inference** — numeric columns become `INTEGER`/`REAL`, everything else `TEXT`
- **Robust CSV handling** — strips UTF-8 BOM, pads/truncates ragged rows, de-duplicates empty or repeated headers
- **Headless CLI** — do conversions from the command line with no GUI (see below)

## Commands

Everything is driven through `run.sh`. The **GUI is the default**; the other
commands are headless and need **only Python 3** (no display, no PyQt6).

| Command | What it does | Needs PyQt6? |
|---------|--------------|:------------:|
| `./run.sh` (or `./run.sh gui`) | Launch the desktop app | yes (auto-installed) |
| `./run.sh install` | Create the venv + install dependencies, then exit | yes |
| `./run.sh tables DB` | List the user tables in a database | no |
| `./run.sh db2csv DB --table T [-o out.csv]` | Export one table to CSV | no |
| `./run.sh csv2db FILE.csv [--table T] [-o new.db]` | Build a database from a CSV | no |

### Examples

```bash
# List tables in a database
./run.sh tables sales.db

# Export the "customers" table to customers.csv
./run.sh db2csv sales.db --table customers

# Same, with an explicit output path
./run.sh db2csv sales.db -t customers -o out/customers.csv

# Build a new database from a CSV (table defaults to "imported_data")
./run.sh csv2db data.csv

# ...or choose the table name and output file
./run.sh csv2db data.csv --table orders -o orders.db
```

### GUI controls

| Button | Action |
|--------|--------|
| 📂 Open SQL Database | Open a `.db`, `.sqlite`, or `.sqlite3` file |
| 📥 Import CSV | Load a CSV file into the grid (no database required) |
| 📤 Export to CSV | Save the current grid data as a CSV file |
| 📤 Import CSV to DB | Insert grid data into a table in the currently open database |
| 📦 Build DB from CSV | Create a new SQLite database from a CSV file |
| 👁️ Preview CSV | Preview the CSV-formatted data in a dialog |
| 🗑️ Clear State | Close the database, clear the grid and table list |

**Workflow examples**

- **Database → CSV:** Open a database → select a table → *Export to CSV*
- **CSV → new database (GUI):** *Build DB from CSV* → pick CSV → choose save location → enter table name
- **CSV → existing database (GUI):** *Import CSV* → *Import CSV to DB* → enter table name
- **Browse data:** Open a database → click tables in the sidebar → view data in the grid

## Requirements

- **Python 3.8+** (the headless commands work with any modern Python 3)
- **PyQt6** — required only for the GUI; `run.sh` installs it automatically into `.venv/`
- `run.sh` auto-detects your operating system (macOS, Windows/WSL, and common Linux distros) and prints the exact command to run if Python 3, the venv module, or a dependency is missing.

You do not need to install anything by hand. If you prefer to, you can create
the environment yourself:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Prerequisites: Install Python 3 (if missing)

Usually you don't need to do this — if Python 3 is missing, `./run.sh` detects
your OS and prints the exact install command for you. The commands below are for
reference. Check whether Python is already installed with `python3 --version`.

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
**macOS (Homebrew)**
```bash
brew install python
```
**Windows**
Download the installer from https://www.python.org/downloads/ (tick "Add to PATH"), or use WSL.

### Troubleshooting

`run.sh` prints an OS-specific hint when it hits a problem:

| Message | What it means / how to fix |
|---------|----------------------------|
| `python3 not found` | Install Python 3 — the script shows your OS's command. |
| `could not create a virtual environment` | The `venv` module is missing; install it (e.g. `sudo apt install python3-venv`). |
| `failed to install dependencies` | Check your internet connection and re-run, or run `<venv>/bin/python -m ensurepip --upgrade`. |

## Project structure

```
SQLlite-CSV/
├── run.sh              # The launcher — the way to run the project
├── sqlcsv.py           # Final application (GUI + headless CLI)
├── SQLlite-CSV.py      # Original version, kept for reference (superseded by sqlcsv.py)
├── requirements.txt    # Python dependencies (PyQt6)
├── README.md
└── LICENSE
```

## License

This project is open source and available under the MIT License.
