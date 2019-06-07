# lighty-ansible - Automation of SDN and SFC
This repository contains example projects implementing automation of network management,
administration, configuration and orchestration workflows leveraging
Software Defined Networking (SDN) and Service Function Chaining (SFC).<br/>
<br/>
The aim is to create a set of Ansible playbooks and modules which can be re-used for
Infrastructure as Code (IaC) approach to manage virtual and physical networks
(overlay and underlay) connecting bare metal servers, virtual machines and
containers (cloud native) running in core and edge data centers (DCs) together
with orchestration of networking devices (physical or virtual).<br/>
<br/>

## Brief description of example projects

- **tenant_provisioning_with_sfc** - Implements Ansible playbooks and module for provisioning and de-provisioning
tenant's containers, VXLAN tunnel, SF (Service Function) and SFC. Check out blog at https://pantheon.tech/awx-ansible-lightyio/ for more details.
