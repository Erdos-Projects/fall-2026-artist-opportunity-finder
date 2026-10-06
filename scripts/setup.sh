#!/usr/bin/env bash
# Local environment setup for Linux and macOS (Part A: data collection, cleaning, labeling).
#
# Run from a terminal in the project folder. Use "source" so the environment
# stays active in your terminal afterwards:
#     source scripts/setup.sh
#
# Running it as "bash scripts/setup.sh" also works, but a script cannot activate
# the environment for the terminal that launched it, so you activate it yourself.
#
# Safe to run again at any time. It reuses the existing .venv and only installs
# what is missing.

# Everything lives in a function and fails with "return", because "exit" or
# "set -e" in a sourced script would close the user's terminal.
_setup_local_env() {
    local script_path="${BASH_SOURCE[0]:-$0}"
    local root
    root="$(cd "$(dirname "$script_path")/.." && pwd)" || return 1
    local venv="$root/.venv"
    local venv_python="$venv/bin/python"
    local requirements="$root/requirements.txt"
    local python_version="3.12"

    local have_uv=0
    command -v uv >/dev/null 2>&1 && have_uv=1

    # 1. Create the virtual environment
    if [ -x "$venv_python" ]; then
        echo "Virtual environment already exists at .venv"
    elif [ "$have_uv" -eq 1 ]; then
        echo "Creating virtual environment with uv (Python $python_version)..."
        uv venv --python "$python_version" "$venv" || {
            echo "Could not create the virtual environment." >&2
            return 1
        }
    elif command -v python3 >/dev/null 2>&1; then
        echo "Creating virtual environment with $(command -v python3)..."
        python3 -m venv "$venv" || {
            echo "Could not create the virtual environment." >&2
            echo "On Debian or Ubuntu you may need: sudo apt install python3-venv" >&2
            return 1
        }
    else
        echo "No Python found. Install uv (https://docs.astral.sh/uv/) or Python $python_version, then run this script again." >&2
        return 1
    fi

    # 2. Install packages
    echo "Installing packages from requirements.txt..."
    if [ "$have_uv" -eq 1 ]; then
        uv pip install --python "$venv_python" -r "$requirements"
    else
        "$venv_python" -m pip install -r "$requirements"
    fi || {
        echo "Package installation failed." >&2
        return 1
    }

    # 3. Create the data folders (their contents are ignored by git)
    local name
    for name in raw clean labeled; do
        mkdir -p "$root/data/$name" || return 1
        [ -e "$root/data/$name/.gitkeep" ] || : > "$root/data/$name/.gitkeep"
    done

    # 4. Activate the environment in the current terminal
    # shellcheck disable=SC1091
    . "$venv/bin/activate" || return 1
}

if _setup_local_env; then
    echo ""
    if (return 0 2>/dev/null); then
        echo "Setup complete. The environment is active in this terminal."
        echo "Next time, activate it with:  source .venv/bin/activate"
    else
        echo "Setup complete. Activate the environment with:  source .venv/bin/activate"
    fi
    echo "Leave it with:                deactivate"
    unset -f _setup_local_env
else
    unset -f _setup_local_env
    # "return" works when sourced, "exit" covers a normal run.
    return 1 2>/dev/null || exit 1
fi
