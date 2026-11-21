"""
SQL <-> CSV Converter (final build)
===================================
A small tool for moving data between SQLite databases and CSV files.

Run it with the bash launcher (recommended):

    ./run.sh                 # launch the GUI (auto-sets up venv + deps)
    ./run.sh install         # set up the environment only
    ./run.sh tables DB       # list tables in a database        (headless, no GUI)
    ./run.sh db2csv DB -t T  # export one table to CSV          (headless, no GUI)
    ./run.sh csv2db FILE.csv # build a database from a CSV      (headless, no GUI)

The core conversion logic is pure Python (no Qt), so the headless commands
work on any machine with just Python 3 -- no display or PyQt6 required.
"""

import sys
import os
import io
import csv
import sqlite3
import argparse

# ---------------------------------------------------------------------------
# Pure-Python core helpers (shared by the GUI and the headless CLI).
# None of these import Qt, so they run anywhere Python 3 runs.
# ---------------------------------------------------------------------------

SQLITE_MAGIC = b"SQLite format 3\x00"


def _qi(name):
    """Quote an SQL identifier safely (doubles embedded double-quotes)."""
    return '"' + str(name).replace('"', '""') + '"'


def sanitize_headers(headers):
    """Return cleaned, unique, non-empty column names.

    - strips surrounding whitespace
    - replaces empty names with col_1, col_2, ...
    - de-duplicates repeated names by appending _2, _3, ...
    """
    used = set()
    out = []
    for i, h in enumerate(headers):
        h = (h or "").strip() or f"col_{i + 1}"
        candidate = h
        n = 2
        while candidate.lower() in used:
            candidate = f"{h}_{n}"
            n += 1
        used.add(candidate.lower())
        out.append(candidate)
    return out


def normalize_rows(rows, n_cols):
    """Pad short rows with '' and truncate long rows to exactly n_cols."""
    norm = []
    for r in rows:
        if len(r) < n_cols:
            r = list(r) + [""] * (n_cols - len(r))
        elif len(r) > n_cols:
            r = r[:n_cols]
        norm.append(list(r))
    return norm


def infer_sqlite_type(values):
    """Infer a SQLite column type from a list of string values.

    Conservative: INTEGER if every non-empty value is an int, REAL if every
    non-empty value is numeric, otherwise TEXT. Empty-only columns -> TEXT.
    """
    ints = 0
    floats = 0
    for v in values:
        if v == "":
            continue
        try:
            int(v)
            ints += 1
            continue
        except (ValueError, TypeError):
            pass
        try:
            float(v)
            floats += 1
            continue
        except (ValueError, TypeError):
            return "TEXT"
    nonempty = ints + floats
    if nonempty == 0:
        return "TEXT"
    if ints == nonempty:
        return "INTEGER"
    return "REAL"


def column_types_for(headers, rows):
    """Return a list of inferred SQLite types, one per column."""
    n = len(headers)
    types = []
    for c in range(n):
        col_values = [row[c] if c < len(row) else "" for row in rows]
        types.append(infer_sqlite_type(col_values))
    return types


def read_csv_file(path):
    """Read a CSV file. Returns (headers, rows). BOM-safe. Raises on empty."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        data = list(csv.reader(f))
    if not data:
        raise ValueError(f"CSV file is empty: {path}")
    headers = data[0]
    rows = data[1:]
    return headers, rows


def build_csv_text(headers, rows):
    """Render headers+rows as a CSV string (QUOTE_MINIMAL).

    Single source of truth for both the GUI preview and export so they always
    produce identical output.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def is_sqlite_file(path):
    """True if path exists and starts with the SQLite header magic bytes."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            return f.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def create_table_from_csv(cursor, table_name, headers, rows, types=None, batch_size=500):
    """Create `table_name` and insert rows. Returns the number of rows inserted.

    headers/rows must already be sanitized and normalized (same width).
    """
    if types is None:
        types = column_types_for(headers, rows)
    cols_def = ", ".join(f"{_qi(h)} {t}" for h, t in zip(headers, types))
    cursor.execute(f"CREATE TABLE {_qi(table_name)} ({cols_def})")
    placeholders = ", ".join(["?"] * len(headers))
    insert_sql = f"INSERT INTO {_qi(table_name)} VALUES ({placeholders})"
    total = 0
    for i in range(0, len(rows), batch_size):
        cursor.executemany(insert_sql, rows[i:i + batch_size])
        total += len(rows[i:i + batch_size])
    return total


# ---------------------------------------------------------------------------
# Headless CLI commands (no Qt). Each returns an int exit code.
# ---------------------------------------------------------------------------

def cmd_tables(args):
    if not is_sqlite_file(args.db):
        print(f"error: '{args.db}' is not a valid SQLite database.", file=sys.stderr)
        return 1
    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    if not tables:
        print("(no user tables)")
    else:
        for t in tables:
            print(t)
    return 0


def cmd_db2csv(args):
    if not is_sqlite_file(args.db):
        print(f"error: '{args.db}' is not a valid SQLite database.", file=sys.stderr)
        return 1
    output = args.output or f"{args.table}.csv"
    conn = sqlite3.connect(args.db)
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT * FROM {_qi(args.table)}')
        headers = [d[0] for d in cur.description]
        rows = [[str(v) if v is not None else "" for v in row] for row in cur.fetchall()]
    except sqlite3.Error as e:
        print(f"error: could not read table '{args.table}': {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    with open(output, "w", encoding="utf-8", newline="") as f:
        f.write(build_csv_text(headers, rows))
    print(f"Wrote {len(rows)} rows x {len(headers)} cols to {output}")
    return 0


def cmd_csv2db(args):
    try:
        raw_headers, raw_rows = read_csv_file(args.csv)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    headers = sanitize_headers(raw_headers)
    rows = normalize_rows(raw_rows, len(headers))
    types = column_types_for(headers, rows)
    output = args.output or os.path.splitext(args.csv)[0] + ".db"

    conn = sqlite3.connect(output)
    try:
        cur = conn.cursor()
        # Replace the table if it already exists so re-runs are idempotent.
        cur.execute(f"DROP TABLE IF EXISTS {_qi(args.table)}")
        n = create_table_from_csv(cur, args.table, headers, rows, types)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Built {output} | table '{args.table}' | {n} rows")
    print("Columns: " + ", ".join(f"{h}:{t}" for h, t in zip(headers, types)))
    return 0


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="sqlcsv",
        description="Convert between SQLite databases and CSV files.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="Launch the graphical interface (default)")

    p_tables = sub.add_parser("tables", help="List tables in a SQLite database")
    p_tables.add_argument("db", help="path to the .db/.sqlite/.sqlite3 file")

    p_db2csv = sub.add_parser("db2csv", help="Export one table from a DB to CSV (headless)")
    p_db2csv.add_argument("db", help="path to the SQLite database")
    p_db2csv.add_argument("-t", "--table", required=True, help="table name to export")
    p_db2csv.add_argument("-o", "--output", default=None,
                          help="output CSV path (default: <table>.csv)")

    p_csv2db = sub.add_parser("csv2db", help="Build a SQLite DB from a CSV file (headless)")
    p_csv2db.add_argument("csv", help="path to the input .csv file")
    p_csv2db.add_argument("-t", "--table", default="imported_data",
                          help="table name (default: imported_data)")
    p_csv2db.add_argument("-o", "--output", default=None,
                          help="output .db path (default: <csv>.db)")

    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    command = args.command
    if command in (None, "gui"):
        return run_gui()
    if command == "tables":
        return cmd_tables(args)
    if command == "db2csv":
        return cmd_db2csv(args)
    if command == "csv2db":
        return cmd_csv2db(args)

    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# GUI (imports PyQt6 lazily so headless commands never need it)
# ---------------------------------------------------------------------------

def run_gui():
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QTableView, QFileDialog, QMessageBox,
        QDialog, QTextEdit, QPushButton, QLabel, QSplitter, QAbstractItemView,
        QInputDialog,
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont

    class DBWorker(QThread):
        # NB: named finished_data (not `finished`) to avoid shadowing the
        # built-in QThread.finished signal.
        progress = pyqtSignal(int, str)
        finished_data = pyqtSignal(int, list, list)  # (generation, headers, rows)
        error = pyqtSignal(str)

        def __init__(self, db_path, table_name, gen):
            super().__init__()
            self.db_path = db_path
            self.table_name = table_name
            self.gen = gen

        def run(self):
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                self.progress.emit(20, "Fetching table...")
                cursor.execute(f"SELECT * FROM {_qi(self.table_name)}")
                headers = [d[0] for d in cursor.description]
                rows = [[str(v) if v is not None else "" for v in row]
                        for row in cursor.fetchall()]
                self.progress.emit(100, "Data ready!")
                self.finished_data.emit(self.gen, headers, rows)
            except Exception as e:  # noqa: BLE001 - surface any DB error to the UI
                self.error.emit(str(e))
            finally:
                if conn:
                    conn.close()

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SQL <-> CSV Converter")
            self.resize(1100, 700)
            self.setCentralWidget(QWidget())

            self.db_conn = None
            self.db_path = None
            self.current_model = None
            self.csv_buffer = None      # {'headers': [...], 'rows': [[...]]}
            self._load_gen = 0          # guards against stale worker results
            self.worker = None

            self.setup_ui()

        def setup_ui(self):
            central = self.centralWidget()
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(8, 8, 8, 8)
            main_layout.setSpacing(6)

            ctrl_layout = QHBoxLayout()
            self.btn_open_db = QPushButton("📂 Open SQL Database")
            self.btn_import_csv = QPushButton("📥 Import CSV")
            self.btn_export_csv = QPushButton("📤 Export to CSV")
            self.btn_import_csv_to_db = QPushButton("📤 Import CSV to DB")
            self.btn_build_db = QPushButton("📦 Build DB from CSV")
            self.btn_preview_csv = QPushButton("👁️ Preview CSV")
            self.btn_clear = QPushButton("🗑️ Clear State")

            for btn in (self.btn_open_db, self.btn_import_csv, self.btn_export_csv,
                        self.btn_import_csv_to_db, self.btn_build_db,
                        self.btn_preview_csv, self.btn_clear):
                ctrl_layout.addWidget(btn)
            main_layout.addLayout(ctrl_layout)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            self.table_list = QListWidget()
            self.table_list.setMinimumWidth(180)
            self.table_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            splitter.addWidget(self.table_list)

            self.table_view = QTableView()
            self.table_view.setAlternatingRowColors(True)
            self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table_view.setWordWrap(False)
            splitter.addWidget(self.table_view)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 3)
            main_layout.addWidget(splitter)

            self.statusBar().showMessage("Ready | Current: None")
            self.statusBar().setFont(QFont("Segoe UI", 10))

            self.btn_open_db.clicked.connect(self.open_sql_db)
            self.btn_import_csv.clicked.connect(self.import_csv)
            self.btn_export_csv.clicked.connect(self.export_csv)
            self.btn_import_csv_to_db.clicked.connect(self.import_csv_to_database)
            self.btn_build_db.clicked.connect(self.build_db_from_csv)
            self.btn_preview_csv.clicked.connect(self.preview_csv)
            self.btn_clear.clicked.connect(self.clear_state)
            self.table_list.currentRowChanged.connect(self.load_table_data)

        # -- database -------------------------------------------------------
        def open_sql_db(self):
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open SQL Database", "",
                "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)")
            if not file_path:
                return
            if not is_sqlite_file(file_path):
                QMessageBox.critical(self, "Database Error",
                                     f"File is not a valid SQLite database:\n{file_path}")
                return
            try:
                self.db_conn = sqlite3.connect(file_path)
                self.db_path = file_path
                self.statusBar().showMessage(f"Connected: {file_path}")
                self.update_table_list()
            except Exception as e:  # noqa: BLE001
                if self.db_conn:
                    self.db_conn.close()
                self.db_conn = None
                self.db_path = None
                QMessageBox.critical(self, "Database Error", f"Failed to open database:\n{e}")

        def update_table_list(self):
            if not self.db_conn:
                return
            self.table_list.clear()
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master "
                           "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            self.table_list.addItems([row[0] for row in cursor.fetchall()])

        def load_table_data(self, row):
            if row < 0 or not self.db_conn:
                return
            table_name = self.table_list.item(row).text()
            self.statusBar().showMessage(f"Loading {table_name}...")
            QApplication.processEvents()

            # Bump the generation so any in-flight worker result is dropped.
            self._load_gen += 1
            gen = self._load_gen
            self.worker = DBWorker(self.db_path, table_name, gen)
            self.worker.progress.connect(self.update_progress)
            self.worker.finished_data.connect(self.display_data)
            self.worker.error.connect(lambda e: QMessageBox.critical(self, "DB Error", e))
            self.worker.start()

        def update_progress(self, pct, msg):
            self.statusBar().showMessage(f"{msg} ({pct}%)")

        def display_data(self, gen, headers, rows):
            # Ignore stale results from a previous table load.
            if gen != self._load_gen:
                return
            self._populate_grid(headers, rows)
            self.statusBar().showMessage(f"Loaded: {len(rows)} rows | {len(headers)} cols")

        def _populate_grid(self, headers, rows):
            """Fill the grid and csv_buffer directly (no worker). Also invalidates
            any in-flight table-load worker so it cannot overwrite this data."""
            self._load_gen += 1
            model = QStandardItemModel(len(rows), len(headers))
            model.setHorizontalHeaderLabels(headers)
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    model.setItem(r_idx, c_idx, QStandardItem(str(val)))
            self.table_view.setModel(model)
            self.table_view.resizeColumnsToContents()
            self.current_model = model
            self.csv_buffer = {'headers': headers, 'rows': rows}

        # -- CSV ------------------------------------------------------------
        def import_csv(self):
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Import CSV", "", "CSV Files (*.csv)")
            if not file_path:
                return
            try:
                raw_headers, raw_rows = read_csv_file(file_path)
            except (OSError, ValueError) as e:  # noqa: BLE001
                QMessageBox.critical(self, "Error", f"Failed to import CSV:\n{e}")
                return
            headers = sanitize_headers(raw_headers)
            rows = normalize_rows(raw_rows, len(headers))
            self._populate_grid(headers, rows)
            self.statusBar().showMessage(f"Imported CSV: {len(rows)} rows | {len(headers)} cols")

        def export_csv(self):
            if not self.csv_buffer:
                QMessageBox.warning(self, "Warning", "No data selected to export.")
                return
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export to CSV", "", "CSV Files (*.csv)")
            if not file_path:
                return
            if not file_path.endswith(".csv"):
                file_path += ".csv"
            try:
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(build_csv_text(self.csv_buffer['headers'], self.csv_buffer['rows']))
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{e}")
                return
            QMessageBox.information(self, "Success", f"Exported to:\n{file_path}")

        def preview_csv(self):
            if not self.csv_buffer:
                QMessageBox.warning(self, "Warning", "No data to preview.")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("CSV Preview")
            dialog.resize(750, 450)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Generated CSV Content:"))
            editor = QTextEdit()
            editor.setReadOnly(True)
            layout.addWidget(editor)
            editor.setPlainText(build_csv_text(self.csv_buffer['headers'], self.csv_buffer['rows']))
            dialog.exec()

        # -- write to a database -------------------------------------------
        def import_csv_to_database(self):
            if not self.csv_buffer:
                QMessageBox.warning(self, "Warning", "No data available to import to database.")
                return
            if not self.db_conn:
                QMessageBox.warning(self, "Warning", "Please open a database first.")
                return

            table_name, ok = QInputDialog.getText(
                self, "Import to Database", "Enter table name:")
            if not ok or not table_name.strip():
                return
            table_name = table_name.strip()

            headers = self.csv_buffer['headers']
            rows = normalize_rows(self.csv_buffer['rows'], len(headers))
            types = column_types_for(headers, rows)

            cursor = self.db_conn.cursor()
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                               (table_name,))
                if cursor.fetchone():
                    reply = QMessageBox.question(
                        self, "Table Exists",
                        f"Table '{table_name}' already exists. Replace it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if reply != QMessageBox.StandardButton.Yes:
                        return

                n = create_table_from_csv(cursor, table_name, headers, rows, types)
                self.db_conn.commit()
            except Exception as e:  # noqa: BLE001
                self.db_conn.rollback()
                QMessageBox.critical(self, "Database Error",
                                     f"Failed to import CSV to database:\n{e}")
                return

            self.update_table_list()
            QMessageBox.information(self, "Success",
                                    f"Imported {n} rows to table '{table_name}'")
            self.statusBar().showMessage(f"Imported {n} rows to table '{table_name}'")

        def build_db_from_csv(self):
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select CSV File", "", "CSV Files (*.csv)")
            if not file_path:
                return
            try:
                raw_headers, raw_rows = read_csv_file(file_path)
            except (OSError, ValueError) as e:  # noqa: BLE001
                QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{e}")
                return

            db_path, _ = QFileDialog.getSaveFileName(
                self, "Save New Database As", "", "SQLite Files (*.db);;All Files (*)")
            if not db_path:
                return
            if not db_path.endswith(".db"):
                db_path += ".db"

            table_name, ok = QInputDialog.getText(
                self, "Table Name", "Enter a name for the table:", text="imported_data")
            if not ok or not table_name.strip():
                return
            table_name = table_name.strip()

            headers = sanitize_headers(raw_headers)
            rows = normalize_rows(raw_rows, len(headers))
            types = column_types_for(headers, rows)

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                n = create_table_from_csv(cursor, table_name, headers, rows, types)
                conn.commit()
                conn.close()
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Error", f"Failed to build database from CSV:\n{e}")
                return

            self.statusBar().showMessage(f"Built {db_path} ({n} rows)")
            QMessageBox.information(
                self, "Success",
                f"Built database at:\n{db_path}\n\nTable: {table_name}\nRows: {n}")

        # -- state ----------------------------------------------------------
        def clear_state(self):
            # Invalidate any in-flight worker so its result is dropped.
            self._load_gen += 1
            if self.db_conn:
                self.db_conn.close()
                self.db_conn = None
            self.db_path = None
            self.current_model = None
            self.csv_buffer = None
            self.table_list.clear()
            self.table_view.setModel(None)
            self.statusBar().showMessage("State cleared | Ready")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
