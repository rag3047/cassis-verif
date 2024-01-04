#! /bin/bash
set -e

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

if [[ -f "$PRESET_DIR/src.tgz" ]]; then
    echo "Entrypoint: Extracting preset sources"
    tar --extract --skip-old-files --file "$PRESET_DIR/src.tgz" --directory=data
fi

if [[ -f "$PRESET_DIR/hints.tgz" ]]; then
    echo "Entrypoint: Extracting preset hints"
    mkdir hints
    tar --extract --skip-old-files --file "$PRESET_DIR/hints.tgz" --directory=hints
fi

if [[ ! -f "sdd.pdf" ]]; then
    echo "Entrypoint: Copying SDD"
    mv "$PRESET_DIR/sdd.pdf" .
fi

# if [[ -d "$PRESET_DIR/includes" ]]; then
#     # TODO fix this
#     echo "Entrypoint: Copying preset includes"
#     cp -r "$PRESET_DIR/includes"/* "$CBMC_ROOT/includes"
# fi

exec "$@"