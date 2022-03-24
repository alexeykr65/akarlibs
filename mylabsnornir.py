#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for get information from routers Cisco
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
"""
Classes for get information from routers Cisco using Nornir
version: 1.0
@author: alexeykr@gmail.com
"""
import warnings
import re
import time
import yaml
import os

# from nornir.plugins.functions.text import (
#     print_result, print_title
# )
# from nornir.core.filter import F
from termcolor import colored
from netaddr import IPNetwork
from nornir import InitNornir
from datetime import datetime
from nornir.plugins.tasks.text import template_file
from nornir.plugins.tasks.networking import netmiko_send_config, napalm_configure, netmiko_send_command

warnings.filterwarnings(action='ignore', module='.*paramiko.*')


class MyLabsNornir:
    """ Class for get information from cisco routers """

    def __init__(self, config_file='config.yaml', filter_roles='', filter_hosts='', data_file='', output_dir='output'):
        self._config_file = config_file
        self._filter_roles = list(filter_roles.lower().split(','))
        self._filter_hosts = list(filter_hosts.lower().split(','))
        self._dry_run = False
        self._data_file = data_file
        self._load_data = ''
        self._res = ''
        self._ospf_filter = ['area', 'nei', 'db']
        self._output_dir = output_dir
        self._save_to_file = True
        # print(f'roles: {self.__filter_hosts}')
        if filter_roles != '':
            norf = InitNornir(config_file=self._config_file, dry_run=False)
            self._nor = norf.filter(filter_func=self.filter_roles)
        elif filter_hosts != '':
            norf = InitNornir(config_file=self._config_file, dry_run=False)
            self._nor = norf.filter(filter_func=self.filter_hosts)
        else:
            self._nor = InitNornir(config_file=self._config_file, dry_run=False)

        if self._data_file != '':
            with open(self._data_file, mode='r') as yaml_id:
                self._load_data = yaml.load(yaml_id, Loader=yaml.CLoader)
        self.getdate()
        filebits = ["output", self.year, self.month, self.day, self.hour, self.minute + ".markdown"]
        self._date_name_file = '-'.join(filebits)

    def write_to_file(self, prep_name, to_file, flag_config):
        """
        This function save output of command to file.
        """
        if not os.path.exists(f'{self._output_dir}'):
            os.makedirs(f'{self._output_dir}')
        if flag_config:
            fileSave = '-'.join([prep_name, "config.txt"])
            name_file = f'{self._output_dir}/{fileSave}'
        else:
            fileSave = '-'.join([prep_name, self._date_name_file])
            if not os.path.exists(f'{self._output_dir}/{prep_name}'):
                os.makedirs(f'{self._output_dir}/{prep_name}')
            name_file = f'{self._output_dir}/{prep_name}/{fileSave}'
        # print(f'name_file: {name_file}')
        with open(f'{name_file}', 'w') as f:
            f.write(to_file)

    def getdate(self):
        """
        This function returns a tuple of the year, month and day.
        """
        # Get Date
        now = datetime.now()
        self.day = str(now.day)
        self.month = str(now.month)
        self.year = str(now.year)
        self.hour = str(now.hour)
        self.minute = str(now.minute)
        if len(self.day) == 1:
            self.day = '0' + self.day
        if len(self.month) == 1:
            self.month = '0' + self.month

    def filter_roles(self, host):
        ret = False
        if 'role' in host.data:
            ret = host.data["role"] in self._filter_roles
        return ret

    @classmethod
    def ipaddr(cls, input_str, net_cfg):
        ip_net = IPNetwork(input_str)
        ret = ''
        if net_cfg == 'address':
            ret = ip_net.ip
        elif net_cfg == 'netmask':
            ret = ip_net.netmask
        elif net_cfg == 'hostmask':
            ret = ip_net.hostmask
        elif net_cfg == 'network':
            ret = ip_net.network
        return ret

    def filter_hosts(self, host):
        return str(host).lower() in self._filter_hosts

    @property
    def ospf_filter(self):
        return self._ospf_filter

    @ospf_filter.setter
    def ospf_filter(self, val):
        self._ospf_filter = val

    @property
    def nor(self):
        return self._nor

    @property
    def load_data(self):
        return self._load_data

    @classmethod
    def ping_task(cls, task, dt):
        for ph in dt['ping_check'][str(task.host)]:
            cmd = f'ping {ph} repeat 3'
            task.run(name=f'Ping {ph}', task=netmiko_send_command, command_string=cmd)

    def ping(self):
        res = self._nor.run(task=self.ping_task, dt=self._load_data)
        for i in res:
            if i in self._load_data['ping_check']:
                self.print_title_host(f'{i}')
                for jj in res[i]:
                    if re.search("Success rate is 100", str(jj), re.DOTALL):
                        self.print_body_result(f'{str(jj.name)} is OK')
                    elif re.search("Success rate is 0", str(jj), re.DOTALL):
                        print(colored(f'{str(jj.name)} is Failed', 'white', 'on_red', attrs=['bold']))

    @classmethod
    def run_cmds_task(cls, task, cmds):
        for cmd in list(cmds.split(',')):
            task.run(name=f'{cmd}', task=netmiko_send_command, command_string=cmd)

    def run_cmds(self, cmds, rgx='.*', flag_config=False):
        res = self._nor.run(task=self.run_cmds_task, cmds=cmds)
        result_ret = dict()
        for i in res:
            to_file = ""
            result_ret[i] = ""
            self.print_title_host(f'{i}', flag_center=True)
            # print(colored(f'=============================== {i} ==================================', 'white'))
            # to_file += f'========================== {i} ============================\n'
            for j in range(1, len(res[i])):
                self.print_title_result(f'{res[i][j].name}')
                line_to_print = ''
                for ln in str(res[i][j]).split('\n'):
                    if re.search(rgx, ln):
                        line_to_print += f'{ln}\n'
                self.print_body_result(f'{line_to_print}')
                to_file += f'### {i}: ===>> {res[i][j].name} <<===\n'
                to_file += f'{res[i][j]}\n\n\n'
                result_ret[i] += line_to_print
            if self._save_to_file:
                self.write_to_file(i.lower(), to_file, flag_config=flag_config)
        return result_ret

    def get_config(self):
        res = self._nor.run(task=self.run_cmds_task, cmds='show run')
        for i in res:
            to_file = ""
            self.print_title_host(f'{i}', flag_center=True)
            for j in range(1, len(res[i])):
                self.print_title_result(f'{res[i][j].name}')
                self.print_body_result(f'{str(res[i][j])}')
                to_file += f'{i}#{res[i][j].name}\n'
                to_file += f'{res[i][j]}\n\n\n'
            if self._save_to_file:
                self.write_to_file(i.lower(), to_file, flag_config=True)

    def get_cdp(self, out_dir=""):
        if out_dir:
            tmp_dir = self._output_dir
            self._output_dir = out_dir
        res = self._nor.run(task=self.run_cmds_task, cmds='show cdp nei deta')
        for i in res:
            to_file = ""
            self.print_title_host(f'{i}', flag_center=True)
            for j in range(1, len(res[i])):
                self.print_title_result(f'{res[i][j].name}')
                self.print_body_result(f'{str(res[i][j])}')
                to_file += f'{i}#{res[i][j].name}\n'
                to_file += f'{res[i][j]}\n\n\n'
            if self._save_to_file:
                self.write_to_file(i.lower(), to_file, flag_config=True)
        if out_dir:
            self._output_dir = tmp_dir

    @classmethod
    def ospf_info_task(cls, task, ospf):
        cmd = f'show ip ospf nei'
        r = task.run(
            name=f'Command: {cmd}',
            task=netmiko_send_command,
            command_string=cmd
            # severity_level=logging.ERROR
        )
        pattern = r'''
                (?P<rid>\d+\.\d+\.\d+\.\d+)\s+
                (?P<priority>\d+)\s+
                (?P<state>\w+)/\s*
                (?P<role>[A-Z-]+)\s+
                (?P<deadtime>[0-9:]+|-)\s+
                (?P<peer>\d+\.\d+\.\d+\.\d+)\s+
                (?P<intf>[0-9A-Za-z./_-]+)
            '''
        inf_nei = r.result
        regex = re.compile(pattern, re.VERBOSE)
        ospf_neighbors = []
        if inf_nei:
            ospf[str(task.host)] = dict()
            for line in inf_nei.split('\n'):
                match = regex.search(line)
                if match:
                    gdict = match.groupdict()
                    # gdict['priority'] = FilterModule._try_int(gdict['priority'])
                    gdict['state'] = gdict['state'].lower()
                    gdict['role'] = gdict['role'].lower()
                    gdict['intf'] = gdict['intf'].lower()
                    ospf_neighbors.append(gdict)
            ospf[str(task.host)]['neighbor'] = ospf_neighbors

        #########################################################
        # Check command 'show ip ospf database database-summary'
        cmd = f'show ip ospf'
        r = task.run(
            name=f'Command: {cmd}',
            task=netmiko_send_command,
            command_string=cmd
            # severity_level=logging.ERROR
        )
        inf_nei = r.result

        process_pattern = r'''
            Routing\s+Process\s+"ospf\s+(?P<id>\d+)"\s+with\s+ID\s+(?P<rid>\d+\.\d+\.\d+\.\d+)
            .*
            \s*Initial\s+SPF\s+schedule\s+delay\s+(?P<init_spf>\d+)\s+msecs
            \s*Minimum\s+hold\s+time\s+between\s+two\s+consecutive\s+SPFs\s+(?P<min_spf>\d+)\s+msecs
            \s*Maximum\s+wait\s+time\s+between\s+two\s+consecutive\s+SPFs\s+(?P<max_spf>\d+)\s+msecs
            .*
            \s*Reference\s+bandwidth\s+unit\s+is\s+(?P<ref_bw>\d+)\s+mbps
        '''
        ospf_proc = dict()
        regex = re.compile(process_pattern, re.VERBOSE + re.DOTALL)

        match = regex.search(inf_nei)
        if match:
            ospf_proc = match.groupdict()
            ospf_proc.update(
                {
                    'is_abr': inf_nei.find('area border') != -1,
                    'is_asbr': inf_nei.find('autonomous system boundary') != -1,
                    'is_stub_rtr': inf_nei.find('Originating router-LSAs with max') != -1,
                    'has_ispf': inf_nei.find('Incremental-SPF enabled') != -1,
                    'has_bfd': inf_nei.find('BFD is enabled') != -1,
                    'has_ttlsec': inf_nei.find('Strict TTL checking enabled') != -1,
                }
            )
            ospf[str(task.host)]['process'] = ospf_proc

        area_pattern = r'''
            Area\s+(?:BACKBONE\()?(?P<id>\d+)(?:\))?\s+
            Number\s+of\s+interfaces\s+in\s+this\s+area\s+is\s+(?P<num_intfs>\d+).*\n
            \s+(?:It\s+is\s+a\s+(?P<type>\w+)\s+area)?
        '''
        regex = re.compile(area_pattern, re.VERBOSE)
        if match:
            areas = [match.groupdict() for match in regex.finditer(inf_nei)]
            for area in areas:
                # area['num_intfs'] = FilterModule._try_int(area['num_intfs'])
                # area['id'] = FilterModule._try_int(area['id'])
                if not area['type']:
                    area['type'] = 'standard'
                else:
                    area['type'] = area['type'].lower()
            ospf[str(task.host)]['areas'] = areas
        #########################################################
        # Check command 'show ip ospf database database-summary'
        cmd = f'show ip ospf database database-summary'
        r = task.run(
            name=f'Command: {cmd}',
            task=netmiko_send_command,
            command_string=cmd
            # severity_level=logging.ERROR
        )
        res = r.result
        process_pattern = r'''
            Process\s+(?P<process_id>\d+)\s+database\s+summary\s+
            (?:LSA\s+Type\s+Count\s+Delete\s+Maxage\s+)?
            Router\s+(?P<total_lsa1>\d+).*\n\s+
            Network\s+(?P<total_lsa2>\d+).*\n\s+
            Summary\s+Net\s+(?P<total_lsa3>\d+).*\n\s+
            Summary\s+ASBR\s+(?P<total_lsa4>\d+).*\n\s+
            Type-7\s+Ext\s+(?P<total_lsa7>\d+).*
            \s+Type-5\s+Ext\s+(?P<total_lsa5>\d+)
        '''
        regex = re.compile(process_pattern, re.VERBOSE + re.DOTALL)
        match = regex.search(res)
        dbms_sum = dict()
        if match:
            match = regex.search(res)
            dbms_sum = match.groupdict()

            ospf[str(task.host)]['dbms_sum'] = dbms_sum

        area_pattern = r'''
            Area\s+(?P<id>\d+)\s+database\s+summary\s+
            (?:LSA\s+Type\s+Count\s+Delete\s+Maxage\s+)?
            Router\s+(?P<num_lsa1>\d+).*\n\s+
            Network\s+(?P<num_lsa2>\d+).*\n\s+
            Summary\s+Net\s+(?P<num_lsa3>\d+).*\n\s+
            Summary\s+ASBR\s+(?P<num_lsa4>\d+).*\n\s+
            Type-7\s+Ext\s+(?P<num_lsa7>\d+)
        '''
        regex = re.compile(area_pattern, re.VERBOSE)
        # match = regex.search(res)
        dbms_sum_areas = list()
        if match:
            dbms_sum_areas = [match.groupdict() for match in regex.finditer(res)]
            ospf[str(task.host)]['dbms_sum_areas'] = dbms_sum_areas

    def ospf_info(self):
        filter_output = self._ospf_filter
        ospf_info = dict()
        res = self._nor.run(task=self.ospf_info_task, ospf=ospf_info)
        # print_result(f'Result: {res}')
        for i in sorted(ospf_info):
            # print(colored("*"*83, 'yellow', attrs=['bold']))
            type_host = ""

            if ospf_info[i]['process']['is_abr']:
                # ABR:{is_abr} ASBR:{is_asbr} STUB:{is_stub_rtr}
                type_host += f'ABR '
            if ospf_info[i]['process']['is_asbr']:
                type_host += f'ASBR '
            if ospf_info[i]['process']['is_stub_rtr']:
                type_host += f'STUB '
            self.print_title_host(f'HOSTNAME: {i}' + '   OSPFid: {id:4s} RID: {rid:15s}'.format_map(ospf_info[i]['process']) + type_host)

            # print_title_result("Process OSPF")
            # print_body_result('Process: {id:4s} RID: {rid:15s} ABR:{is_abr} ASBR:{is_asbr} STUB:{is_stub_rtr}'.format_map(ospf_info[i]['process']))
            if 'area' in filter_output:
                self.print_title_result("Areas")
                for n in ospf_info[i]['areas']:
                    self.print_body_result('Area: {id:6s} Type: {type:16s} Number of Interfaces: {num_intfs:4s} '.format_map(n))

            if 'nei' in filter_output:
                self.print_title_result("Neighbors")
                for n in ospf_info[i]['neighbor']:
                    self.print_body_result('{rid:15s} {state:6s} {role:6s} {peer:15s} {intf:s}'.format_map(n))
            if 'db' in filter_output:
                self.print_title_result("Database Summary")
                # print_body_result('Process: {process_id:4s}'.format_map(ospf_info[i]['dbms_sum']))
                self.print_body_result(
                    'Proc: {process_id:4s} LSA1: {total_lsa1:5s} LSA2: {total_lsa2:5s} LSA3: {total_lsa3:5s} LSA4: {total_lsa4:5s} LSA7: {total_lsa7:5s} LSA5: {total_lsa5:5s}'.format_map(
                        ospf_info[i]['dbms_sum']
                    )
                )
                self.print_title_result("Area Database Summary ")
                for n in ospf_info[i]['dbms_sum_areas']:
                    # print_body_result('Area: {id:4s} '.format_map(n))
                    self.print_body_result(
                        'Area: {id:4s} LSA1: {num_lsa1:5s} LSA2: {num_lsa2:5s} LSA3: {num_lsa3:5s} LSA4: {num_lsa4:5s} LSA7: {num_lsa7:5s}'.format_map(n)
                    )

    def __str__(self):
        return f'Name='

    @classmethod
    def print_title_host(cls, title_txt, flag_center=False):
        print(colored("*" * 83, 'yellow', attrs=['bold']))
        ln = len(title_txt)
        lf = int((80 - ln) / 2)
        rf = int(80 - ln - lf)
        if flag_center:
            print("*" * lf, colored(f' {title_txt}', 'magenta', attrs=['bold', 'underline']), "*" * rf)
        else:
            print(colored(f' {title_txt}', 'magenta', attrs=['bold']))

    @classmethod
    def print_title_result(cls, title_txt):
        ln = len(title_txt)
        lf = int((80 - ln) / 2)
        rf = int(80 - lf - ln)
        print("=" * lf, colored(f' {title_txt}', 'green'), "=" * rf)

    @classmethod
    def print_body_result(cls, body_txt, bg=''):
        # if re.search(regex, body_txt):
        if bg:
            print(colored(body_txt, 'white', bg))
        else:
            print(colored(body_txt, 'white'))
