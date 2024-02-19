ARG UBUNTU_VERSION=22.04
ARG PRESET=default

#--------------------------------------
# Default Preset
#--------------------------------------

FROM ubuntu:${UBUNTU_VERSION} AS default
RUN mkdir /output

#--------------------------------------
# SUCHAI Preset
#--------------------------------------

FROM ubuntu:${UBUNTU_VERSION} AS suchai
RUN mkdir /output

#--------------------------------------
# Cassis Preset
#--------------------------------------

FROM ubuntu:16.04 AS cassis

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /rtems

RUN apt-get update && apt-get install -y \
    binutils gcc g++ gdb unzip git python python2.7-dev wget bzip2 \
    bison flex make xz-utils texinfo libz-dev libncurses5-dev \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir src \
    && cd src \
    && wget https://git.rtems.org/rtems-source-builder/snapshot/rtems-source-builder-4.11.3.tar.bz2 -q \
    && tar -xjf rtems-source-builder-4.11.3.tar.bz2 \
    && rm rtems-source-builder-4.11.3.tar.bz2 \
    && mv rtems-source-builder-4.11.3 rsb \
    && mkdir -p rsb/rtems/sources \
    # manually download expat because download url is no longer valid
    && cd rsb/rtems/sources \
    && wget https://sourceforge.net/projects/expat/files/expat/2.1.0/expat-2.1.0-RENAMED-VULNERABLE-PLEASE-USE-2.3.0-INSTEAD.tar.gz -q \
    && mv expat-2.1.0-RENAMED-VULNERABLE-PLEASE-USE-2.3.0-INSTEAD.tar.gz expat-2.1.0.tar.gz \
    && cd .. \
    && mkdir -p /output/rtems \
    && ../source-builder/sb-set-builder --prefix=/output/rtems --with-rtems 4.11/rtems-sparc

#--------------------------------------
# Workbench
#--------------------------------------

# Select preset based on build arg
FROM ${PRESET} AS preset

FROM ubuntu:${UBUNTU_VERSION}
LABEL maintainer="Raphael Gerber <raphael.gerber@students.unibe.ch>"

# Apparently this needs to be repeated if we want to use it in the COPY command
ARG PRESET

EXPOSE 80

# The following ENV vars can be modified using a .env file
ENV APP_PATH=""
ENV DEBUG=false
ENV LOG_LEVEL=info
ENV USE_PREBUILT_HINTS=true
ENV TZ=Europe/Zurich
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# The following ENV vars should not be modified (might break the container)
# Disable interactive frontend
# Note: this is required for certain package installations
ENV DEBIAN_FRONTEND=noninteractive
# Specify the working directory
# Note: This path is hardcoded in certain places
ENV WORKDIR=/cassis-verif
# Allows streaming stdout of python as it is generated
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=${WORKDIR}/data
ENV CBMC_ROOT=${DATA_DIR}/cbmc
ENV PROOF_ROOT=${CBMC_ROOT}/proofs
ENV DOXYGEN_DIR=${WORKDIR}/doxygen
ENV PRESET_DIR=${WORKDIR}/preset

WORKDIR ${WORKDIR}

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-jinja2 universal-ctags bash-completion \
    ninja-build gnuplot graphviz git wget doxygen \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/diffblue/cbmc/releases/download/cbmc-5.95.1/ubuntu-20.04-cbmc-5.95.1-Linux.deb -q \
    && wget https://github.com/awslabs/aws-build-accumulator/releases/download/1.29.0/litani-1.29.0.deb -q \
    && apt-get install -y ./*cbmc*.deb ./*litani*.deb \
    && rm *cbmc*.deb *litani*.deb

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/cbmc-setup-noninteractive.py cbmc-setup-noninteractive.py
COPY doxygen doxygen

# Copy Preset specific files
COPY --from=preset /output/ preset/
COPY presets/${PRESET}/ preset/

COPY app app

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/cassis-verif/data"]

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]