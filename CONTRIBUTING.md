# Contributing to CAVE FRF

Thanks for your interest in improving this pipeline. The maintainer is
Fernando Vanderlinde dos Santos (neurokreative@gmail.com).

## Reporting bugs or suggesting features

Open an [issue](https://github.com/YOUR_USERNAME/cave-frf/issues). For bugs,
please include:

- What you tried to do
- What happened (paste the exact error message if any)
- Your operating system and Python version (`python --version`)
- A small example of the data layout you used (folder names, one filename — **never paste actual subject data**)

## Proposing code changes

This repo uses the standard fork-and-pull-request workflow. You cannot push
directly to `main`; changes must come through a pull request that the
maintainer reviews.

1. **Fork the repo** on GitHub (the **Fork** button at the top right).
2. **Clone your fork** locally.
3. **Install the pre-commit hook** so you can't accidentally commit subject
   data:
   ```bash
   bash scripts/install_hooks.sh    # Mac/Linux
   scripts\install_hooks.bat        # Windows
   ```
4. **Make your changes on a branch** named after the change
   (`fix-walking-coherence`, `add-spectrogram-plot`, etc.).
5. **Run the tests:** `python tests/test_basic.py` — all tests must pass.
6. If you added new functionality, **add a test for it** in `tests/test_basic.py`.
7. **Commit and push** your branch to your fork.
8. **Open a pull request** against this repo's `main` branch.

The maintainer will review and either merge, request changes, or explain
why a change isn't a fit. Reviews typically happen within a week.

## What kinds of changes are likely to be accepted

- Bug fixes
- New plot styles or analysis options that don't change the default behavior
- Better error messages and validation of user input
- Cross-platform fixes (Windows path issues, etc.)
- Test coverage improvements
- Documentation clarifications

## What kinds of changes will likely be discussed first

If you want to make these changes, please open an **issue first** so we can
align before you write code:

- Methodology changes (e.g., different FRF estimator, different windowing)
- Adding a new dependency
- Changes to the output CSV schema (would break downstream analysis)
- Anything that changes the meaning of the gain/phase/coherence numbers

## Subject data — non-negotiable

**Never commit subject data files to this repository.** Subject COP files,
stimulus logs, and intermediate results that contain subject IDs are
biomedical research data. They belong outside the repo entirely.

The pre-commit hook (installed via `scripts/install_hooks.sh`) will block
commits that contain files matching the data patterns. If you ever see this
hook fire, **do not bypass it with `--no-verify`** unless you've manually
confirmed the file is not subject data.

Test fixtures are allowed under `tests/fixtures/` — but they should be
synthetic data (generated programmatically), never anonymized real data.

## Code style

- Match the existing style in the file you're editing (4-space indents,
  `snake_case` for functions and variables).
- Type hints are nice but not required.
- Docstrings on every public function — describe parameters, return value,
  and any non-obvious behavior.

## Maintainer notes

The maintainer reserves the right to:

- Decline contributions that don't fit the project's scope
- Request revisions to PRs before merging
- Refactor or rewrite contributed code as needed for consistency

Thanks for contributing.
