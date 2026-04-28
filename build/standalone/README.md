# Standalone executable build (EXPERIMENTAL)

> **Read this first.** The supported way to run CAVE FRF is the Python +
> launcher route documented in the project [README.md](../../README.md).
> This standalone-executable path exists for users who absolutely cannot
> install Python — but bundling Streamlit apps with PyInstaller is fragile,
> and the maintainer does not provide pre-built binaries. **You build it
> yourself on the same OS you'll run it on**, and you are on your own
> debugging it. If it fails, fall back to the Python install path.

## Why this exists

Some students or collaborators may be on locked-down lab computers where
they can't install Python. For those cases, a self-contained executable
that can be copied to a USB stick and run directly is occasionally useful.

## What you get

A folder called `CAVE_FRF/` (around 300 MB) containing:

- An executable (`CAVE_FRF` on Mac/Linux, `CAVE_FRF.exe` on Windows)
- All bundled Python modules and dependencies

Double-click the executable. A terminal window opens, then a browser tab
opens with the UI.

## Why building works on YOUR machine but not as a download

PyInstaller produces a binary for the OS you build on:

- Build on macOS → Mac `.app` (won't run on Windows)
- Build on Windows → `.exe` (won't run on Mac)
- Build on Linux → ELF binary (won't run on either)

You must run the build on the same OS as your target users.

## Building

### Prerequisites

The same Python install you'd use for the regular launcher route, plus
PyInstaller:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### Build command

From the repository root:

```bash
pyinstaller build/standalone/cave_frf.spec --noconfirm
```

This takes 5–15 minutes. The output appears in `dist/CAVE_FRF/`.

### Test the bundle

```bash
# macOS / Linux
./dist/CAVE_FRF/CAVE_FRF

# Windows
dist\CAVE_FRF\CAVE_FRF.exe
```

If the UI opens in a browser, the build worked.

### Distributing

- **macOS:** zip the `dist/CAVE_FRF/` folder. Recipients double-click the
  executable inside. They will get a "developer cannot be verified" warning
  on first run; they need to right-click → Open → Open. (Code-signing the
  bundle to remove that warning costs $99/year for an Apple Developer
  account — almost certainly not worth it for a research tool.)
- **Windows:** zip the `dist\CAVE_FRF\` folder. Recipients unzip and
  double-click `CAVE_FRF.exe`. Windows SmartScreen may warn that the
  publisher is unrecognized; users click "More info" → "Run anyway".
- **Linux:** zip and ship. Recipients `chmod +x CAVE_FRF` and run.

## Common build failures

### "ModuleNotFoundError: No module named X" at runtime

PyInstaller missed a dynamically-imported module. Open the spec file
(`build/standalone/cave_frf.spec`), add the module name to the
`hiddenimports` list, and rebuild.

### "RuntimeError: Could not find a version that satisfies the requirement"

You have a version mismatch between Streamlit and PyInstaller. Try:

```bash
pip install --upgrade streamlit pyinstaller
```

### Streamlit launches but the page is blank

This is typically Streamlit failing to find its static assets in the
bundle. The spec file already calls `collect_all('streamlit')` to gather
these — if it's still broken, your Streamlit version may be incompatible
with PyInstaller. Try downgrading to a known-good version:

```bash
pip install 'streamlit<1.40'
```

### "PermissionError" or "could not get source files" on macOS

macOS Gatekeeper is blocking the unsigned bundle. Right-click the
executable → Open → confirm. You only need to do this once per machine.

### Build succeeds but the executable is 1+ GB

Normal. PyInstaller bundles your entire Python interpreter plus every
imported library. Streamlit and matplotlib are large. There's no easy way
to make it dramatically smaller — this is why the maintainer recommends
the Python install path instead.

### Build hangs at "Processing module hooks" for >30 minutes

Streamlit drags in many transitive deps. On a slow machine this is just
slow, not stuck. If it really has hung, kill with Ctrl+C, delete
`build/work/`, and retry — sometimes the cache gets corrupted.

## Why we don't ship pre-built binaries

Three reasons:

1. **OS coverage.** The maintainer would need to build, test, and re-ship
   on three OSes for every release. Research lab tooling rarely justifies
   that overhead.
2. **Code signing.** Unsigned binaries trigger scary security warnings on
   modern Mac and Windows. Real signing costs money and ongoing renewal.
3. **Trust.** A pre-built binary is opaque — a recipient can't verify what
   it does without trusting the publisher. A clear build script and Python
   source file is auditable. For research data, auditability matters.

If your lab really needs binaries for a study, ask Fernando — but the
honest answer is going to be "use the Python launcher unless you have a
specific reason you can't."

## When to give up on this path

If you've spent more than two hours trying to make the bundle work on a
specific OS, **stop and use the Python install path**. It works reliably,
the install is genuinely 5 minutes once you've done it once, and you don't
have to debug PyInstaller every time the dependencies update.
