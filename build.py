import os
import sys
import subprocess

def build():
    print("=== LIEM OS STANDALONE EXE BUILDER ===")
    
    # Check if pyinstaller is installed
    try:
        import PyInstaller
        print("PyInstaller found. Ready to compile.")
    except ImportError:
        print("PyInstaller not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    # We target src/liem_os/main.py as the entry point
    entry_point = os.path.join("src", "liem_os", "main.py")
    
    # PyInstaller data files separator (semicolon for Windows, colon for Linux/macOS)
    sep = os.pathsep
    
    cmd = [
        "pyinstaller",
        "--onefile",
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
