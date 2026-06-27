import os
import sys
import shutil
import subprocess
import urllib.request
import tempfile

def check_command(cmd):
    return shutil.which(cmd) is not None

def install_rust():
    print("[Bootstrap] Rust (rustc) is not installed. Installing Rustup...")
    if os.name == 'nt':
        # On Windows, try installing via winget first (user-friendly and clean)
        if check_command("winget"):
            try:
                print("[Bootstrap] Found winget. Installing Rust via winget...")
                subprocess.check_call([
                    "winget", "install", "--id", "Rust.Rustup", 
                    "--silent", "--accept-package-agreements", "--accept-source-agreements"
                ])
                print("[Bootstrap] Rust installation via winget triggered successfully.")
                return
            except Exception as e:
                print(f"[Bootstrap] winget installation failed: {e}. Falling back to direct download...")
        
        # Fallback: Download rustup-init.exe
        url = "https://win.rustup.rs/x86_64"
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "rustup-init.exe")
        print(f"[Bootstrap] Downloading rustup-init.exe from {url}...")
        urllib.request.urlretrieve(url, installer_path)
        print("[Bootstrap] Running rustup-init.exe silently...")
        subprocess.check_call([installer_path, "-y", "--default-toolchain", "stable"])
        
        # Add cargo bin to path for current session
        cargo_bin = os.path.expanduser("~/.cargo/bin")
        if cargo_bin not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + cargo_bin
    else:
        # On Unix, run rustup installer script
        print("[Bootstrap] Downloading and running rustup installer script...")
        script = urllib.request.urlopen("https://sh.rustup.rs").read()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(script)
            script_path = f.name
        try:
            subprocess.check_call(["sh", script_path, "-y"])
            # Add cargo bin to path
            cargo_bin = os.path.expanduser("~/.cargo/bin")
            if cargo_bin not in os.environ["PATH"]:
                os.environ["PATH"] += os.pathsep + cargo_bin
        finally:
            os.unlink(script_path)

def install_uv():
    print("[Bootstrap] uv is not installed. Installing uv...")
    # Try installing via pip first since we are running Python
    try:
        print("[Bootstrap] Attempting to install uv via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uv"])
        print("[Bootstrap] uv successfully installed via pip.")
        return
    except Exception as e:
        print(f"[Bootstrap] Failed to install uv via pip: {e}")
    
    # Fallback to web installers
    if os.name == 'nt':
        print("[Bootstrap] Trying to install uv via PowerShell installer...")
        ps_cmd = "irm https://astral.sh/uv/install.ps1 | iex"
        subprocess.check_call(["powershell", "-Command", ps_cmd])
        # Add uv bin to path
        uv_bin = os.path.expanduser("~/.local/bin")
        if uv_bin not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + uv_bin
    else:
        print("[Bootstrap] Trying to install uv via curl shell script...")
        subprocess.check_call(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"])
        # Add uv bin to path
        uv_bin = os.path.expanduser("~/.local/bin")
        if uv_bin not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + uv_bin

def main():
    # ANSI Colors
    CYAN = ""
    RESET = ""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            CYAN = "\033[36m"
            RESET = "\033[0m"
        except:
            pass
    else:
        CYAN = "\033[36m"
        RESET = "\033[0m"

    art = r"""
.----------------------------------------.
|                                        |
|   _    ___ ___ __  __       ___  ___   |
|  | |  |_ _| __|  \/  |     / _ \/ __|  |
|  | |__ | || _|| |\/| |    | (_) \__ \  |
|  |____|___|___|_|  |_|     \___/|___/  |
|                                        |
'----------------------------------------'"""
    print(f"\n{CYAN}{art}{RESET}")
    print("[Bootstrap] Starting LIEM OS automated environment bootstrapper...")
    
    # 1. Rust Check and Installation
    if not check_command("rustc"):
        try:
            install_rust()
        except Exception as e:
            print(f"[Bootstrap] Warning: Rust installation failed: {e}")
            print("[Bootstrap] Proceeding with bootstrap anyway (some dependencies may require Rust during compilation)...")
    else:
        print("[Bootstrap] Rust is already installed.")
        
    # 2. uv Check and Installation
    if not check_command("uv"):
        try:
            install_uv()
        except Exception as e:
            print(f"[Bootstrap] Error: uv installation failed: {e}")
            sys.exit(1)
    else:
        print("[Bootstrap] uv is already installed.")
        
    # Resolve uv executable path
    uv_bin = "uv"
    if not check_command("uv"):
        # If uv was installed in this session and not refreshed in PATH yet, check standard paths
        local_uv_win = os.path.expanduser("~/.local/bin/uv.exe")
        local_uv_unix = os.path.expanduser("~/.local/bin/uv")
        cargo_uv_win = os.path.expanduser("~/.cargo/bin/uv.exe")
        cargo_uv_unix = os.path.expanduser("~/.cargo/bin/uv")
        
        for candidate in [local_uv_win, local_uv_unix, cargo_uv_win, cargo_uv_unix]:
            if os.path.exists(candidate):
                uv_bin = candidate
                # Add directory to PATH so subprocesses can find it
                os.environ["PATH"] += os.pathsep + os.path.dirname(candidate)
                break
                
    # 3. Create virtual environment
    venv_created = False
    venv_python = os.path.join(".venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join(".venv", "bin", "python")
    
    if os.path.exists(".venv") and os.path.exists(venv_python):
        print("[Bootstrap] Existing virtual environment (.venv) detected. Reusing it to update dependencies...")
        venv_created = True
    else:
        print("[Bootstrap] Creating virtual environment (.venv) using uv...")
        if os.path.exists(".venv"):
            try:
                print("[Bootstrap] Cleaning incomplete/corrupted .venv directory...")
                shutil.rmtree(".venv")
            except Exception as e:
                print(f"[Bootstrap] Warning: Could not remove existing .venv folder: {e}")
                print("[Bootstrap] Please close any active terminal shells, editor instances, or dashboard servers locking the virtual environment.")
        
        try:
            # Run uv venv with default python
            subprocess.check_call([uv_bin, "venv", ".venv"])
            print("[Bootstrap] Virtual environment created successfully using default Python.")
            venv_created = True
        except Exception as e:
            print(f"[Bootstrap] Default Python venv creation failed or errored: {e}.")
            
    if not venv_created:
        try:
            # Install python 3.12.10 via uv
            print("[Bootstrap] Installing Python 3.12.10 via uv...")
            subprocess.check_call([uv_bin, "python", "install", "3.12.10"])
            # Create virtual env with python 3.12.10
            print("[Bootstrap] Creating virtual environment using Python 3.12.10...")
            subprocess.check_call([uv_bin, "venv", ".venv", "--python", "3.12.10"])
            print("[Bootstrap] Virtual environment created successfully using Python 3.12.10.")
        except Exception as e:
            print(f"[Bootstrap] Error creating virtual environment with Python 3.12.10: {e}")
            sys.exit(1)
            
    # 4. Install dependencies in editable mode
    print("[Bootstrap] Installing LIEM OS package and dependencies...")
    try:
        # Construct environment with virtualenv set
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = os.path.abspath(".venv")
        
        # Add venv bin/Scripts to path for the installation command
        venv_bin_dir = os.path.join(os.path.abspath(".venv"), "Scripts" if os.name == 'nt' else "bin")
        env["PATH"] = venv_bin_dir + os.pathsep + env["PATH"]
        
        subprocess.check_call([uv_bin, "pip", "install", "-e", "."], env=env)
        print("[Bootstrap] Package and dependencies successfully installed in editable mode.")
    except Exception as e:
        print(f"[Bootstrap] Error installing dependencies: {e}")
        sys.exit(1)
        
    print_completion_card()

def print_completion_card():
    # ANSI Colors
    CYAN = ""
    GREEN = ""
    RESET = ""
    
    # Enable Windows ANSI support using ctypes
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable ENABLE_PROCESSED_OUTPUT (1) and ENABLE_VIRTUAL_TERMINAL_PROCESSING (4)
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            CYAN = "\033[36m"
            GREEN = "\033[32m"
            RESET = "\033[0m"
        except:
            pass
    else:
        CYAN = "\033[36m"
        GREEN = "\033[32m"
        RESET = "\033[0m"

    # Try importing rich from the new virtual environment dynamically
    try:
        # Resolve site-packages directory in the virtual environment
        if os.name == 'nt':
            site_packages = os.path.join(os.path.abspath(".venv"), "Lib", "site-packages")
        else:
            lib_path = os.path.join(os.path.abspath(".venv"), "lib")
            python_dirs = [d for d in os.listdir(lib_path) if d.startswith("python")] if os.path.exists(lib_path) else []
            if python_dirs:
                site_packages = os.path.join(lib_path, python_dirs[0], "site-packages")
            else:
                site_packages = os.path.join(lib_path, f"python3.{sys.version_info.minor}", "site-packages")
        
        if os.path.exists(site_packages) and site_packages not in sys.path:
            sys.path.insert(0, site_packages)
            
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        
        console = Console()
        text = Text()
        text.append("SUCCESS: ", style="bold green")
        text.append("LIEM OS bootstrap completed successfully!\n\n", style="bold cyan")
        text.append("To initialize your first project workspace, run:\n", style="bold white")
        if os.name == 'nt':
            text.append("-> .venv\\Scripts\\liem-os init <project-name>", style="cyan")
        else:
            text.append("-> .venv/bin/liem-os init <project-name>", style="cyan")
            
        panel = Panel(
            text,
            title="[bold green]LIEM OS ENGINE[/bold green]",
            border_style="green",
            expand=False,
            padding=(1, 2)
        )
        print()
        console.print(panel)
        
    except Exception:
        # Fallback to clean colored text if rich fails to load (no misaligned box)
        print(f"\n{GREEN}============================================================{RESET}")
        print(f"{GREEN}SUCCESS:{RESET} LIEM OS bootstrap completed successfully!")
        print("\nTo initialize your first project workspace, run:")
        if os.name == 'nt':
            print(f"  {CYAN}.venv\\Scripts\\liem-os init <project-name>{RESET}")
        else:
            print(f"  {CYAN}.venv/bin/liem-os init <project-name>{RESET}")
        print(f"{GREEN}============================================================{RESET}")


if __name__ == "__main__":
    main()
