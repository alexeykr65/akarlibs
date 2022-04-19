#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Nornir inventory from openstack
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
from operator import mod
import ansible_runner
import json

import nornir
import nornir.core
import bpdb
import logging
from pathlib import Path
from akarlibs.gentemplates import GenTemplates
from akarlibs.akarlogging import AkarLogging
from typing import Any, Dict, cast


ANS_HOSTS_TEMPLATE = "ansible_srvs.j2"
ANS_ROLES_TEMPLATE = "ansible_roles.j2"
ANS_PLAYBOOK = {
                'hosts': 'all',
                'gather_facts': False,
                'roles': [
                    {
                    'role': 'gitlab',
                    'when': 'gitlab_role is defined',
                },
                {
                    'role': 'jenkins',
                    'when': 'jenkins_role is defined',
                },
                {
                    'role': 'ansible',
                    'when': 'ansible_role is defined',
                },
                {
                    'role': 'kubespray/common',
                    'when': 'kubespray_common_role is defined',
                },
                ]
            }

class RunAnsibleRoles():

    def __init__(self, nor_hosts: nornir.core.Nornir) -> None:
        # bpdb.set_trace()
        self._logger = AkarLogging(logging.INFO, "RunAnsibleRoles").get_color_logger()
        self._logger.info(f'Srvs Hosts: {nor_hosts.inventory.hosts}')
        ans_host_template = Path(Path(__file__).parent, ANS_HOSTS_TEMPLATE)
        gtmp = GenTemplates(template_file=ans_host_template, template_data=nor_hosts)
        self.ans_hosts = gtmp.generate_template()        
        self._logger.info(f'hosts: {self.ans_hosts}')
        self.ansible_roles = dict()
        for h in nor_hosts.inventory.hosts:
            if 'ansible_roles' in nor_hosts.inventory.hosts[h].data['lab_config']:
                for role in nor_hosts.inventory.hosts[h].data['lab_config']['ansible_roles']:
                    if role not in self.ansible_roles:
                        self.ansible_roles[role] = list()
                    self.ansible_roles[role].append(h)
        ans_roles_template = Path(Path(__file__).parent, ANS_ROLES_TEMPLATE)
        gtmp = GenTemplates(template_file=ans_roles_template, template_data=self.ansible_roles)
        self.ans_playbook = gtmp.generate_template()
        self.ans_playbook_file = str(Path(Path.cwd(), "gen_playbook.yml"))
        with open(self.ans_playbook_file, mode='w') as f:
            f.write(self.ans_playbook)
#        self._logger.info(f'playbook: {self.ans_playbook}')

        #playbook = ANS_PLAYBOOK
        envvars = {
                'ANSIBLE_ROLES_PATH': '~/my_ansible_roles:',
            }
        extravars: Dict[str, Any] = {}
        #     "jenkins_role": "True", 
        #     "net_os": "ubuntu"
        # }
        kwargs = {
            'playbook': self.ans_playbook_file,
            'inventory': self.ans_hosts,
    #        'private_data_dir': '.',
            'envvars': envvars,
            'extravars': extravars
        }
        self._logger.info(f'Run ansible playbooks')
        result = ansible_runner.run(**kwargs)
        # stdout = result.stdout.read()
        # events = list(result.events)
        # stats = result.stats

        # print(json.dumps(stats, indent=4))

    def get_roles(self):
        pass

