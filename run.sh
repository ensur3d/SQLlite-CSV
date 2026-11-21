#!/usr/bin/env bash
#
# SQL <-> CSV Converter — launcher
# --------------------------------
# The single, easy way to run this project:
#
#   ./run.sh                 # launch the GUI (auto-sets up venv + deps on first run)
#   ./run.sh install         # set up the environment only, then exit
#   ./run.sh tables DB       # list tables in a database            (headless, no GUI)
#   ./run.sh db2csv DB -t T  # export one table to CSV              (headless, no GUI)
#   ./run.sh csv2db FILE.csv # build a database from a CSV          (headless, no GUI)
#
# The headless commands need only Python 3 (no display, no PyQt6).
# If something is missing (Python 3, the venv module, or a dependency), the
# script detects your operating system and prints the exact command to fix it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
APP="$SCRIPT_DIR/sqlcsv.py"
VENV="$SCRIPT_DIR/.venv"
PY="$VENV/bin/python"

# --- OS detection (so error messages can be targeted) ------------------------
detect_os() {
  OS_FAMILY="unknown"
  OS_ID=""
  OS_ID_LIKE=""
  local uname_s
  uname_s="$(uname -s 2>/dev/null || echo unknown)"

  case "$uname_s" in
    Darwin) OS_FAMILY="macos" ;;
    Linux)
      OS_FAMILY="linux"
      if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        OS_ID="${ID:-}"
        OS_ID_LIKE="${ID_LIKE:-}"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT) OS_FAMILY="windows" ;;
  esac

  case "$OS_FAMILY" in
    macos)   OS_LABEL="macOS" ;;
    windows) OS_LABEL="Windows (Git Bash / MSYS2)" ;;
    linux)   OS_LABEL="${NAME:-Linux}" ;;
    *)       OS_LABEL="$uname_s" ;;
  esac
}

hint_python_install() {
  case "$OS_FAMILY" in
    macos)
      echo "Install Python 3 on macOS, e.g.:"
      echo "  Homebrew:   brew install python"
      echo "  or download from https://www.python.org/downloads/macos/"
      ;;
    windows)
      echo "Install Python 3 on Windows:"
      echo "  Download the installer from https://www.python.org/downloads/ (tick 'Add to PATH')"
      echo "  or use WSL: sudo apt install python3 python3-pip python3-venv"
      ;;
    linux)
      case "${OS_ID:-} ${OS_ID_LIKE:-}" in
        *fedora*|*rhel*|*centos*)
          echo "Install Python 3 on ${OS_LABEL}:"
          echo "  sudo dnf install python3 python3-pip python3-virtualenv" ;;
        *arch*|*manjaro*)
          echo "Install Python 3 on ${OS_LABEL}:"
          echo "  sudo pacman -S python python-pip python-virtualenv" ;;
        *debian*|*ubuntu*)
          echo "Install Python 3 on ${OS_LABEL}:"
          echo "  sudo apt update && sudo apt install python3 python3-pip python3-venv" ;;
        *)
          echo "Install Python 3 (common commands):"
          echo "  Debian/Ubuntu: sudo apt update && sudo apt install python3 python3-pip python3-venv"
          echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip python3-virtualenv"
          echo "  Arch Linux:    sudo pacman -S python python-pip python-virtualenv"
          ;;
      esac
      ;;
    *)
      echo "Install Python 3 from https://www.python.org/downloads/"
      ;;
  esac
}

hint_venv_module() {
  case "$OS_FAMILY" in
    macos)
      echo "  Ensure Python includes the venv module (Homebrew builds do): brew install python"
      ;;
    windows)
      echo "  In WSL: sudo apt install python3-venv. On native Windows use the python.org installer."
      ;;
    linux)
      case "${OS_ID:-} ${OS_ID_LIKE:-}" in
        *fedora*|*rhel*|*centos*) echo "  sudo dnf install python3-virtualenv" ;;
        *arch*|*manjaro*)         echo "  sudo pacman -S python-virtualenv" ;;
        *debian*|*ubuntu*)        echo "  sudo apt install python3-venv" ;;
        *)                        echo "  Install the 'python3-venv' (or equivalent) package for your distro." ;;
      esac
      ;;
    *)
      echo "  Ensure your Python installation includes the 'venv' module."
      ;;
  esac
}

need_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found on this system (${OS_LABEL})." >&2
    hint_python_install >&2
    exit 1
  fi
}

make_venv() {
  if [ ! -x "$PY" ]; then
    echo "Creating virtual environment in .venv ..."
    if ! python3 -m venv "$VENV"; then
      echo "ERROR: could not create a virtual environment." >&2
      echo "This usually means the 'venv' module is missing. Fix for ${OS_LABEL}:" >&2
      hint_venv_module >&2
      exit 1
    fi
  fi
}

install_deps() {
  if ! "$PY" -c "import PyQt6" >/dev/null 2>&1; then
    echo "Installing dependencies (first run may take a minute) ..."
    "$PY" -m pip install --upgrade pip >/dev/null 2>&1 || true   # best-effort
    if ! "$PY" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
      echo "ERROR: failed to install dependencies (PyQt6)." >&2
      echo "  - Check your internet connection and re-run './run.sh'." >&2
      echo "  - If pip is missing, try: $PY -m ensurepip --upgrade" >&2
      exit 1
    fi
  fi
}

# --- detect the OS once so error messages can be targeted ---------------------
detect_os

# --- pure setup command: build the environment and stop ----------------------
if [ "${1:-}" = "install" ]; then
  need_python
  make_venv
  install_deps
  echo "Environment ready. Run './run.sh' to launch the app."
  exit 0
fi

cmd="${1:-gui}"
case "$cmd" in
  gui|run|"")            # GUI: needs a venv + PyQt6
    need_python
    make_venv
    install_deps
    exec "$PY" "$APP" "${@:2}"
    ;;
  *)                     # headless CLI (tables / db2csv / csv2db): stdlib only
    need_python
    exec python3 "$APP" "$@"
    ;;
esac
