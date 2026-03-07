"""Web GUI launcher for pysysfan.

This module handles launching the GUI either in a browser for development
or via Tauri for production builds.
"""

import subprocess
import sys
import webbrowser
from pathlib import Path


def launch_gui():
    """Launch the PySysFan GUI.

    In development mode, this starts the Vite dev server and opens a browser.
    In production (Tauri), this should be handled by the Tauri runtime.
    """
    web_dir = Path(__file__).parent

    # Check if we're in development mode (vite is available)
    if (web_dir / "node_modules" / ".bin" / "vite").exists() or (
        web_dir / "node_modules" / ".bin" / "vite.cmd"
    ).exists():
        # Development mode - start vite dev server
        _launch_dev_mode(web_dir)
    else:
        # Production mode - check for Tauri or static build
        _launch_production_mode(web_dir)


def _launch_dev_mode(web_dir: Path):
    """Launch the GUI in development mode using Vite."""
    print("Starting PySysFan GUI in development mode...")
    print(f"Working directory: {web_dir}")

    # Start Vite dev server
    try:
        if sys.platform == "win32":
            vite_cmd = ["npm", "run", "dev"]
        else:
            vite_cmd = ["npm", "run", "dev"]

        # Open browser after a short delay
        import threading
        import time

        def open_browser():
            time.sleep(3)  # Wait for server to start
            webbrowser.open("http://localhost:5173")

        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()

        # Run npm dev server
        subprocess.run(
            vite_cmd,
            cwd=web_dir,
            check=True,
        )
    except FileNotFoundError:
        print(
            "Error: npm not found. Please install Node.js and run 'npm install' in the web directory."
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error starting dev server: {e}")
        sys.exit(1)


def _launch_production_mode(web_dir: Path):
    """Launch the GUI in production mode."""
    tauri_dir = web_dir.parent / "tauri"

    if tauri_dir.exists():
        # Try to launch Tauri app
        _launch_tauri(tauri_dir)
    else:
        # Try to open static build
        dist_dir = web_dir.parent / "tauri" / "dist"
        index_html = dist_dir / "index.html"

        if index_html.exists():
            webbrowser.open(f"file://{index_html}")
        else:
            print("Error: No production build found.")
            print("Please build the GUI first with: npm run build")
            sys.exit(1)


def _launch_tauri(tauri_dir: Path):
    """Launch the Tauri application."""
    print("Launching Tauri application...")

    # Look for the built Tauri binary
    src_tauri = tauri_dir / "src-tauri"

    if sys.platform == "win32":
        exe_path = src_tauri / "target" / "release" / "pysysfan-gui.exe"
        if not exe_path.exists():
            exe_path = src_tauri / "target" / "debug" / "pysysfan-gui.exe"
    else:
        exe_path = src_tauri / "target" / "release" / "pysysfan-gui"
        if not exe_path.exists():
            exe_path = src_tauri / "target" / "debug" / "pysysfan-gui"

    if exe_path.exists():
        subprocess.run([str(exe_path)], check=False)
    else:
        print("Error: Tauri binary not found. Please build with: cargo tauri build")
        sys.exit(1)
