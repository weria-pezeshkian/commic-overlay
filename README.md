# COMMIC Overlay

A wizard-style GUI that drives already-installed command-line analysis
tools, starting with [CALM](https://github.com/weria-pezeshkian/Membrane_Shape_Analysis).
Pick inputs step by step, click Run, get a results page with one-click
plots. An "Advanced" window still exposes every real CLI flag for anyone
who wants it.

**This project is an overlay only.** It never installs, bundles, or
vendors CALM (or any other tool it wraps) — it assumes CALM is already
installed in the same Python environment it's run from, and drives it
exactly as a user would from the command line: by invoking the `CALM`
console script as a subprocess, and by reading CALM's own installed
`argparse` parser-builder functions to generate the Advanced form. If CALM
isn't importable and on `PATH` when this app starts, it says so and exits
rather than guessing.

## Install

```console
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

This installs only PySide6 (and `dev` extras if you ask for them). CALM
itself must already be installed in the same environment separately:

```console
pip install git+https://github.com/weria-pezeshkian/Membrane_Shape_Analysis
```

## Run

```console
commic-overlay
```

## Project layout

- `commic_overlay/` — tool-agnostic shell: the main window, top nav bar,
  home page, working-directory page, settings, and generic widgets
  (`widgets/`).
- `commic_overlay/calm/` — everything CALM-specific: the wizard pages that
  speak CALM's own flags and output files (`pages/`), and the bridge code
  that builds/runs CALM CLI invocations and introspects CALM's installed
  argparse parsers for the Advanced window (`calm_bridge/`). A sibling
  tool, if one is ever added, gets its own directory next to `calm/`
  following the same split.

## Development

```console
ruff check commic_overlay/
mypy commic_overlay/ --ignore-missing-imports
pytest
```

The test suite runs against whatever CALM is actually installed in the
current environment (it introspects CALM's real parsers rather than
mocking them), so it needs CALM installed to pass — same requirement as
running the app itself.
