#!/bin/bash

# Handle special flags if we're root
if [ $(id -u) == 0 ]; then
    su jovyan /etc/init.d/munge start
    su jovyan /etc/init.d/slurmd start
    su jovyan /etc/init.d/slurmctld start
else
    /etc/init.d/munge start
    /etc/init.d/slurmd start
    /etc/init.d/slurmctld start
fi