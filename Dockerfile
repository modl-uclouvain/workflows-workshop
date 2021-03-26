# https://github.com/jupyter/docker-stacks
# https://jupyter-docker-stacks.readthedocs.io/en/latest/index.html
FROM jupyter/scipy-notebook
LABEL maintainer="Gian-Marco Rignanese <gian-marco.rignanese@uclouvain.be>"


# # Fix DL4006
# SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Abinit installation
# ===================
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
    slurmd slurm-client slurmctld \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

ARG abinit_version="9.4.0"
COPY configs/abinit_config.ac9 /opt/abinit-${abinit_version}/build/abinit_config.ac9

RUN wget -k "https://www.abinit.org/sites/default/files/packages/abinit-${abinit_version}.tar.gz" \
 && tar xzf abinit-${abinit_version}.tar.gz \
 && cd abinit-${abinit_version} \
 && cd build \
 && ../configure --with-config-file='abinit_config.ac9'   \
 && make -j4 \
 && make install \
 && rm /opt/abinit-${abinit_version}.tar.gz \
 # && rm -rf /opt/abinit-${abinit_version}
 && fix-permissions "/opt/abinit-${abinit_version}"

USER $NB_UID

# Install Python 3 packages
# =========================

RUN conda install --quiet --yes \
    # 'ase' \
    # 'pymatgen' \
    # 'atomate' \
    # 'matminer' \
    # 'jupyterlab-git' \
    'abipy' \
    'jupyter-server-proxy' \
    'jupyter_contrib_nbextensions' \
    'jupyter_nbextensions_configurator' \
 && pip install --no-cache-dir jupyter-jsmol fireworks \
 && conda clean --all -f -y \
 && fix-permissions "${CONDA_DIR}" \
 && fix-permissions "/home/${NB_USER}"

# Pseudo-dojo
USER root
WORKDIR /opt

RUN git clone --depth 1 https://github.com/abinit/pseudo_dojo.git \
 && cd pseudo_dojo \
 && fix-permissions "/opt/pseudo_dojo"

USER $NB_UID

RUN pip install -e pseudo_dojo

USER $NB_UID
WORKDIR $HOME

