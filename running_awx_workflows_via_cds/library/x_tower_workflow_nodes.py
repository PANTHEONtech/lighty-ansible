#!/usr/bin/env python3
#
#  Copyright (c) 2020 PANTHEON.tech s.r.o. All Rights Reserved.
#
#  This program and the accompanying materials are made available under the
#  terms of the Eclipse Public License v1.0 which accompanies this distribution,
#  and is available at https://www.eclipse.org/legal/epl-v10.html
#


"""
This module implements creation of Ansible AWX/Tower workflow node chains.
Only creates on_success-chains of initally empty workflow templates.
"""

import base64
import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


# parameter names
P_ORG = "organization"
P_TOWER_HOST = "tower_host"
P_USERNAME = "tower_username"
P_PASSWORD = "tower_password"
P_VERIFY_SSL = "tower_verify_ssl"
P_TIMEOUT = "timeout"
P_JOB_TEMPLATES = "job_templates"
P_WORKFLOW_TEMPLATES = "workflow_templates"
P_CHAINS = "chains"


def main():
    """ Parse Ansible module parameters and call respective method. """

    fields = {
        P_TOWER_HOST: {"default": "awxweb", "type": "str"},
        P_USERNAME: {"default": "admin", "type": "str"},
        P_PASSWORD: {"default": "password", "type": "str", "no_log": True},
        P_VERIFY_SSL: {"default": True, "type": "bool"},
        P_TIMEOUT: {"default": 60, "type": "int"},
        P_ORG: {"default": "", "type": "str"},
        P_JOB_TEMPLATES: {"default": None, "type": "list"},
        P_WORKFLOW_TEMPLATES: {"default": None, "type": "list"},
        P_CHAINS: {"default": None, "type": "dict"},
    }

    module = AnsibleModule(argument_spec=fields, supports_check_mode=True)

    jobs = {item['job_template']: item['id']
            for item in module.params[P_JOB_TEMPLATES]}
    workflows = {item['workflow_template']: item['id']
                 for item in module.params[P_WORKFLOW_TEMPLATES]}

    chains = module.params[P_CHAINS]
    nodes = []

    result = dict(
        changed=False,
        original_message='',
        msg='',
        answer=nodes,
    )

    if not jobs:
        result['msg'] = 'Missing required parameter jobs'
        module.fail_json(**result)
    if not workflows:
        result['msg'] = 'Missing required parameter workflows'
        module.fail_json(**result)
    if not chains:
        result['msg'] = 'Missing required parameter chains'
        module.fail_json(**result)


    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic {credentials}'.format(
            credentials=base64.b64encode(
                '{username}:{password}'.format(
                    username=module.params[P_USERNAME],
                    password=module.params[P_PASSWORD])
                .encode()).decode())

    }

    for workflow in chains:
        if workflow not in workflows:
            result['msg'] = 'Undefined {workflow}'.format(workflow=workflow)
            module.fail_json(**result)

        for job in chains[workflow]:
            if job not in jobs:
                result['msg'] = 'Undefined {job} for {workflow}'.format(
                    job=job, workflow=workflow)
                module.fail_json(**result)

    success = True
    for workflow in chains:
        workflow_id = workflows.get(workflow)
        api_url = API_JOB_NODES.format(workflow_id=workflow_id)
        if nodes_exist(module, api_url, headers, nodes):
            continue
        for job in chains[workflow]:
            content = {
                'job_type': 'run',
                'unified_job_template': jobs[job],
            }
            if not node_create(module, api_url, headers, content, nodes):
                success = False
                result['msg'] = 'Failed to create nodes for {workflow}'.format(
                    workflow=workflow)
                break
            result['changed'] = True
            api_url = API_ADD_NODES.format(node_id=nodes[-1]['id'])
        else:
            # workflow done
            continue
        # workflow failed
        break
    else:
        result['msg'] = 'All workflow template chains were created'

    if success:
        module.exit_json(**result)
    else:
        module.fail_json(**result)


class FetchResponse(dict):
    def __init__(self, fetch_result):
        super(FetchResponse, self).__init__(fetch_result[1])
        self.status = self['status']
        self.data = (self.get('body', '')
                     if fetch_result[0] is None
                     else fetch_result[0].read())
        self.answer = self.data
        if self.status == 204 or not self.data:
            return

        try:
            self.answer = json.loads(self.data)
        except ValueError:
            pass


def nodes_exist(module, api_url, headers, nodes):
    response = FetchResponse(fetch_url(
        module=module, url=module.params[P_TOWER_HOST] + api_url,
        headers=headers, timeout=module.params[P_TIMEOUT]))
    if (200 <= response.status < 300
            and isinstance(response.answer, dict)
            and response.answer['count']):
        # only the head of a chain may be added
        nodes.extend(response.answer['results'])
        return True
    return False


def node_create(module, api_url, headers, content, nodes):
    headers = dict(headers)
    headers['Content-Type'] = 'application/json'
    payload = json.dumps(content)
    if module.check_mode:
        payload['id'] = len(nodes) + 1
        nodes.append(payload)
        return True

    response = FetchResponse(fetch_url(
        module=module, url=module.params[P_TOWER_HOST] + api_url, data=payload,
        headers=headers, method='POST', timeout=module.params[P_TIMEOUT]))

    if 200 <= response.status < 300 and response.answer:
        node = response.answer
        nodes.append(node)
        return True

    nodes.append({
        "api_url": api_url,
        "headers": headers,
        "content": content,
        "status": response.status,
        "answer": response.data,
    })
    return False


API_ADD_NODES = '/api/v2/workflow_job_template_nodes/{node_id}/success_nodes/'
API_JOB_NODES = '/api/v2/workflow_job_templates/{workflow_id}/workflow_nodes/'


if __name__ == '__main__':
    main()
