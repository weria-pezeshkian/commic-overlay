"""Hand-built field specs for TS2CG's three compiled C++ tools (PLM, PCG, SOL).

Unlike CALM's argparse-based commands, these are plain C++ binaries with
their own ad hoc `-flag value` parsing (`cpp/MembraneBuilder/Argument.cpp`)
- there is no `argparse.ArgumentParser` to introspect, so each tool's own
real `-h` output (verified directly against the installed binaries, not
just the README's own tables, which omit a few flags these binaries
actually have - `-b_dist`/`-less` on PLM; `-skip_lipids`/`-Rcutoff`/`-keep`/
`-less` on PCG) is hand-encoded here instead. The five Python tools
(`DOP`/`DAI`/`INU`/`VIS`/`libmaker`) build their own `argparse` parser
inline inside their entry function, with no separate factory to call either
- `point_placement.py` and `dop_bridge.py` build `INU`'s and `DOP`'s argv
directly, `dai_bridge.py` calls DAI's underlying function in-process, and
`libmaker`'s flags are internal to `libmaker_bridge.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FieldSpec:
    """One TS2CG flag's shape, as the Advanced window's form generator needs it.

    `kind` is one of "bool" (presence-only - every TS2CG C++ tool's own
    boolean flags work this way, never a `--no-x` form), "text", "int",
    "float", "floats3" (three space-separated floats, e.g.
    `-rescalefactor rx ry rz`), "ints2" (two space-separated ints, e.g.
    `-ion pos neg`), or "choice" (a fixed set of string values TS2CG itself
    doesn't validate but only ever documents one of).
    """

    dest: str
    flag: str
    kind: str
    help: str
    default: Any = None
    choices: list[str] | None = None


# PLM (Pointillism) - verified against `TS2CG PLM -h`.
PLM_FIELDS: list[FieldSpec] = [
    FieldSpec("TSfile", "-TSfile", "text", "TS file name (.q/.tsi/.dat)", default="TS.tsi"),
    FieldSpec("o", "-o", "text", "name of the output folder", default="point"),
    FieldSpec("rescalefactor", "-rescalefactor", "floats3", "rescaling factor", default=(1.0, 1.0, 1.0)),
    FieldSpec("bilayerThickness", "-bilayerThickness", "float", "bilayer thickness", default=3.8),
    FieldSpec("monolayer", "-monolayer", "int", "generate a monolayer instead (1/-1) rather than 0", default=0),
    FieldSpec("r", "-r", "text", "function (PLM/in_out/check/add_pbc)", default="PLM"),
    FieldSpec("smooth", "-smooth", "bool", "might be necessary for rough surfaces", default=False),
    FieldSpec("resizebox", "-resizebox", "bool", "find a better box for the system", default=False),
    FieldSpec("b_dist", "-b_dist", "float", "distance from the box edge, if -resizebox is used", default=4.0),
    FieldSpec("Mashno", "-Mashno", "int", "number of Mosaicing passes (points grow as 4^Mashno)", default=1),
    FieldSpec("AlgType", "-AlgType", "choice", "Mosaicing algorithm type", default="Type1", choices=["Type1", "Type2"]),
    FieldSpec("less", "-less", "bool", "print less output", default=False),
]

# PCG (Membrane Builder) - verified against `TS2CG PCG -h`.
PCG_FIELDS: list[FieldSpec] = [
    FieldSpec("dts", "-dts", "text", "DTS/point folder built by PLM or PCG -WPointDir", default="point"),
    FieldSpec("str", "-str", "text", "input.str file", default="input.str"),
    FieldSpec("defout", "-defout", "text", "output files prefix", default="output"),
    FieldSpec("LLIB", "-LLIB", "text", "CG lipid library (.LIB) file", default=None),
    FieldSpec("function", "-function", "choice", "backmap or analytical_shape", default="backmap",
               choices=["backmap", "analytical_shape"]),
    FieldSpec("WPointDir", "-WPointDir", "bool", "only write the point folder, no full structure", default=False),
    FieldSpec("Bondlength", "-Bondlength", "float", "initial bond guess", default=0.1),
    FieldSpec("renorm", "-renorm", "bool", "renormalize the lipid molar ratio", default=False),
    FieldSpec("iter", "-iter", "float", "point selections = iter * number of points", default=4.0),
    FieldSpec("incdirtype", "-incdirtype", "choice", "protein direction data type", default="Global",
               choices=["Global", "Local"]),
    FieldSpec("Wall", "-Wall", "bool", "create a wall around the membrane", default=False),
    FieldSpec("WallBName", "-WallBName", "text", "name of the wall beads", default="WL"),
    FieldSpec("skip_lipids", "-skip_lipids", "bool", "skip the lipid placement step", default=False),
    FieldSpec("Rcutoff", "-Rcutoff", "float", "cutoff distance between proteins and lipids", default=0.5),
    FieldSpec("keep", "-keep", "bool", "keep points close to proteins instead of removing them", default=False),
    FieldSpec("less", "-less", "bool", "print less output", default=False),
]

# SOL (Solvate) - verified against `TS2CG SOL -h`.
SOL_FIELDS: list[FieldSpec] = [
    FieldSpec("in", "-in", "text", "name of the file to be solvated", default="input.gro"),
    FieldSpec("o", "-o", "text", "output file name", default="output.gro"),
    FieldSpec("ion", "-ion", "ints2", "number of positive/negative ions to add", default=(0, 0)),
    FieldSpec("db", "-db", "float", "distance between each copy when propagating the water box", default=0.05),
    FieldSpec("Rcutoff", "-Rcutoff", "float", "cutoff distance", default=0.4),
    FieldSpec("tem", "-tem", "text", "template file for solvation", default="W.gro"),
    FieldSpec("nname", "-nname", "text", "name of the negative ions", default="CL"),
    FieldSpec("pname", "-pname", "text", "name of the positive ions", default="NA"),
    FieldSpec("seed", "-seed", "int", "seed for ion placement", default=9474),
    FieldSpec("unsize", "-unsize", "float", "size of the unit cells for overlap checking", default=2.0),
]


def build_argv(module: str, specs: list[FieldSpec], values: dict[str, object]) -> list[str]:
    """TS2CG's own argv for one module call, from its field specs and current values.

    An unset/empty optional field is omitted entirely, same convention as
    CALM's own `build_argv` (`calm_bridge/runner.py`) - never passed as
    `-flag ""`. `floats3`/`ints2` values are 3- or 2-tuples, written as
    three/two separate argv tokens after the flag (TS2CG's own C++ parser
    reads them positionally, not as one combined string).
    """
    argv = ["TS2CG", module]
    for spec in specs:
        value = values.get(spec.dest)
        if spec.kind == "bool":
            if value:
                argv.append(spec.flag)
        elif spec.kind == "floats3":
            if value is not None:
                argv.append(spec.flag)
                argv.extend(str(float(v)) for v in value)
        elif spec.kind == "ints2":
            if value is not None:
                argv.append(spec.flag)
                argv.extend(str(int(v)) for v in value)
        else:
            if value is not None and str(value) != "":
                argv.append(spec.flag)
                argv.append(str(value))
    return argv
