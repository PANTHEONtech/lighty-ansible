#!/usr/bin/python
#
#  Copyright (c) 2019 PANTHEON.tech s.r.o. All Rights Reserved.
#
#  This program and the accompanying materials are made available under the
#  terms of the Eclipse Public License v1.0 which accompanies this distribution,
#  and is available at https://www.eclipse.org/legal/epl-v10.html
#


"""
This module implements requests to HTTP REST API (RESTCONF)
of lighty.io based SDN controllers with OpenFlow plugin used.
"""

from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
import json
from string import Template

from ast import literal_eval
import pdb

# parameter names
P_CMD = "cmd"
P_CONTROLLER_URL = "controller_url"
P_BRIDGE_NAME = "bridge_name"
P_BRIDGE_ID = "bridge_id"
P_FLOW_ID = "flow_id"
P_IN_PORT = "in_port"
P_OUT_PORT = "out_port"
P_TABLE_ID = "table_id"

# commands
GET_BRIDGE_ID = "get_bridge_id"
SET_PORT_TO_PORT_FWD = "set_port_port_fwd"
DEL_FLOW = "del_flow"


def main():
    """ Parse Ansible module parameters and call respective method. """

    fields = {
        P_CMD: {"default": None, "type": "str"},
        P_CONTROLLER_URL: {"default": "http://localhost:8888", "type": "str"},
        P_BRIDGE_NAME: {"default": None, "type": "str"},
        P_BRIDGE_ID: {"default": None, "type": "str"},
        P_FLOW_ID: {"default": None, "type": "int"},
        P_IN_PORT: {"default": None, "type": "int"},
        P_OUT_PORT: {"default": None, "type": "int"},
        P_TABLE_ID: {"default": 0, "type": "int"}
    }

    module = AnsibleModule(argument_spec=fields)
    # data = literal_eval(data)

    cmd = module.params[P_CMD]
    cmd = cmd.lower()
    controller = module.params[P_CONTROLLER_URL]
    br_name = module.params[P_BRIDGE_NAME]
    br_id = module.params[P_BRIDGE_ID]
    flow_id = module.params[P_FLOW_ID]
    in_port = module.params[P_IN_PORT]
    out_port = module.params[P_OUT_PORT]
    table_id = module.params[P_TABLE_ID]

    if None is cmd:
        raise AttributeError("Mandatory attributes not set")

    controller = controller[0:-1] if controller[-1] == '/' else controller

    # bridge ID must be of format openflow:<id>
    if None is not br_id and \
            (br_id.split(':')[0] != "openflow" or int(br_id.split(':')[1]) < 0):
        raise AttributeError("Invalid bridge ID: {}".format(br_id))

    if GET_BRIDGE_ID == cmd:
        if None is br_name:
            raise_missing_params(cmd)
        ret = get_bridge_id(controller, br_name)

        if not ret:
            module.fail_json(msg="Bridge ID not found for bridge: {}".format(br_name))
        module.exit_json(changed=False, br_id=ret)

    elif SET_PORT_TO_PORT_FWD == cmd:
        if None is br_id or None is flow_id or None is in_port or None is out_port:
            raise_missing_params(cmd)
        ret = set_port_port_fwd(controller, br_id, flow_id, in_port, out_port, table_id)

        if not ret:
            module.exit_json(changed=True)
        module.fail_json(msg="Failed to set port to port forwarding flow")

    elif DEL_FLOW == cmd:
        if None is br_id or None is flow_id:
            raise_missing_params(cmd)
        ret = delete_flow(controller, br_id, flow_id, table_id)

        if not ret:
            module.exit_json(changed=True)
        module.fail_json(msg="Failed to delete flow of bridge: {}, flow_id: {}, table_id: {}".format(
            br_id, flow_id, table_id))

    else:
        raise AttributeError("Unknown command specified: {}".format(cmd))


def raise_missing_params(cmd):
    raise AttributeError("Missing mandatory parameters of command: {}".format(cmd))


def get_bridge_id(controller, bridge_name):
    """ Retrieves ID of the OpenFlow bridge assigned by controller when
    the bridge has beeing connected to the controller. The ID is mapped to
    the name of the bridge assigned during creation of the bridge.

    Args:
        controller (str): URL to SDN controller's RESTCONF server
        bridge_name (str): The name of the OpenFlow bridge

    Returns:
        str: The OpenFlow brige's ID assigned by SDN controller
    """

    url = "{}/restconf/data/opendaylight-inventory:nodes".format(controller)
    headers = {'Accept': 'application/json'}

    rsp = open_url(url, method="GET", headers=headers)
    data = json.loads(rsp.read())

    for node in data['opendaylight-inventory:nodes']['node']:
        id = node['id']
        if "node-connector" in node:
            for connector in node["node-connector"]:
                if connector['id'] == id+':LOCAL' and connector["flow-node-inventory:name"] == bridge_name:
                    return id
    return None


def _create_url_to_flow(controller, br_id, table_id, flow_id):
    br_id_escaped = (br_id.split(":")[0] + "%3a" + br_id.split(":")[1])
    return "{}/restconf/data/opendaylight-inventory:nodes/node={}/table={}/flow={}".format(
        controller, br_id_escaped, table_id, flow_id)


def set_port_port_fwd(controller, br_id, flow_id, in_port, out_port, table_id=0):
    """ Configures OpenFlow flows which forwards all packets received at one
    port (in_port) to another port (out_port).

    Args:
        controller (str): URL to SDN controller's RESTCONF server
        br_id (str): The unique ID of the bridge assigned by SDN controller
        flow_id (int): The identifier of the flow in the specific table
        in_port (int): The input port of the flow
        out_port (int): The output port of the flow
        table_id (int): Optional identifier of the flow table

    Returns:
        Nothing is returned in cases of success
    """
    url = _create_url_to_flow(controller, br_id, table_id, flow_id)

    payload = Template("""
        {
            "flow": [
                {
                    "table_id": "${table_id}",
                    "id": "${flow_id}",
                    "priority": "10",
                    "match": {
                        "in-port": "${br_id}:${in_port}"
                    },
                    "instructions": {
                        "instruction": [
                            {
                                "order": 0,
                                "apply-actions": {
                                    "action": [
                                        {
                                            "order": 0,
                                            "output-action": {
                                                "output-node-connector": "${out_port}",
                                                "max-length": "65535"
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
             ]
        }
    """).substitute(table_id=table_id,
                    flow_id=flow_id,
                    br_id=br_id,
                    in_port=in_port,
                    out_port=out_port)

    headers = {'Content-Type': 'application/json'}

    rsp = open_url(url, method="PUT", headers=headers, data=payload)
    return rsp.read()


def delete_flow(controller, br_id, flow_id, table_id=0):
    """ Deletes specific flow from the specific table.

    Args:
        controller (str): URL to SDN controller's RESTCONF server
        br_id (str): The unique ID of the bridge assigned by SDN controller
        flow_id (int): The identifier of the flow in the specific table
        table_id (int): Optional identifier of the flow table

    Returns:
        Nothing is returned in cases of success
    """

    url = _create_url_to_flow(controller, br_id, table_id, flow_id)
    rsp = open_url(url, method="DELETE")
    return rsp.read()


if __name__ == '__main__':
    main()
