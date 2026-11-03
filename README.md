# COMMIC Overlay

A wizard-style GUI that drives already-installed command-line analysis
tools. Two tools so far:

- [CALM](https://github.com/weria-pezeshkian/Membrane_Shape_Analysis) —
  membrane curvature/thickness/lipid-composition analysis.
- [TS2CG](https://github.com/weria-pezeshkian/TS2CG-v2.0) — builds
  coarse-grained membrane structures from a triangulated surface or a
  purely analytical shape.

Pick inputs step by step, click Run, get a results page. An "Advanced"
window still exposes the real underlying CLI flags for anyone who wants
them.

**This project is an overlay only.** It never installs, bundles, or
vendors either tool — it assumes whichever one you want is already
installed in the same Python environment it's run from, and drives it
exactly as you would from the command line: by invoking that tool's own
console script (`CALM`, `TS2CG`) as a subprocess, and by reading its
installed argparse parsers (CALM) or real `-h` output (TS2CG's compiled
binaries) to generate the Advanced form. The app itself always opens
regardless of what's installed - each tool's own Home-page button simply
disables itself, with an explanatory tooltip, if that tool isn't
importable/on `PATH` yet.

TS2CG's own lipid library is built from the [Martini 3
Lipidome](https://github.com/Martini-Force-Field-Initiative/M3-Lipid-Parameters),
fetched over plain HTTPS the first time the Select Lipids page is shown
and cached locally - no extra dependency needed for that (stdlib
`urllib`/`tarfile` only).

## Install

```console
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

This installs only PySide6 (and `dev` extras if you ask for them). Each
tool you actually want to drive must already be installed in the same
environment separately:

```console
pip install git+https://github.com/weria-pezeshkian/Membrane_Shape_Analysis   # CALM
pip3 install git+https://github.com/weria-pezeshkian/TS2CG-v2.0               # TS2CG
```

## Run

```console
commic-overlay
```

Started from a terminal, the Working Directory page offers the directory
the command was run in. Started without a terminal (for example from a
desktop launcher), it offers the most recently used working directory, or
your home directory on first use.

## Project layout

- `commic_overlay/` — tool-agnostic shell: the main window, top nav bar,
  home page, working-directory page, settings, generic widgets
  (`widgets/`), and the shared subprocess-running infrastructure
  (`process_runner.py`).
- `commic_overlay/calm/` — everything CALM-specific: the wizard pages that
  speak CALM's own flags and output files (`pages/`), and the bridge code
  that builds/runs CALM CLI invocations and introspects CALM's installed
  argparse parsers for the Advanced window (`calm_bridge/`).
- `commic_overlay/ts2cg/` — everything TS2CG-specific, the same split:
  wizard pages (`pages/`) and the bridge code (`ts2cg_bridge/`) that
  builds/runs TS2CG CLI invocations, fetches/indexes the Martini 3
  lipidome, assembles a run-scoped `.LIB` file, and writes `input.str`.
  A sibling tool, if one is ever added, gets its own directory next to
  these two, following the same split.

## Development

```console
ruff check commic_overlay/
mypy commic_overlay/ --ignore-missing-imports
pytest
```

The test suite covers both tools' own pure logic (argv-building, file
parsing/writing, geometry) without needing either tool actually
installed or any network access. Manually exercising a real run end to
end does need the relevant tool installed (and, for TS2CG, network
access the first time, to fetch the lipidome).
