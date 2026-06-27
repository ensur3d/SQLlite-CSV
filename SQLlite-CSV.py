"""
SQL ↔ CSV Converter
A PyQt6 application for importing SQLite databases, viewing table data,
and exporting to CSV format.

Features:
- Open SQLite database files (.db, .sqlite, .sqlite3)
- Browse tables in the database
- View table data in a sortable grid
- Import CSV files into the application
- Export current table data to CSV
- Import CSV data into an existing database table
- Build a new SQLite database from a CSV file
- Preview CSV data before exporting
- Threaded database operations for responsive UI
"""

import sys
import sqlite3
import csv
import io
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTableView, QFileDialog, QStatusBar, QMessageBox,
    QDialog, QTextEdit, QPushButton, QLabel, QSplitter, QAbstractItemView,
    QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont

# -----------------------------------------------------------------------------
# Background Worker Thread (keeps GUI responsive during heavy operations)
# -----------------------------------------------------------------------------
class DBWorker(QThread):
    progress = pyqtSignal(int, str)  # percentage, message
    finished = pyqtSignal(list, list)  # headers, rows
    error = pyqtSignal(str)

    def __init__(self, db_path, table_name):
        super().__init__()
        self.db_path = db_path
        self.table_name = table_name

    def run(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self.progress.emit(20, "Fetching table structure...")

            cursor.execute(f"SELECT * FROM \"{self.table_name}\"")
            headers = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            total = len(rows)
            
            data = []
            for i, row in enumerate(rows):
                # Convert all values to strings for safe CSV handling
                data.append([str(val) if val is not None else "" for val in row])
                
                # Update progress every 100 rows
                if i % 100 == 0 and total > 0:
                    pct = int((i / total) * 80)
                    self.progress.emit(pct, f"Loaded {i}/{total} rows...")
            
            self.progress.emit(100, "Data ready!")
            self.finished.emit(headers, data)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if conn:
                conn.close()

# -----------------------------------------------------------------------------
# Main Application Window
# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQL ↔ CSV Converter")
        self.resize(1100, 700)
        self.setCentralWidget(QWidget())
        
        self.db_conn = None
        self.db_path = None
        self.current_model = None
        self.csv_buffer = None  # Stores data as dict with 'headers' and 'rows'
        
        self.setup_ui()

    def setup_ui(self):
        central = self.centralWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Top control bar
        ctrl_layout = QHBoxLayout()
        self.btn_open_db = QPushButton("📂 Open SQL Database")
        self.btn_import_csv = QPushButton("📥 Import CSV")
        self.btn_export_csv = QPushButton("📤 Export to CSV")
        self.btn_import_csv_to_db = QPushButton("📤 Import CSV to DB")
        self.btn_build_db = QPushButton("📦 Build DB from CSV")
        self.btn_preview_csv = QPushButton("👁️ Preview CSV")
        self.btn_clear = QPushButton("🗑️ Clear State")
        
        for btn in (self.btn_open_db, self.btn_import_csv, self.btn_export_csv, self.btn_import_csv_to_db, self.btn_build_db, self.btn_preview_csv, self.btn_clear):
            ctrl_layout.addWidget(btn)
        main_layout.addLayout(ctrl_layout)

        # Splitter: Left (Table List), Right (Data Grid)
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

        # Status bar (fixed font assignment)
        self.statusBar().showMessage("Ready | Current: None")
        self.statusBar().setFont(QFont("Segoe UI", 10))  # ✅ PyQt6 compatible

        # Connect signals
        self.btn_open_db.clicked.connect(self.open_sql_db)
        self.btn_import_csv.clicked.connect(self.import_csv)
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_import_csv_to_db.clicked.connect(self.import_csv_to_database)
        self.btn_build_db.clicked.connect(self.build_db_from_csv)
        self.btn_preview_csv.clicked.connect(self.preview_csv)
        self.btn_clear.clicked.connect(self.clear_state)
        self.table_list.currentRowChanged.connect(self.load_table_data)

    def open_sql_db(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SQL Database", "", 
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if not file_path:
            return

        try:
            self.db_conn = sqlite3.connect(file_path)
            self.db_path = file_path
            self.statusBar().showMessage(f"Connected: {file_path}")
            self.update_table_list()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to connect to database:\n{e}")
            self.db_conn = None
            self.db_path = None

    def update_table_list(self):
        if not self.db_conn:
            return
        self.table_list.clear()
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        self.table_list.addItems([row[0] for row in cursor.fetchall()])

    def load_table_data(self, row):
        if row < 0 or not self.db_conn:
            return

        table_name = self.table_list.item(row).text()
        self.statusBar().showMessage(f"Loading {table_name}...")
        QApplication.processEvents()  # Prevent UI freeze during thread start

        self.worker = DBWorker(self.db_path, table_name)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.display_data)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "DB Error", e))
        self.worker.start()

    def update_progress(self, pct, msg):
        self.statusBar().showMessage(f"{msg} ({pct}%)")

    def display_data(self, headers, rows):
        model = QStandardItemModel(len(rows), len(headers))
        model.setHorizontalHeaderLabels(headers)
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                model.setItem(r_idx, c_idx, QStandardItem(str(val)))
        self.table_view.setModel(model)
        self.table_view.resizeColumnsToContents()
        self.current_model = model
        self.csv_buffer = {'headers': headers, 'rows': rows}  # Keep for export/preview
        self.statusBar().showMessage(f"Loaded: {headers[0]}... | {len(rows)} rows | {len(headers)} cols")

    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                data = list(reader)
            
            if not data:
                QMessageBox.warning(self, "Warning", "CSV file is empty.")
                return

            headers = data[0]
            rows = data[1:]
            
            self.display_data(headers, rows)
            self.statusBar().showMessage(f"Imported CSV: {len(rows)} rows | {len(headers)} cols")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import CSV:\n{e}")

    def import_csv_to_database(self):
        if not self.csv_buffer:
            QMessageBox.warning(self, "Warning", "No data available to import to database.")
            return

        if not self.db_conn:
            QMessageBox.warning(self, "Warning", "Please open a database first.")
            return

        # Ask for table name
        table_name, ok = QInputDialog.getText(self, "Import to Database", "Enter table name:")
        if not ok or not table_name:
            return

        # Ask if table should be replaced if exists
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        table_exists = cursor.fetchone()
        
        if table_exists:
            reply = QMessageBox.question(self, "Table Exists", 
                                       f"Table '{table_name}' already exists. Replace it?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
            else:
                cursor.execute(f"DROP TABLE IF EXISTS \"{table_name}\"")

        try:
            # Create table with columns from CSV data
            headers = self.csv_buffer['headers']
            rows = self.csv_buffer['rows']
            
            # Generate CREATE TABLE statement
            # For simplicity, we'll make all columns TEXT type
            columns_def = ", ".join([f'"{header}" TEXT' for header in headers])
            create_table_sql = f'CREATE TABLE "{table_name}" ({columns_def})'
            cursor.execute(create_table_sql)
            
            # Insert data
            placeholders = ", ".join(["?" for _ in headers])
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
            
            # Insert rows in batches for better performance
            batch_size = 100
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                cursor.executemany(insert_sql, batch)
                self.statusBar().showMessage(f"Importing to database... {min(i+batch_size, len(rows))}/{len(rows)} rows")
                QApplication.processEvents()
            
            self.db_conn.commit()
            self.update_table_list()  # Refresh table list
            QMessageBox.information(self, "Success", f"Imported {len(rows)} rows to table '{table_name}'")
            self.statusBar().showMessage(f"Imported {len(rows)} rows to table '{table_name}'")
            
        except Exception as e:
            self.db_conn.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to import CSV to database:\n{e}")

    def build_db_from_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                data = list(reader)

            if not data:
                QMessageBox.warning(self, "Warning", "CSV file is empty.")
                return

            headers = data[0]
            rows = data[1:]

            self.statusBar().showMessage(f"Read {len(rows)} rows from CSV")
            QApplication.processEvents()

            # Ask where to save the new database
            db_path, _ = QFileDialog.getSaveFileName(self, "Save New Database As", "", "SQLite Files (*.db);;All Files (*)")
            if not db_path:
                return
            if not db_path.endswith(".db"):
                db_path += ".db"

            # Ask for table name
            table_name, ok = QInputDialog.getText(self, "Table Name", "Enter a name for the table:", text="imported_data")
            if not ok or not table_name:
                return

            QApplication.processEvents()

            # Build and populate the database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            columns_def = ", ".join([f'"{header}" TEXT' for header in headers])
            cursor.execute(f'CREATE TABLE "{table_name}" ({columns_def})')

            placeholders = ", ".join(["?" for _ in headers])
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

            batch_size = 100
            total = len(rows)
            for i in range(0, total, batch_size):
                batch = rows[i:i+batch_size]
                cursor.executemany(insert_sql, batch)
                pct = int((i + len(batch)) / total * 100) if total > 0 else 100
                self.statusBar().showMessage(f"Building database... {min(i+batch_size, total)}/{total} rows ({pct}%)")
                QApplication.processEvents()

            conn.commit()
            conn.close()

            # Ask if user wants to open the new database
            reply = QMessageBox.question(self, "Database Created",
                                       f"Created database with {total} rows in table '{table_name}'.\n\nOpen it now?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.clear_state()
                self.db_conn = sqlite3.connect(db_path)
                self.db_path = db_path
                self.statusBar().showMessage(f"Connected: {db_path}")
                self.update_table_list()

            QMessageBox.information(self, "Success", f"Built database at:\n{db_path}\n\nTable: {table_name}\nRows: {total}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build database from CSV:\n{e}")

    def export_csv(self):
        if not self.current_model or self.current_model.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data selected to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        if not file_path.endswith(".csv"):
            file_path += ".csv"

        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
                # Headers
                from PyQt6.QtCore import Qt
                headers = [self.current_model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) for i in range(self.current_model.columnCount())]
                writer.writerow(headers)
                # Rows
                for r in range(self.current_model.rowCount()):
                    row_data = [self.current_model.index(r, c).data() for c in range(self.current_model.columnCount())]
                    writer.writerow(row_data)
            
            QMessageBox.information(self, "Success", f"Exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{e}")

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

        # Generate CSV string
        output = io.StringIO()
        writer = csv.writer(output)
        if self.csv_buffer:
            writer.writerow(self.csv_buffer['headers'])
            for row in self.csv_buffer['rows']:
                writer.writerow(row)
        editor.setPlainText(output.getvalue())
        dialog.exec()

    def clear_state(self):
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None
        
        self.current_model = None
        self.csv_buffer = None
        self.table_list.clear()
        self.table_view.setModel(None)
        self.statusBar().showMessage("State cleared | Ready")
        QMessageBox.information(self, "Cleared", "Database and data cleared. Ready for new input.")

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Cross-platform consistent look
    window = MainWindow()
    window.show()
    sys.exit(app.exec())