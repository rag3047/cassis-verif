#! /bin/bash
set -e

export DATA_DIR="$PWD/data"
export CBMC_ROOT="$DATA_DIR/cbmc"
export PROOF_ROOT="$CBMC_ROOT/proofs"
export SRC_DIR="$DATA_DIR/src"
export DOXYGEN_DIR="$PWD/doxygen/html"

if [[ ! -d "$DATA_DIR/.git" ]]; then
    echo "Entrypoint: Initializing empty git repository"
    git init -q $DATA_DIR
    touch "$DATA_DIR/.git/.git-credentials"
fi

# Make sure git credentials file is persistet across containers
echo "Entrypoint: Linking git credentials file"
ln -sf $DATA_DIR/.git/.git-credentials ~/.git-credentials

if [[ ! -d $CBMC_ROOT ]]; then
    echo "Entrypoint: Initializing cbmc project 'cassis-verif'"

    mkdir -p $CBMC_ROOT && cd $CBMC_ROOT
    python3 /cassis-verif/cbmc-setup-noninteractive.py --project-name cassis-verif
    cd ../..
fi

# DEV: extract C sources
if [[ -d $SRC_DIR ]]; then
    echo "Entrypoint: Extracting C sources"
    rm -rf $SRC_DIR
fi

tar -xf /cassis-verif/src.tar.gz -C data
# END DEV

exec "$@"