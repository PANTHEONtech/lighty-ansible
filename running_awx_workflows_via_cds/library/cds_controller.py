#!/usr/bin/env python3
#
#  Copyright (c) 2020 PANTHEON.tech s.r.o. All Rights Reserved.
#
#  This program and the accompanying materials are made available under the
#  terms of the Eclipse Public License v1.0 which accompanies this distribution,
#  and is available at https://www.eclipse.org/legal/epl-v10.html
#


"""
This module implements select requests to HTTP REST API
of ONAP CDS blueprint processor.
"""

import binascii
import collections
import io
import json
import os.path
import random

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, urllib_error

# parameter names
P_CMD = "cmd"
P_CDS_URL = "cds_url"
P_CDS_AUTH_TOKEN = "cds_auth_token"
P_TIMEOUT = "timeout"


def main():
    """ Parse Ansible module parameters and call respective method. """

    fields = {
        P_CMD: {"default": None, "type": "str"},
        P_CDS_URL: {"default": "http://localhost:8000", "type": "str"},
        P_CDS_AUTH_TOKEN: {
            "default": "Y2NzZGthcHBzOmNjc2RrYXBwcw==", "type": "str"},
        P_TIMEOUT: {"default": 60, "type": "int"},
    }
    for cmd in API:
        endpoint = API[cmd]
        for parameter in endpoint.parameters:
            # make sure same parameter
            fields[parameter.name] = {
                "default": parameter.default,
                "type": parameter.cls.__name__.lower()}

    module = AnsibleModule(argument_spec=fields, supports_check_mode=True)

    cmd = module.params[P_CMD]
    cds_url = module.params[P_CDS_URL].rstrip('/')
    cds_auth_token = module.params[P_CDS_AUTH_TOKEN]
    timeout = module.params[P_TIMEOUT]

    result = dict(
        changed=False,
        original_message='',
        msg='',
        answer='',
    )

    try:
        endpoint = API[cmd]
    except KeyError:
        result['msg'] = "Unknown command specified: {cmd}".format(cmd=cmd)
        module.fail_json(**result)

    values = {}
    target = None
    for parameter in endpoint.parameters:
        value = module.params[parameter.name]
        if value is None:
            result['msg'] = "Parameter missing or invalid: {name}".format(
                name=parameter.name)
            module.fail_json(**result)
        if parameter.cls is Path and not parameter.payload:
            target = parameter.cls(value)
        else:
            values[parameter.name] = parameter.cls(value)

    route = endpoint.route.format(**values)
    request_url = API_ROUTE.format(cds_url=cds_url, route=route)
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic {token}'.format(token=cds_auth_token),
    }

    if not endpoint.payload:
        payload = None
    else:
        values = {(parameter.name, parameter.payload): values[parameter.name]
                  for parameter in endpoint.parameters if parameter.payload}
        if endpoint.payload == 'JSON':
            payload = encode_json(values, headers)
        elif endpoint.payload == 'FORM':
            payload = encode_multipart(values, headers, not module.check_mode)

    success = False
    try:
        if module.check_mode and endpoint.method != 'GET':
            result['msg'] = 'CDS call skipped for check mode'
            result['answer'] = {
                'request_url': request_url,
                'method': endpoint.method,
                'headers': headers,
                'data': payload,
            }
            module.exit_json(**result)

        response = FetchResponse(target, fetch_url(
            module=module, url=request_url, data=payload, headers=headers,
            method=endpoint.method, timeout=timeout))

        result['answer'] = response.answer
        if (200 <= response.status < 300
                or endpoint.method == 'DELETE' and response.status == 404):
            success = True
            if endpoint.method != 'GET':
                result['changed'] = True
            msg = 'CDS call succeeded ({status})'
        else:
            msg = 'CDS call failed ({status})'
        result['msg'] = msg.format(status=response.status)
    except urllib_error.HTTPError as err:
        result['msg'] = "{err}".format(err=err)

    if success:
        module.exit_json(**result)
    else:
        module.fail_json(**result)


class Path(object):

    def __init__(self, path):
        self.path = path

    @property
    def base(self):
        return os.path.basename(self.path)

    @property
    def mime(self):
        split = self.path.rsplit('.', 1)
        return (split[1] if len(split) == 2 else None) or 'octet-stream'

    def get(self):
        with io.open(self.path, 'rb') as source:
            return source.read()


class FetchResponse(dict):
    def __init__(self, target, fetch_result):
        super(FetchResponse, self).__init__(fetch_result[1])
        self.status = self['status']
        self.data = (self.get('body', '')
                     if fetch_result[0] is None
                     else fetch_result[0].read())
        self.answer = self.data
        if self.status == 204 or not self.data:
            return

        # content-type is usually wrong
        if target is not None and self.status < 300:
            with io.open(target.path, 'wb') as output:
                output.write(self.data)
            self.answer = 'Content written to {path}'.format(path=target.path)
        else:
            try:
                self.answer = json.loads(self.data)
            except ValueError:
                pass


def encode_json(values, headers):
    headers['Content-Type'] = 'application/json'
    output = {}
    for name, key in values:
        value = values[name, key]
        if key is True:
            parts = []
        else:
            parts = key.split('/')
            name = parts.pop() or name
        into = output
        for part in parts:
            try:
                into = into[part]
            except KeyError:
                into[part] = into = {}
        into[name] = value
    return json.dumps(output)


def encode_multipart(values, headers, read_path):
    """Encode a multipart msg, but put root headers aside"""
    if not values:
        return b''
    boundary = str(random.randint(1 << 20, 1 << 64)).encode()
    headers['Content-Type'] = ('multipart/form-data; boundary="{boundary}"'
                               .format(boundary=boundary))

    output = io.BytesIO()
    for name, key in values:
        value = values[name, key]
        if key is True:
            key = name
        if isinstance(value, Path):
            payload = value.get() if read_path else value.path.encode()
            mime = 'application/{mime}'.format(mime=value.mime)
            disposition = '; name="{key}"; filename="{base}"'.format(
                key=key, base=value.base)
        else:
            payload = str(value).encode('utf-8')
            mime = 'text/form-data; encoding="utf-8"'
            disposition = '; name="{key}"'.format(key=key)

        output.write('--{boundary}\r\n'.format(boundary=boundary).encode())
        output.write('Content-Disposition: form-data{plus}\r\n'.format(
            plus=disposition).encode())
        output.write('Content-Type: {mime}\r\n\r\n'.format(mime=mime).encode())
        output.write(payload)
    output.write('\r\n--{boundary}--\r\n'.format(boundary=boundary).encode())
    return output.getvalue()


CdsControllerEndpoint = collections.namedtuple(
    'CdsControllerEndpoint', 'name method route payload parameters')

CdsControllerParameter = collections.namedtuple(
    'CdsControllerParameter', 'name cls default payload')


API_ROUTE = '{cds_url}/api/v1/{route}'

API = {name: CdsControllerEndpoint(
    name, method, route, payload,
    [CdsControllerParameter(*parameter) for parameter in parameters])
       for name, method, route, payload, parameters in [
           ('health', 'GET', 'execution-service/health-check', '', []),
           ('model_type', 'GET', 'model-type/{name}', '', [
               ("name", str, None, False),
           ]),
           ('bootstrap', 'POST', 'blueprint-model/bootstrap', 'JSON', [
               ("load_types", bool, True, "loadModelType"),
               ("load_dicts", bool, True, "loadResourceDictionary"),
               ("load_cbas", bool, True, "loadCBA"),
           ]),
           ('blueprints', 'GET', 'blueprint-model', '', []),
           ('blueprint', 'GET', 'blueprint-model/{blueprint}', '', [
               ("blueprint", str, None, False),
           ]),
           ('named_blueprint', 'GET', 'blueprint-model/by-name/{blueprint}/version/{version}', '', [
               ("blueprint", str, None, False),
               ("version", str, None, False),
           ]),
           ('remove', 'DELETE', 'blueprint-model/{blueprint}', '', [
               ("blueprint", str, None, False),
           ]),
           ('enrich', 'POST', 'blueprint-model/enrich', 'FORM', [
               ("cba_source", Path, None, 'file'),
               ("cba_target", Path, None, False),
           ]),
           ('upload', 'POST', 'blueprint-model', 'FORM', [
               ("cba_source", Path, None, 'file'),
           ]),
           ('execute', 'POST', 'execution-service/process', 'JSON', [
               #
               ("timestamp", str, None, "commonHeader/"),
               ("originator", str, None, "commonHeader/originatorId"),
               ("request", str, None, "commonHeader/requestId"),
               ("subrequest", str, None, "commonHeader/subRequestId"),
               ("force", bool, False, "commonHeader/flags/isForce"),
               ("ttl", int, 3600, "commonHeader/flags/"),
               ("blueprint", str, None, "actionIdentifiers/blueprintName"),
               ("version", str, None, "actionIdentifiers/blueprintVersion"),
               ("workflow", str, None, "actionIdentifiers/actionName"),
               ("mode", str, "sync", "actionIdentifiers/"),
               # top-level
               ("payload", dict, {}, True),
           ]),
       ]}


if __name__ == '__main__':
    main()
