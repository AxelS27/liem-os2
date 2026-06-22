import os
import sys
import subprocess

def build():
    print("=== LIEM OS STANDALONE EXE BUILDER ===")
    
    # Auto-relaunch inside virtual environment if present
    venv_python = os.path.join(".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(".venv", "bin", "python")
    if os.path.exists(venv_python):
        abs_venv = os.path.abspath(venv_python)
        if os.path.abspath(sys.executable) != abs_venv:
            print(f"Relaunching build.py inside virtual environment: {venv_python}...")
            cmd = [abs_venv] + sys.argv
            sys.exit(subprocess.call(cmd))
            return
    
    # Check if pyinstaller is installed
    try:
        import PyInstaller
        print("PyInstaller found. Ready to compile.")
    except ImportError:
        print("PyInstaller not found. Installing via uv...")
        import shutil
        if shutil.which("uv"):
            try:
                # Use uv pip install. If not in a virtual environment, append --system.
                in_venv = sys.prefix != sys.base_prefix
                cmd = ["uv", "pip", "install"]
                if not in_venv:
                    cmd.append("--system")
                cmd.append("pyinstaller")
                print(f"Running: {' '.join(cmd)}")
                subprocess.check_call(cmd)
            except Exception as e:
                print(f"Failed to install with uv: {e}. Falling back to pip...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        else:
            print("uv not found. Falling back to pip...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    # We target src/liem_os/main.py as the entry point
    entry_point = os.path.join("src", "liem_os", "main.py")
    
    # PyInstaller data files separator (semicolon for Windows, colon for Linux/macOS)
    sep = os.pathsep
    
    # Find the correct PyInstaller executable path (e.g., in the virtual environment's Scripts/ or bin/)
    pyinstaller_bin = "pyinstaller"
    pyinstaller_dir = os.path.dirname(sys.executable)
    for ext in ["", ".exe"]:
        candidate = os.path.join(pyinstaller_dir, "pyinstaller" + ext)
        if os.path.exists(candidate):
            pyinstaller_bin = candidate
            break
            
    cmd = [
        pyinstaller_bin,
        "--onefile",
        "--noconsole",
        "--name", "liem-os",
        "--add-data", f"src/liem_os/dashboard{sep}liem_os/dashboard",
        entry_point
    ]
    
    print(f"Running compilation command: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("\n=== BUILD SUCCESSFUL ===")
        print("Standalone executable has been created and saved at: dist/liem-os.exe")
    except subprocess.CalledProcessError as e:
        print(f"\nError occurred during PyInstaller compilation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
