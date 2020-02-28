# Ansible AWX/Tower and ONAP CDS automation

This project demonstrates the use of ONAP CDS blueprint processor
to drive operation of virtual networking infrastructure through
execution of other - essentially arbitrary - Ansible playbooks hosted
on an Ansible AWX server.

It uses the sibling demo, [DC tenant provisioning and SFC automation][demo],
as an example of the targeted executable playbooks. This set of playbooks,
code and associated configuration are enabling automated setup of AWX, CDS,
and a suitable target topology to configure.

This topology comprises a separate node running the SDN controller based
on [Lighty.io][lighty] with Restconf, OpenFlow and OVSDB plugins,
alongside two nodes running OpenVSwitch that represent a datacenter each.
The workings of demo hosted by this infrastructure is discussed in detail
at [Panthen.tech's][blog] site.

## Playthrough

After having met the prerequisites listed in a section below, one can run
this demo as follows:

0. Login to the shell under the selected user account, change into
   a suitable (new) directory writable by that user.

1. Clone this repository and change to this subdirectory:

        git clone https://pantheon.tech/awx-ansible-lightyio/ --depth 1
        cd awx-ansible-lightyio/running_awx_workflows_via_cds

2. If you do not have ansible and its modules' python prerequisites
   installed, bootstrap them into a virtualenv, then activate it:

        ./files/bootstrap.sh
        source runtime_data/ansible_venv/bin/activate

3. Ensure the required Docker images are available; image names and
   tags may be adjusted to updated or alternative builds.
   Refer to the section on Docker images below for details.

   If keen to do so, review and adjust other variables as well.

4. Download, build and start Ansible AWX server containers:

        ansible-playbook apb_awx_server.yaml -v

5. Build and start both CDS and the target demo topology:

        ansible-playbook apb_docker_topology.yaml -v

6. Setup AWX project, inventory, job and workflow templates:

        ansible-playbook apb_upload_awx.yaml -v

7. Bootstrap CDS starter models and data definitions:

        ansible-playbook apb_bootstrap_cds.yaml -v

8. Setup CBA for the demo topology, enrich and upload to CDS;
   the CBA is built from the files/cba/Lighty\_ROO subdirectory:

        ansible-playbook apb_upload_cds.yaml -v

9. Review the contents of AWX in its UI (default at http://localhost:8052),
   the contents of the CBA main definition file, and [demo description][blog].
   Run through and work with the demo topology.

   Three workflows are created and configured in the CBA:

   - tenant-flows
   - sf-bridge
   - deprovision

   To execute a workflow through CDS, run the execute playbook with its name:

        ansible-playbook apb_execute_cba.yaml -e workflow=tenant-flows -vvv

10. Once done, teardown the CDS and demo topologies, and AWX server completely:

        ansible-playbook apb_docker_topology.yaml -e docker_destroy=true -v
        ansible-playbook apb_awx_server.yaml -e awx_destroy=true -v

    Docker images will not be removed from the local repository;
    use `docker images` and `docker rmi` to manually remove unneeded images.

## Prerequisites

The complete demo runs as a set of Docker containers and can be run
in a suitable Linux machine, even in a VM on a current laptop.

The playbooks build the topology using docker-compose, a lightweight
system for orchestrating sets of related containers.

The system requirements are as follows:

- a machine with a current/updated Linux operating system

- up to 6GB of RAM, 2 or more CPUs, and 10 GB of storage for images
  (the demo requires much less resources than production deployments)

- a user account which is allowed to run docker containers
  (this can be typically achieved by adding the user to the "docker"
  group; if the current user is modified, a re-login may be required;
  the account need not be new - any existing user account is valid)

- same user account which can become a superuser (without password)
  (only required during teardown of the containers, to remove volume data
  which is not owned by the user account running the demo)

- ability to pull git repositories from Github and python packages from PyPI
  
- ability to pull Docker container images from Docker Hub and ONAP
  (use `docker login -u docker -p docker nexus3.onap.org:10001`)

- a current Docker engine installed
  (instructions to do that vary by distribution and are freely available)

- installed distribution packages for bash, python3, git, make, node and npm
  (the latter three are requirements for AWX server setup)

- installed python3 packages for docker, docker-compose and ansible-tower-cli
  (this is optional, an included script can install a virtual environment
  containing these packages, and run the playbooks within it)

## Docker images

As of this writing, the Docker images required are not readily available from
public sources; even the CDS blueprint processor image requires adjustment.

### ONAP CDS Blueprint processor

The image can be pulled using the tag:

    nexus3.onap.org:10001/onap/ccsdk-blueprintsprocessor:0.7.0-STAGING-latest

This image's configuration contains paths where started model and data types
are stored; these are howewer incorrect and need adjustment prior to starting
the container.

Additionally, a java debugger port can be optionally exposed in the application.
Configure a suitable port for `cds_jdb_port` in the `group_vars/all.yaml` file.

To build the modified image, run:

    cd files/docker/cdsd
    docker build -t onap/ccsdk-blueprintsprocessor:0.7.0-PANTHEONTECH-latest .

### OpenVSwitch

The image `globocom1/openvswitch` from docker hub has been found suitable for
demo purposes (other use is neither proposed nor encouraged herein).
It merely requires the iproute2 package, as the built-in BusyBox implementation
lacks support for network namespaces.

To create the network namespaces, the containers must be run in privileged mode.

To build the modified image, run:

    cd files/docker/ovs
    docker build -t pantheontech/openvswitch:latest .

### Lighty.io with Restconf, OpenFlow, OVSDB plugins

There is no public build of this image currently available, so it must be built
manually; the build requires OpenJDK 8 (openjdk 11 can build it too) and maven.
It also requires [ALPN boot from Maven Central][alpn]

An example build of Lighty.io would be as follows:

    # outside this cloned repository, perhaps in the starting directory
    wget https://raw.githubusercontent.com/opendaylight/odlparent/master/settings.xml
    git clone https://github.com/PantheonTechnologies/lighty-core.git \
        --branch 9.3.x --depth 1
    cd lighty-core
    JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/ mvn -s ../settings.xml \
        clean install -DskipTests=true -Dmaven.test.skip=true \
        -Dmaven.javadoc.skip=true -Dadditionalparam=-Xdoclint:none

    cd lighty-examples/lighty-community-restconf-ofp-ovsdb-app
    JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64/ mvn -s ../../../settings.xml \
        clean install -DskipTests=true -Dmaven.test.skip=true \
        -Dmaven.javadoc.skip=true -Dadditionalparam=-Xdoclint:none

Once built, copy over target/lighty-community\*-bin.zip and the ALPN .jar into
the directory files/docker/roo.

To build the modified image, run:

    # back in the root of this project (directory containing this README.md)
    cd files/docker/roo
    docker build -t pantheontech/lighty-roo:latest .


[demo]: ../tenant_provisioning_with_sfc/README.md
[blog]: https://pantheon.tech/awx-ansible-lightyio/
[lighty]: https://lighty.io
[alpn]: https://search.maven.org/artifact/org.mortbay.jetty.alpn/alpn-boot/8.1.13.v20181017/jar
