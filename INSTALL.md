# Installation guide

This is the longer, walk-you-through-it version. The README has the short
version. If something here is confusing, email Fernando
(neurokreative@gmail.com).

---

## What you need

- A computer running macOS, Linux, or Windows
- Python 3.10 or newer (this guide walks through installing it)
- About 10 minutes for first-time setup
- Internet connection (only needed for the first install — runs offline after that)

---

## Step 1 — Install Python

You only have to do this once per computer.

### On Windows

1. Go to <https://www.python.org/downloads/>
2. Click the big yellow **"Download Python 3.x.x"** button
3. Open the downloaded `.exe` file
4. **CRITICAL — at the bottom of the install window, check the box that says
   "Add python.exe to PATH"** before you click Install. If you miss this step,
   nothing will work and you'll have to reinstall.
5. Click **Install Now** and wait for it to finish.
6. Close any open terminals/PowerShell windows.

> ⚠️ **Don't install Python from the Microsoft Store.** Windows 10/11 ships
> with a placeholder named `python` that, when you run it, opens the
> Microsoft Store and offers to install Python from there. The Store version
> often has permission issues that break virtual environments. Always
> install from python.org instead.
>
> If you've already accidentally installed the Store version, uninstall it
> via Settings → Apps → Installed apps, then disable the placeholder via
> **Settings → Apps → Advanced app settings → App execution aliases** (turn
> off both `python.exe` and `python3.exe`), then install from python.org.

### On macOS

The easiest path is **Anaconda**:

1. Go to <https://www.anaconda.com/download>
2. Download the macOS installer (Apple Silicon `.pkg` for M1/M2/M3 Macs;
   Intel `.pkg` for older Macs — your About This Mac will tell you which)
3. Open the `.pkg` file and follow the installer
4. Open a fresh Terminal window after installing

If you prefer not to install Anaconda, use Homebrew:

```bash
brew install python@3.12
```

### On Linux

Use your package manager. Examples:

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip

# Fedora
sudo dnf install python3.12

# Arch
sudo pacman -S python python-pip
```

---

## Step 2 — Verify Python works

Open a fresh terminal (PowerShell on Windows, Terminal on macOS, your shell
on Linux) and type:

```bash
python --version
```

(On macOS/Linux you may need `python3 --version` instead.)

You should see something like `Python 3.12.4`. If you see version 3.10 or
higher, you're good.

If you see `command not found` or version 2.x:

- **On Windows:** the "Add to PATH" checkbox was probably missed. Re-run the
  Python installer, choose "Modify", and add it to PATH. Then close and
  reopen PowerShell.
- **On macOS/Linux:** try `python3` instead of `python`. If that works, you
  can use `python3` everywhere else in this guide.

---

## Step 3 — Download CAVE FRF

### Option A: download the ZIP (no git needed)

1. Go to the repository page on GitHub
2. Click the green **Code** button
3. Click **Download ZIP**
4. Unzip it somewhere you'll remember (Documents folder is fine)
5. Open a terminal and `cd` into the unzipped folder

### Option B: clone with git (preferred if you might contribute)

```bash
git clone https://github.com/YOUR_USERNAME/cave-frf.git
cd cave-frf
```

---

## Step 4 — Run the app

### On macOS / Linux

```bash
./run.sh
```

If you get "Permission denied", run this once:

```bash
chmod +x run.sh
./run.sh
```

### On Windows

Either double-click `run.bat` from File Explorer, or in PowerShell:

```powershell
.\run.bat
```

The first run takes about a minute — it sets up a project-local Python
environment and installs the dependencies. Subsequent runs start in a few
seconds.

When you see the message about `http://localhost:8501`, your browser should
open automatically. If it doesn't, copy that URL into your browser.

---

## Step 5 — (Optional but recommended) Install the data-protection hook

If you forked or cloned the repo and might commit changes back, install the
pre-commit hook. This refuses commits that contain subject data files.

### macOS / Linux

```bash
bash scripts/install_hooks.sh
```

### Windows

```powershell
scripts\install_hooks.bat
```

You only have to do this once per clone of the repo.

---

## Common problems and fixes

### "python: command not found" / "'python' is not recognized"

Python isn't on your PATH. Easiest fix: reinstall Python and check the
"Add to PATH" box during install (Windows) or use the Anaconda installer
(macOS), which handles PATH for you.

### Windows says "Python was not found; run without arguments to install from the Microsoft Store"

This is the most common Windows install failure. You're seeing the Windows
*placeholder* for Python, not real Python. Even if you've installed Python
from python.org, the placeholder can take precedence on PATH.

**Fix:**

1. Disable the placeholder: **Settings → Apps → Advanced app settings →
   App execution aliases** → turn OFF both `python.exe` and `python3.exe`
2. If you haven't yet installed Python from python.org, do that now —
   making sure to check **"Add python.exe to PATH"** during install
3. Close all PowerShell/Command Prompt windows
4. Open a fresh one and run `run.bat` again

### "ssl module is not available" or pip can't connect

Your Python install is missing SSL support. On Linux this means installing
`python3-pip` and `ca-certificates` from your package manager. On Windows
this is rare but means reinstalling Python.

### "ERROR: Could not install packages" / "Permission denied" from pip

The launcher creates a project-local virtual environment to avoid this.
If you see permission errors, delete the `.venv/` folder in the repo and
re-run the launcher.

### The browser doesn't open automatically

Manually visit <http://localhost:8501> in any browser. Streamlit prints
the URL in the terminal when it starts.

### Port 8501 is already in use

Another Streamlit instance is running, or another app grabbed that port.
Either stop the other one, or run with a different port:

```bash
.venv/bin/python -m streamlit run app.py --server.port 8502
```

### "ModuleNotFoundError: No module named 'cave_frf'"

You're running from outside the repo folder. `cd` into the folder before
running the launcher.

### The folder picker can't see my Google Drive files

Make sure Google Drive Desktop is installed and the folder is set to
"Available offline" (right-click → Drive → Available offline). The pipeline
needs the actual files on disk, not stream-only references.

### I still can't get it working

Email Fernando (neurokreative@gmail.com) with:

- What OS and version (e.g., "macOS Sonoma 14.5", "Windows 11 22H2")
- The output of `python --version`
- The exact error message
- What command you ran

---

## Updating to a new version

When new versions are released:

1. Download the new ZIP (or `git pull` if you cloned)
2. Re-run `./run.sh` (or `run.bat`). The launcher will install any new
   dependencies automatically.

If a new version changes the analysis methodology, your cached results
may need to be regenerated. To force a clean re-run, delete the cache
folder shown in the UI sidebar, or pass `--no-cache` on the CLI.

---

## Uninstalling

Just delete the `cave-frf` folder. Everything (Python venv, cached results,
dependencies) lives inside it.

To also remove Python itself: use the standard uninstaller for whichever
method you used to install it (Add/Remove Programs on Windows, the Anaconda
uninstaller on macOS, your package manager on Linux).
