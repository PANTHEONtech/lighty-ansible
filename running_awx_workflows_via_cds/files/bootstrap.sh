#!/bin/bash
#
#  Copyright (c) 2020 PANTHEON.tech s.r.o. All Rights Reserved.
#
#  This program and the accompanying materials are made available under the
#  terms of the Eclipse Public License v1.0 which accompanies this distribution,
#  and is available at https://www.eclipse.org/legal/epl-v10.html


# Check local machine for ability to host the demo
set -euo pipefail

# some constants
runtime_data=runtime_data
venv_name=ansible_venv
docker_data=/var/lib/docker
docker_min=10000
mem_min=$((6 * 1024 * 1024))


function die() {
    if [[ $# -ge 1 ]] ; then
        echo "$@" >&2
    else
        echo "Command failed" >&2
    fi
    exit 1
}

function ansible_virtualenv() {
    echo "Creating a suitable ansible virtual environment"
    # Create working directory
    mkdir $runtime_data || die "Failed to create new $runtime_data directory"

    # create virtualenv

    (
        cd $runtime_data
        python3 -mvenv $venv_name
    ) || die "Failed to create python virtual environment $venv_name"

    (
        source $runtime_data/$venv_name/bin/activate
        pip install wheel
        pip install ansible ansible-tower-cli docker docker-compose
        pypath=$(type -P python)
        opts="ansible_connection=local ansible_python_interpreter=$pypath"
        echo "localhost $opts" >hosts
    ) || die "Failed to install ansible and module requirements"

    echo "Ansible prerequisite environmnent has been bootstrapped"
    echo "Run the following command to make it available in a shell:"
    echo "    source $runtime_data/$venv_name/bin/activate"
}


# Check necessary software is installed
for cmd in python3 docker git make node npm ; do
    type -P $cmd >/dev/null || die "Please install required $cmd package"
done

# Check system resources
[[ $(sed -n '/MemAvailable:/s/[^0-9]//gp' /proc/meminfo) -ge $mem_min ]] ||
die "Please ensure there is at least $mem_min kB available memory"

df_args="--output=avail -BMB"
[[ $(df $df_args $docker_data | sed -n '$s/[^0-9]//gp') -ge $docker_min ]] ||
die "Please ensure drive containing $docker_data has $docker_min MB available"

# Check current user can run docker commands
docker images >/dev/null || die "Please add current user to docker group"

# Check current user is a no-password sudoer
sudo -n true || die "Please make current user no-password sudoer"

(
    type -P ansible-playbook &&
    type -P tower-cli &&
    type -P docker-compose &&
    python3 -c 'import ansible, docker, tower_cli' &&
    echo "Ansible prerequisite environment seems setup, skip virtualenv"
) >/dev/null || ansible_virtualenv
