# SQL ↔ CSV Converter (portable build)

A self-contained copy of the SQL ↔ CSV Converter. Copy this folder anywhere,
make sure Python 3 is installed, and run:

    ./run.sh

On first run it creates a `.venv/` inside this folder, installs PyQt6, and
launches the GUI. The headless commands below need only Python 3 (no display,
no PyQt6).

## Commands

| Command | What it does | Needs PyQt6? |
|---------|--------------|:------------:|
| `./run.sh` (or `./run.sh gui`) | Launch the desktop app | yes (auto-installed) |
| `./run.sh install` | Create the venv + install dependencies, then exit | yes |
| `./run.sh tables DB` | List the user tables in a database | no |
| `./run.sh db2csv DB --table T [-o out.csv]` | Export one table to CSV | no |
| `./run.sh csv2db FILE.csv [--table T] [-o new.db]` | Build a database from a CSV | no |

### Examples

```bash
./run.sh tables sales.db
./run.sh db2csv sales.db --table customers
./run.sh csv2db data.csv --table orders -o orders.db
```

## GUI controls

| Button | Action |
|--------|--------|
| 📂 Open SQL Database | Open a `.db`, `.sqlite`, or `.sqlite3` file |
| 📥 Import CSV | Load a CSV into the grid (no database required) |
| 📤 Export to CSV | Save the current grid data as a CSV file |
| 📤 Import CSV to DB | Insert grid data into a table in an open database |
| 📦 Build DB from CSV | Create a new SQLite database from a CSV file |
| 👁️ Preview CSV | Preview the CSV-formatted data before saving |
| 🗑️ Clear State | Close the database, clear the grid and table list |

## Features

- Open / browse / view SQLite databases; import & export CSV
- Automatic type inference (INTEGER / REAL / TEXT)
- Robust CSV handling (BOM, ragged rows, duplicate/empty headers)
- Headless CLI for scripting

## Requirements

- Python 3.8+ (headless commands work with any modern Python 3)
- PyQt6 — GUI only; `run.sh` installs it automatically into `.venv/`

## Project structure

```
dist/
├── run.sh              # launcher — the way to run it
├── sqlcsv.py           # application (GUI + headless CLI)
├── requirements.txt    # dependencies (PyQt6)
├── README.md
└── LICENSE
```

## License

This project is open source and available under the MIT License.
