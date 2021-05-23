# https://github.com/jupyter/docker-stacks
# https://jupyter-docker-stacks.readthedocs.io/en/latest/index.html

FROM jupyter/scipy-notebook:4d9c9bd9ced0 AS builder

# Abinit compilation
# ==================
# # 1. compiler: gfortran
# # 2. MPI libraries - choice for Open MPI: mpi-default-dev libopenmpi-dev
# # 3. math libraries - choice for lapack and blas: liblapack-dev libblas-dev
# # 4. mandatory libraries:libhdf5-dev libnetcdf-dev libnetcdff-dev libpnetcdf-dev libxc-dev libfftw3-dev libxml2-dev

USER root

RUN apt-get update \
 && apt install -y --no-install-recommends \
    gfortran \
    mpi-default-dev libopenmpi-dev \
    liblapack-dev libblas-dev \
    libhdf5-dev libnetcdf-dev libnetcdff-dev libpnetcdf-dev libxc-dev \
    libfftw3-dev libxml2-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

ARG abinit_version="9.4.0"
COPY configs/abinit/abinit_config.ac9 /tmp/abinit-${abinit_version}/build/abinit_config.ac9

RUN wget -k "https://www.abinit.org/sites/default/files/packages/abinit-${abinit_version}.tar.gz" \
 && tar xzf abinit-${abinit_version}.tar.gz \
 && cd abinit-${abinit_version} \
 && cd build \
 && ../configure --with-config-file='abinit_config.ac9'  --prefix=/opt/abinit \
 && make -j4 \
 && make install


FROM jupyter/scipy-notebook
LABEL maintainer="Gian-Marco Rignanese <gian-marco.rignanese@uclouvain.be>"


# Setup slurm
# ===========

USER root

RUN apt-get update \
 && apt install -y --no-install-recommends \
    slurmd slurm-client slurmctld \
 && rm -rf /var/lib/apt/lists/*

COPY configs/slrum/slurm.conf /etc/slurm-llnl/slurm.conf
COPY configs/slurm/start_slurm.sh  /usr/local/bin/before-notebook.d/

# https://github.com/yuwata/slurm-fedora/blob/master/slurm-setuser.in
RUN mkdir -p /run/munge \
 && chown -R jovyan /run/munge /etc/munge /var/lib/munge /var/log/munge \
 && mkdir -p /var/run/slurm-llnl \
 && chown -R jovyan /var/run/slurm-llnl /var/lib/slurm-llnl /var/log/slurm-llnl

USER $NB_UID


# Abinit installation
# ===================
# - MPI libraries - choice for Open MPI: mpi-default-bin openmpi-bin libopenmpi3
# - math libraries - choice for lapack and blas: liblapack3 libblas3
# - mandatory libraries: libhdf5-103 libnetcdf15 libnetcdff7 libpnetcdf0d libxc5 libfftw3-bin libxml2

USER root

RUN apt-get update \
 && apt install -y --no-install-recommends \
    mpi-default-bin openmpi-bin libopenmpi3 \
    liblapack3 libblas3 \
    libhdf5-103 libnetcdf15 libnetcdff7 libpnetcdf0d libxc5 \
    libfftw3-bin libxml2 \
 && rm -rf /var/lib/apt/lists/*

USER $NB_UID

COPY --chown=$NB_UID:$NB_GID --from=builder /opt/abinit /opt/abinit
ENV PATH=/opt/abinit/bin:$PATH


# Install Python 3 packages
# =========================
# Depenecies:
# - fireworks: flask-paginate gunicorn pymongo
# - pseudo_dojo: periodic-table-plotter atomicfile

RUN conda install --quiet --yes \
    'abipy' \
    'jupyter-server-proxy' \
    'flask-paginate' 'gunicorn' 'pymongo' \
    'periodic-table-plotter' 'atomicfile' \
 && pip install --no-cache-dir jupyter-jsmol \
 && pip install --no-cache-dir git+https://github.com/modl-uclouvain/fireworks.git \
 && pip install --no-cache-dir jupyter-fireworks-proxy \
 && pip install --no-cache-dir git+https://github.com/gpetretto/abiflows.git@develop \
 && conda clean --all -f -y \
 && fix-permissions "${CONDA_DIR}" \
 && fix-permissions "/home/${NB_USER}"

# Install a "lightweight" version of Pseudo-dojo
COPY --chown=$NB_UID:$NB_GID pseudo_dojo /opt/pseudo_dojo
WORKDIR /opt/pseudo_dojo
RUN pip install -e .

# Setup home folder 
# =================

WORKDIR $HOME

COPY --chown=$NB_UID:$NB_GID configs/abipy .abinit/abipy
COPY --chown=$NB_UID:$NB_GID configs/fireworks .fireworks

COPY --chown=$NB_UID:$NB_GID tutorials tutorials
