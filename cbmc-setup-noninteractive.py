# -----------------------------------------------------------------------------------------------------
# Notice: This file is a modified version of the original cbmc-starter-kit setup.py
# See:    https://github.com/model-checking/cbmc-starter-kit/blob/master/src/cbmc_starter_kit/setup.py
# -----------------------------------------------------------------------------------------------------

import os
import sys
import shutil
import logging

from pathlib import Path

from cbmc_starter_kit import arguments
from cbmc_starter_kit import repository
from cbmc_starter_kit import update
from cbmc_starter_kit import util
from cbmc_starter_kit.setup import (
    litani_definition,
    project_name_definition,
    srcdir_definition,
)

INCLUDES_TEXT = "INCLUDES += -I {}"
DEFINES_TEXT = "DEFINES += -D {}"


def includes_definition(includes: list[str]) -> str:
    return os.linesep.join(INCLUDES_TEXT.format(incl) for incl in includes)


def defines_definition(defines: list[str]) -> str:
    return os.linesep.join(DEFINES_TEXT.format(defn) for defn in defines)


def parse_arguments():
    desc = "Set up CBMC proof infrastructure for a repository."
    options = [
        {
            "flag": "--project-name",
            "default": "cassis-verif",
        }
    ]
    args = arguments.create_parser(options=options, description=desc).parse_args()
    arguments.configure_logging(args)
    return args


def cbmc_starter_kit_setup_noninteractive():
    """Set up the CBMC proof infrastructure."""

    args = parse_arguments()

    # Gather project-specific definitions
    source_root = repository.repository_root()
    if shutil.which("litani"):
        litani = Path("litani")
    elif repository.litani_root() is not None:
        litani = repository.litani_root() / "litani"
    else:
        logging.error(
            "Could not find litani root. See installation instructions at https://github.com/awslabs/aws-build-accumulator/releases/latest."
        )
        raise FileNotFoundError("litani")

    project_name = args.project_name

    # Copy cbmc infrastructure into cbmc directory
    cbmc_root = Path.cwd()
    shutil.copytree(
        util.package_repository_template_root(), cbmc_root, dirs_exist_ok=True
    )
    shutil.rmtree(cbmc_root / util.NEGATIVE_TESTS, ignore_errors=True)
    shutil.rmtree(cbmc_root / util.PROOF_DIR / "__pycache__", ignore_errors=True)

    # Overwrite Makefile.common and run-cbmc-proofs.py with versioned copies
    # Quiet warnings about overwriting files
    update.update(cbmc_root, quiet=True)

    # Write project-specific definitions to cbmc/proofs/Makefile-template-defines
    proof_root = cbmc_root / util.PROOF_DIR
    makefile = proof_root / util.TEMPLATE_DEFINES
    with open(makefile, "w", encoding="utf-8") as mkfile:
        print(srcdir_definition(source_root, proof_root), file=mkfile)
        print(litani_definition(litani, proof_root), file=mkfile)
        print(project_name_definition(project_name), file=mkfile)

    # TODO: Make this configurable (or add support for presets (RTEMS, other RTOS etc.))
    includes = [
        "/cassis-verif/data/src/include",
        "/cassis-verif/includes/include",
        "/cassis-verif/includes/leon3/lib/include",
        "/cassis-verif/includes/leon3/lib/include/grlib",
        "/cassis-verif/includes/7.5.0/include",
        "/cassis-verif/includes/sparc-rtems4.11/leon3/lib/include",
    ]

    defines = ["__rtems__"]

    # Write project-specific definitions to cbmc/proofs/Makefile-project-defines
    makefile = proof_root / util.PROJECT_DEFINES
    with open(makefile, "a", encoding="utf-8") as mkfile:
        print(includes_definition(includes), file=mkfile, end=os.linesep * 2)
        print(defines_definition(defines), file=mkfile, end=os.linesep * 2)
        print("ENABLE_MEMORY_PROFILING = TRUE", file=mkfile)
        print(
            "MEMORY_PROFILING = --profile-memory --profile-memory-interval 1",
            file=mkfile,
            end=os.linesep * 2,
        )
        print(
            "CBMCFLAGS += --big-endian  --arch sparc", file=mkfile, end=os.linesep * 2
        )


if __name__ == "__main__":
    sys.exit(cbmc_starter_kit_setup_noninteractive())
