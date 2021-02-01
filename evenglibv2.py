#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Configure EVE-NG labs
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
"""
Classes for change configuration of router on EVE-NG
version: 2.0
@author: alexeykr@gmail.com
"""

import paramiko
import yaml
import scp
import re
import time
import netmiko as nm
import coloredlogs
import warnings
import logging
import xmltodict
import os
import multiprocessing as mp
from functools import partial
from pyats import aetest
from pyats.topology import loader
from genie import testbed
from netaddr import IPNetwork
from jinja2 import Template, Environment, FileSystemLoader
from .akarlogging import AkarLogging
warnings.filterwarnings(action='ignore', module='.*paramiko.*')


class EveUnlInterface:
    """ Class for description of EVE-NG Interface """

    def __init__(self, id, name, net_id):
        self.__int_id = id
        self.__int_name = name
        self.__int_net_id = net_id
        self.__int_ipv4 = ''
        self.__int_mgmt = False

    def __str__(self):
        return f'IntID: {self.__int_id} IntName: {self.__int_name}  LinkID: {self.__int_net_id} ipv4: {self.__int_ipv4} MGMT: {self.__int_mgmt}'

    @property
    def int_id(self):
        return self.__int_id

    @property
    def int_name(self):
        return self.__int_name

    @property
    def int_net_id(self):
        return self.__int_net_id

    @property
    def int_ipv4(self):
        return self.__int_ipv4

    @int_ipv4.setter
    def int_ipv4(self, ipv4):
        self.__int_ipv4 = ipv4

    @property
    def int_mgmt(self):
        return self.__int_mgmt

    @int_mgmt.setter
    def int_mgmt(self, flg_mgmt):
        self.__int_mgmt = flg_mgmt


class EveUnl:
    """ Class for description of EVE-NG Node """

    def __init__(self, id='', name='', uuid='', nod_type='', template='', firstmac='', image='', ethernet='', nod_int=list()):
        self.__nod_uuid = uuid
        self.__nod_id = id
        self.__nod_type = nod_type
        self.__nod_name = name
        self.__nod_template = template
        self.__nod_firstmac = firstmac
        self.__nod_image = image
        self.__nod_port = ''
        self.__nod_interfaces = nod_int
        self.__nod_routes = list()

    @property
    def name(self):
        return self.__nod_name

    @property
    def interfaces(self):
        return self.__nod_interfaces

    @property
    def uuid(self):
        return self.__nod_uuid

    @property
    def id(self):
        return self.__nod_id

    @property
    def type(self):
        return self.__nod_type

    @property
    def template(self):
        return self.__nod_template

    @property
    def port(self):
        return self.__nod_port

    @port.setter
    def port(self, nod_port):
        self.__nod_port = nod_port

    @property
    def routes(self):
        return self.__nod_routes

    @routes.setter
    def routes(self, nod_routes):
        self.__nod_routes = nod_routes

    @property
    def firstmac(self):
        return self.__nod_firstmac

    def __str__(self):
        ret = f'NodeID= {self.__nod_id}' +\
            f'  Name = {self.__nod_name}' +\
            f'  Port = {self.__nod_port}' +\
            f'  Template = {self.__nod_template}' +\
            f'  Image = {self.__nod_image}'
        for nod_int in self.__nod_interfaces:
            ret = ret + f'\n    {str(nod_int)}'
        for nod_route in self.__nod_routes:
            ret = ret + f'\n    Net Route: {str(nod_route["net_prefix"])} GW: {str(nod_route["gw"])}'

        return ret


class EveNgLab:
    """ Get some information about lab from unl file and processes in EVE-NG """

    def __init__(self, unl_file, eve_ip_host='', eve_ssh_username='root', eve_ssh_password='cisco'):
        self.__template_list = ['csr1000vng', 'xrv', 'vios']
        self.__unl_file = unl_file
        self.__eveng_conn_param = dict()
        self.__eveng_conn_param['ip'] = eve_ip_host
        self.__eveng_conn_param['device_type'] = "linux"
        self.__eveng_conn_param['password'] = eve_ssh_password
        self.__eveng_conn_param['username'] = eve_ssh_username
        self.__local_unl_file = "lab_unl_file.unl"
        self.__cmd_find_unl_file = f'find /opt/unetlab/ -iname "*{self.__unl_file}*.unl"'
        self.__lab_param = dict()
        self.__lg = AkarLogging(logging.INFO, "EveNgLab")
        self.__logger = self.__lg.get_color_logger()

    def __str__(self):
        return f'Device type : {self.__template_list}'

    # @classmethod
    def ipaddr(self, input_str, net_cfg):
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

    def eveng_conn_param(self, eve_ip_host, eve_ssh_username, eve_ssh_password):
        self.__eveng_conn_param['ip'] = eve_ip_host
        self.__eveng_conn_param['password'] = eve_ssh_password
        self.__eveng_conn_param['username'] = eve_ssh_username

    def __connect_to_host(self, cmd_run):
        return_message = ""
        # print(f'Connect to host: {self.__eveng_conn_param}')
        try:
            id_ssh = nm.ConnectHandler(**self.__eveng_conn_param)
            id_ssh.read_channel()
            find_hostname = id_ssh.find_prompt()
            if not find_hostname:
                time.sleep(0.1)
                find_hostname = id_ssh.find_prompt()
            hostname = re.match("root@([^:]*):~#", find_hostname).group(1).strip()
            self.__logger.info(f"Connected to hostname: {hostname} with Ip : {self.__eveng_conn_param['ip']} ... OK")
            cmd_return = id_ssh.send_command(cmd_run)
            self.__logger.debug(f'Run command: {cmd_run} ... OK')
            return_message += '{}\n'.format(cmd_return)
            return return_message
        except Exception as error:
            self.__logger.error(f'{error} Exit script ...')
            # logger.error("Exit script ...")
            exit(1)
        return return_message

    def get_proc_param(self):
        ret_msg = self.__connect_to_host('ps -ax | grep qemu_wrapper')
        for ss in ret_msg.split("\n"):
            proc_variable = dict()
            self.__logger.debug(ss)
            if re.search("uuid", ss):
                re_res = re.match(r'[^-]*-C\s(\d*)\s-T\s\d*\s-D\s\d*\s-t\s([^\s]*).*-uuid\s*([^q]*).*', ss)
                proc_variable['uuid'] = re_res.group(3).strip('-').strip()
                proc_variable['host_name'] = re_res.group(2).strip().lower()
                proc_variable['port'] = re_res.group(1)
                self.__logger.debug(f'HOST: {proc_variable["host_name"]}')
                if proc_variable['host_name'] in self.__lab_param and proc_variable['uuid'] == self.__lab_param[proc_variable['host_name']].uuid:
                    self.__logger.debug('uuid:{uuid} host:{host_name} telnet_port:{port}'.format_map(proc_variable))
                    self.__lab_param[proc_variable["host_name"]].port = proc_variable['port']
                    self.__logger.debug(f' Host: {proc_variable["host_name"]} Port: {proc_variable["port"]}')
        return self.__lab_param

    def parse_unl_file(self, name_unl_file):
        # local_unl_file = 'eve-ng.unl'
        self.__logger.info(f'UNL file on EVE-NG : {name_unl_file}')
        # Find path of UNL file on EVE-NG
        unl_param = dict()
        with open(name_unl_file, mode='r') as id_unl:
            content_xml = id_unl.read()
        dict_xml = xmltodict.parse(content_xml)
        for router in dict_xml['lab']['topology']['nodes']['node']:
            self.__logger.debug(f'RECORD_XML: {router}')
            if "@uuid" in router:
                unl_nod_int = list()
                self.__logger.debug('Name:{@name}  UUID: {@uuid}'.format_map(router))
                # self.__logger.info(f'{router["interface"]}')
                self.__logger.info(f'{router["@name"]} Interfaces:')
                if 'interface' in router:
                    nod_interface = router["interface"]
                    if isinstance(nod_interface, list):
                        for interf in nod_interface:
                            self.__logger.info(f" - id: {interf['@id']}  name: {interf['@name']} net_id: {interf['@network_id']}")
                            unl_nod_int.append(EveUnlInterface(interf['@id'], interf['@name'], interf['@network_id']))
                    else:
                        self.__logger.info(f"id: {nod_interface['@id']}  name: {nod_interface['@name']} net_id: {nod_interface['@network_id']}")
                eve = EveUnl(name=router['@name'].lower(),
                             template=router['@template'],
                             id=router['@id'],
                             nod_type=router['@type'],
                             uuid=router['@uuid'],
                             image=router['@image'],
                             ethernet=router['@ethernet'],
                             nod_int=unl_nod_int)
                unl_param[router['@name'].strip().lower()] = eve

        self.__logger.debug(f'UNL: {unl_param}')
        self.__lab_param = unl_param
        return unl_param

    def get_local_unl_file(self, name_unl_file):
        # local_unl_file = 'eve-ng.unl'
        self.__logger.info(f'Find UNL file on EVE-NG : {name_unl_file}')
        # Find path of UNL file on EVE-NG
        unl_param = self.parse_unl_file(name_unl_file)
        return unl_param

    def get_remote_unl_file(self):
        # local_unl_file = 'eve-ng.unl'
        self.__logger.info(f'Find UNL file on EVE-NG : {self.__cmd_find_unl_file}')
        # Find path of UNL file on EVE-NG
        ret_msg = self.__connect_to_host(self.__cmd_find_unl_file)
        self.__logger.debug(f"Full return: {ret_msg}")
        path_to_unl = ret_msg.strip()
        # print(f'Path: {path_to_unl}')
        self.__logger.info(f"Finded unl file: {path_to_unl}")
        # Get UNL file
        id_conn_paramiko = paramiko.SSHClient()
        id_conn_paramiko.set_missing_host_key_policy(paramiko.WarningPolicy)
        id_conn_paramiko.connect(self.__eveng_conn_param['ip'], username=self.__eveng_conn_param['username'], password=self.__eveng_conn_param['password'])
        with scp.SCPClient(id_conn_paramiko.get_transport()) as id_scp:
            id_scp.get(path_to_unl, self.__local_unl_file)
        self.__logger.info(f'Download file {path_to_unl} ... OK')
        # Analyze UNL file
        unl_param = self.parse_unl_file(self.__local_unl_file)
        return unl_param

    def load_config_yaml(self, name_config_yaml):
        with open(name_config_yaml) as yml:
            conf_Yaml = yaml.load(yml, Loader=yaml.FullLoader)
        for router_name in conf_Yaml:
            # print(router_name)
            for router_int in conf_Yaml[router_name]['interfaces']:
                for unl_int in self.__lab_param[router_name.lower()].interfaces:
                    if unl_int.int_name == router_int['name']:
                        # print(self.__lab_param[router_name.lower()].interfaces)
                        unl_int.int_ipv4 = router_int['ipv4']
                        if 'mgmt' in router_int:
                            unl_int.int_mgmt = True
            for router_route in conf_Yaml[router_name]['routes']:
                nod_routes = dict()
                nod_routes['net_prefix'] = router_route['net']
                nod_routes['gw'] = router_route['gw']
                self.__lab_param[router_name.lower()].routes.append(nod_routes)
        for k in self.__lab_param:
            for m in self.__lab_param[k].interfaces:
                self.__logger.info(f'Node: {k} {m}')

    def generate_jinja(self, tmp_name_file, out_file):
        file_loader = FileSystemLoader('evenglibv2')
        env = Environment(loader=file_loader)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        env.filters['ipaddr'] = self.ipaddr
        template = env.get_template(tmp_name_file)
        output = template.render(unl_param=self.__lab_param, eve_ng_ip_host=self.__eveng_conn_param['ip'])
        with open(out_file, mode='w') as file_:
            file_.write(output)

    def create_tbd_file(self, testbed_name_file):
        self.__logger.info(f'Generate Cisco Testbed file: {testbed_name_file}')
        for hst in self.__lab_param:
            self.__logger.debug(f'{self.__lab_param[hst]}')
        self.generate_jinja('testbed_eveng.j2', testbed_name_file)

    def create_ansible_file(self):
        self.__logger.info(f'Generate Ansible Hosts file: hosts.yml')
        for hst in self.__lab_param:
            self.__logger.debug(f'{self.__lab_param[hst]}')
        self.generate_jinja('ansible_hosts.j2', 'hosts.yml')

    @property
    def unl_lab_param(self):
        return self.__lab_param

    @unl_lab_param.setter
    def unl_lab_param(self, new_lab):
        self.__lab_param = new_dv


class TestbedConf:
    """ Configure nodes using module pyaty/genie """

    def __init__(self, file_testbed):
        self.__file_testbed = file_testbed
        self.__testbed = testbed.load(file_testbed)
        self.__init_exec_commands = []
        self.__log_stdout = False
        # self.__init_conf_commands = []
        self.__lg = AkarLogging(logging.INFO, "TestbedConf")
        self.__logger = self.__lg.get_color_logger()
        self.__logger.info(f'Initialized class TestbedConf')

    def execute_in_fork(self, dev):
        proc = os.getpid()
        self.__logger.info(f'Process pid: {proc} Connected to hostname: {dev.name}')
        dev.connect(init_exec_commands=self.__init_exec_commands, log_stdout=self.__log_stdout)
        assert dev.connected
        for int_name in dev.interfaces:
            dev_int = dev.interfaces[int_name]
            dev_int.vrf = "MGMT"
            self.__logger.info(f'Host: {dev.name} Int: {int_name} ipv4: {dev_int.ipv4}')
            dev_int.build_config(apply=True)
        dev.configure(f'hostname {dev.name}')
        dev.configure(self.__testbed.custom.postcommands['all'], timeout=60)
        dev.configure(self.__testbed.custom.postcommands[dev.name], timeout=60)
        dev.execute("wr mem")
        dev.disconnect()

    def execute_testbed(self):
        jobs = []
        self.__logger.info(f'Configure devices ...')
        for dev_name in self.__testbed.devices:
            dev = self.__testbed.devices[dev_name]
            p = mp.Process(target=self.execute_in_fork, args=(dev,))
            jobs.append(p)
            p.start()
        for pr in jobs:
            pr.join()

    def run_testbed(self):
        self.__logger.info(f'Run Testing of configuration')
        file_path = "evenglibv2/evetestbed.py"
        # aetest.main(testable=file_path, testbed=Genie.init(self.__file_testbed), logger=self.__logger)
        testbed = loader.load(self.__file_testbed)
        aetest.main(testable=file_path, testbed=testbed, logger=self.__logger)
