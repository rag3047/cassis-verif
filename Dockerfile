ARG UBUNTU_VERSION=22.04
ARG PRESET=default

FROM ubuntu:${UBUNTU_VERSION} AS default
RUN mkdir /output

FROM ubuntu:16.04 AS cassis
# Here we build dependencies for the CaSSIS FSW such as RTEMS for SPARC LEON3
RUN mkdir /output && echo "cassis" > /output/test.txt

# TODO: RTEMS 4.11 Build container
# FROM ubuntu:22.04 AS builder
# LABEL maintainer="Raphael Gerber <raphael.gerber@students.unibe.ch>"

# ENV DEBIAN_FRONTEND=noninteractive

# WORKDIR /rtems

# RUN apt-get update && apt-get install -y \
#     build-essential g++ gdb unzip pax bison flex texinfo python3-dev \
#     python-is-python3 libpython2-dev libncurses5-dev zlib1g-dev ninja-build \
#     pkg-config curl xz-utils git \
#     && rm -rf /var/lib/apt/lists/*

# RUN mkdir src \
#     && mkdir 4.11 \
#     && cd src \
#     && curl https://ftp.rtems.org/pub/rtems/releases/4.11/4.11.3/rtems-source-builder-4.11.3.tar.xz | tar -xJf - \
#     && mv rtems-source-builder-4.11.3 rsb \
#     && cd rsb/rtems \
#     && ../source-builder/sb-set-builder --prefix=/rtems/4.11 4.11/rtems-sparc


# Select preset based on build arg
FROM ${PRESET} AS preset

FROM ubuntu:${UBUNTU_VERSION}
LABEL maintainer="Raphael Gerber <raphael.gerber@students.unibe.ch>"

# Apparently this needs to be repeated if we want to use it in the COPY command
ARG PRESET

EXPOSE 80

ENV TZ=Europe/Zurich
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV WORKDIR=/cassis-verif
ENV USE_PREBUILT_HINTS=true

WORKDIR ${WORKDIR}

ENV DATA_DIR=${WORKDIR}/data
ENV CBMC_ROOT=${DATA_DIR}/cbmc
ENV PROOF_ROOT=${CBMC_ROOT}/proofs
ENV DOXYGEN_DIR=${WORKDIR}/doxygen
ENV PRESET_DIR=${WORKDIR}/preset

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-jinja2 universal-ctags bash-completion \
    ninja-build gnuplot graphviz git wget doxygen \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/diffblue/cbmc/releases/download/cbmc-5.95.1/ubuntu-20.04-cbmc-5.95.1-Linux.deb -q \
    && wget https://github.com/awslabs/aws-build-accumulator/releases/download/1.29.0/litani-1.29.0.deb -q \
    && apt-get install -y ./*cbmc*.deb ./*litani*.deb \
    && rm *cbmc*.deb *litani*.deb

COPY cbmc-setup-noninteractive.py cbmc-setup-noninteractive.py
COPY doxygen doxygen

# Copy Preset specific files
COPY --from=preset /output/* preset/
COPY presets/${PRESET}/* preset/

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/cassis-verif/data"]

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]