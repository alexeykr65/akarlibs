#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for extract information from openstack
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
import logging
import yaml
import json
import urllib3
import re
import os
import netmiko
import paramiko
import requests
import subprocess
import time
from .akarlogging import AkarLoggingRich
from scp import SCPClient
from vmanage.api.authentication import Authentication
from vmanage.api.certificate import Certificate
from vmanage.api.settings import Settings
from vmanage.api.utilities import Utilities
from vmanage.api.device import Device
from jinja2 import Template, Environment, BaseLoader, FileSystemLoader

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

enable_tunnel = """
    {% if val.dv_type == 'cedge' %}
    config-transaction
    sdwan
    {% else %}
    config
    {% endif %}
    {% if val.dv_type != 'cedge' %}
    vpn 0
    {% endif %}
     interface {{ val.int_vpn0 }}
      tunnel-interface
    {% if val.dv_type == 'vbond' or val.dv_type == 'vedge' or val.dv_type == 'cedge' %}
       encapsulation ipsec
    {% endif %}
       exit
    commit
    end
"""

netmiko.log.setLevel(logging.ERROR)

OPENSSL = '/usr/bin/openssl'


class ViptelaTemplate:
    def __init__(self, cfg_tmp):
        self.t_type = cfg_tmp['t_type']
        self.name = cfg_tmp['name']
        self.t_scope = cfg_tmp['t_scope']
        self.descr = cfg_tmp['description']
        self.dv_type = cfg_tmp['device_type']
        if 'template_vpn' in cfg_tmp and len(cfg_tmp['template_vpn']) > 0:
            self.vpn_id = cfg_tmp['template_vpn']['vpn_id']
            self.vpn_name = cfg_tmp['template_vpn']['vpn_name']
            self.routes = list()
            self.omp = False
            if 'omp' in cfg_tmp['template_vpn']:
                self.omp = True
            if 'routes' in cfg_tmp['template_vpn'] and len(cfg_tmp['template_vpn']['routes']) > 0:
                for rt in cfg_tmp['template_vpn']['routes']:
                    vm = dict()
                    vm['prefix'] = rt['prefix']
                    vm['prefix_var_name'] = rt['prefix_var_name']
                    vm['next_hop_var_name'] = rt['next_hop_var_name']
                    vm['distance_val'] = rt['distance_val']
                    vm['distance_var_name'] = rt['distance_var_name']
                    self.routes.append(vm)

        if 'template_interface' in cfg_tmp and len(cfg_tmp['template_interface']) > 0:
            rt = cfg_tmp['template_interface']
            vm = dict()
            vm['name'] = rt['name']
            vm['if_var_name'] = rt['if_var_name']
            vm['if_desc_var_name'] = rt['if_desc_var_name']
            vm['ip_addr'] = rt['ip_addr']
            vm['ip_addr_var_name'] = rt['ip_addr_var_name']
            vm['dhcp'] = rt['dhcp']
            self.interface = vm

    def __str__(self):
        if self.t_scope == "vpn_cfg":
            st = f"""
            Type: [green]{self.t_type}[/]
            name: [green]{self.name}[/]
            descr: [green]{self.descr}[/]
            dv_type: [green]{self.dv_type}[/]
            vpn_id: {self.vpn_id}
            vpn_name: {self.vpn_name}
            routes: {self.routes}
            """
        elif self.t_scope == "vpn_interfaces":
            st = f"""
            Type: [green]{self.t_type}[/]
            name: [green]{self.name}[/]
            descr: [green]{self.descr}[/]
            dv_type: [green]{self.dv_type}[/]
            interface: {self.interface}
            """
        else:
            st = f"""
            Type: [green]{self.t_type}[/]
            name: [green]{self.name}[/]
            descr: [green]{self.descr}[/]
            dv_type: [green]{self.dv_type}[/]
            """

        return st


class Controller:
    def __init__(self, dv_type, dv_vmanage):
        self.dv_type = dv_type
        self.name = dv_vmanage['vm_name']
        self.int_vpn0 = dv_vmanage['interface_vpn0']
        self.int_mgmt = dv_vmanage['interface_mgmt']
        self.mgmt_ip = dv_vmanage['mgmt_ip']
        if 'port' in dv_vmanage:
            self.port = dv_vmanage['port']
        else:
            self.port = ""
        self.vpn0_ip = dv_vmanage['vpn0_ip']
        self.sys_ip = dv_vmanage['sys_ip']
        self.default_route_vpn0 = ""
        if 'default_route_vpn0' in dv_vmanage:
            self.default_route_vpn0 = dv_vmanage['default_route_vpn0']
        self.init_config = ""

    def __str__(self):
        st = f"""
        controller: [green]{self.dv_type}[/]
        name: [green]{self.name}[/]
        int_vpn0: [green]{self.int_vpn0}[/]
        int_mgmt: [green]{self.int_mgmt}[/]
        mgmt_ip: {self.mgmt_ip}
        vpn0_ip: {self.vpn0_ip}
        sys_ip: {self.sys_ip}
        default_route_vpn0: {self.default_route_vpn0}
        """
        return st


class Vedge:
    def __init__(self, dv_type, dv_vmanage):
        self.dv_type = dv_type
        self.name = dv_vmanage['vm_name']
        self.int_vpn0 = dv_vmanage['interface_vpn0']
        self.int_mgmt = dv_vmanage['interface_mgmt']
        self.mgmt_ip = dv_vmanage['mgmt_ip']
        self.vpn0_ip = dv_vmanage['vpn0_ip']
        self.sys_ip = dv_vmanage['sys_ip']
        self.site_id = dv_vmanage['site_id']
        self.vm_model = dv_vmanage['vm_model']
        self.reg_chassis = ""
        self.reg_token = ""
        self.add_routes = list()
        if 'add_routes' in dv_vmanage:
            self.add_routes = dv_vmanage['add_routes']
        self.default_route_vpn0 = ""
        if 'default_route_vpn0' in dv_vmanage:
            self.default_route_vpn0 = dv_vmanage['default_route_vpn0']
        self.init_config = ""

    def __str__(self):
        st = f"""
        controller: [green]{self.dv_type}[/]
        name: [green]{self.name}[/]
        int_vpn0: [green]{self.int_vpn0}[/]
        int_mgmt: [green]{self.int_mgmt}[/]
        mgmt_ip: {self.mgmt_ip}
        vpn0_ip: {self.vpn0_ip}
        sys_ip: {self.sys_ip}
        default_route_vpn0: {self.default_route_vpn0}
        """
        return st


class Viptela:
    def __init__(self, config_file, dbg=logging.INFO):
        self.__logger = AkarLoggingRich("Viptela", level=dbg).get_logger()
        self.init_conf_template_vedges = "template_sdwan_init_config_controllers.j2"
        self.init_conf_template_cedges = "template_sdwan_init_config_cedges.j2"
        self.sdwan_conf = dict()
        with open(config_file, mode='r') as fn:
            self.sdwan_conf = yaml.load(fn, Loader=yaml.FullLoader)
        self.__logger.info(f'[orange1]Init class viptela')
        self.__logger.debug(f'{json.dumps(self.sdwan_conf, indent=4)}')

        self.tftp_server = self.sdwan_conf['all']['tftp_server']
        self.org = self.sdwan_conf['all']['org']
        self.vm_user = self.sdwan_conf['all']['user']
        self.vm_pass = self.sdwan_conf['all']['pass']
        self.site_id = self.sdwan_conf['all']['site_id']
        self.serial_file = self.sdwan_conf['all']['serial_file']
        self.cert_path = self.sdwan_conf['all']['cert_path']
        self.gen_rootca = self.sdwan_conf['all']['gen_rootca']
        self.rootca_name = "CA.crt"
        if self.gen_rootca:
            self.__generate_rootca()

        self.vm_bond_vpn0_ip = self.sdwan_conf['controllers']['vbond']['vpn0_ip']

        self.controllers = self.__get_controllers()
        self.vedges = self.__get_vedges()
        self.__logger.debug(f'{self.controllers}')
        self.templates = self.__get_templates()

        self.vm_mgmt_ip = self.controllers['vmanage'].mgmt_ip
        self.base_url = 'https://%s:%s' % (self.vm_mgmt_ip, self.controllers['vmanage'].port)
        self.vm_sess_api = self.__vmanage_auth()
        self.vm_auth = Authentication()
        # self.vm_auth = Authentication(host=self.vm_mgmt_ip, user=self.vm_user, password=self.vm_pass).login()

    def init_auth(self):
        self.vm_sess_api = self.__vmanage_auth()
        self.vm_auth = Authentication(host=self.vm_mgmt_ip, user=self.vm_user, password=self.vm_pass).login()

    def load_serial_file(self):
        self.__logger.info(f'[orange1]Load license file')
        vmanage_utilities = Utilities(self.vm_auth, self.vm_mgmt_ip)
        result = vmanage_utilities.upload_file(self.serial_file)
        self.__logger.info(result)

    def get_free_bootstrap_device(self, dv_type="vedges"):
        dv = Device(self.vm_auth, self.vm_mgmt_ip)
        self.__logger.debug(f"Get Devices list '{dv_type}'")
        result = dv.get_device_list(dv_type)
        free_lic = dict()
        free_lic['vedge-cloud'] = list()
        free_lic['vedge-CSR-1000v'] = list()
        for dv in result:
            if dv['vedgeCertificateState'] == 'bootstrapconfiggenerated' or dv['vedgeCertificateState'] == 'tokengenerated':
                self.__logger.debug(f'bootstrapconfiggenerated: {dv["uuid"]} {dv["serialNumber"]}')
                lic = dict()
                lic["uuid"] = dv["uuid"]
                lic["serialNumber"] = dv["serialNumber"]
                lic["free"] = True
                free_lic[dv['deviceModel']].append(lic)
        return free_lic

    def push_cert_to_controllers(self):
        cert = Certificate(self.vm_auth, self.vm_mgmt_ip)
        self.__logger.info(f'[orange1]Push certificates to controllers')
        response = cert.push_certificates()
        self.__logger.info(f"[cyan]{response}")

    def initialize_vedges(self):
        self.__logger.info("[orange1]Configure vedges/cedges with init-config ")
        delay_factor = 2
        for vm_name in self.vedges:
            self.__logger.info(f"[magenta]Configure {vm_name}")
            self.send_command_to_device(self.vedges[vm_name].mgmt_ip, str(self.vedges[vm_name].init_config).split("\n"), self.vm_user, self.vm_pass)
        time.sleep(10)
        # Copy root certificate to vedges
        self.__logger.info("[orange1]Copy rootCA to vedges ")
        for vm_name in self.vedges:
            self.__logger.info(f"[magenta]Copy rootCA to {vm_name}")
            if self.vedges[vm_name].dv_type == 'vedge':
                self.__copy_cert_root_to_controller(
                    self.vedges[vm_name].mgmt_ip, f'{self.cert_path}/{self.rootca_name}', f'{self.rootca_name}', self.vm_user, self.vm_pass
                )
            else:
                cmd_copy_rootca = f"copy tftp://{self.tftp_server}/CA.crt bootflash:\n\n\n"
                self.__logger.debug(f"Cmd to run: [green]'{cmd_copy_rootca}'")
                self.send_command_to_device(self.vedges[vm_name].mgmt_ip, ["delete /force bootflash:CA.crt"], self.vm_user, self.vm_pass)
                self.send_command_to_device(self.vedges[vm_name].mgmt_ip, [cmd_copy_rootca], self.vm_user, self.vm_pass, "\?")

        # Install root certificate for vbond, vmanage, vsmart
        self.__logger.info("[orange1]Install rootCA to vedges ")
        for vm_name in self.vedges:
            self.__logger.info(f"[magenta]Install rootCA on {vm_name}")
            if self.vedges[vm_name].dv_type == 'vedge':
                req_install_rootca = f'request root-cert-chain install /home/admin/{self.rootca_name}'
                delay_factor = 2
            else:
                req_install_rootca = f'request platform software sdwan root-cert-chain install bootflash:{self.rootca_name}'
                delay_factor = 10
            self.__logger.debug(f"Cmd to run: [green]'{req_install_rootca}'")
            # req_install_rootca = f'show ip int br'
            self.send_command_to_device(self.vedges[vm_name].mgmt_ip, [req_install_rootca], self.vm_user, self.vm_pass, delay_factor=delay_factor)

        # Enable transport tunnel on controllers
        self.__logger.info(f'[orange1]Enable transport tunnel')
        for vm_name in self.vedges:
            self.__logger.info(f'[magenta]Enable transport tunnel on {vm_name}')
            gen_config = self.get_enable_conf(enable_tunnel, self.vedges[vm_name])
            self.__logger.debug(gen_config)
            self.send_command_to_device(self.vedges[vm_name].mgmt_ip, gen_config.split("\n"), self.vm_user, self.vm_pass)
        # time.sleep(40)
        # Register vedges/cedges on vmanage
        free_lic = self.get_free_bootstrap_device()
        self.__logger.info(f'[orange1]Register vedges/cedges on vmanage')
        self.__logger.debug(f"{free_lic}")
        for vm_name in self.vedges:
            self.__logger.info(f'[magenta]Get bootstrap for {vm_name} from vmanage')
            cur = free_lic[self.vedges[vm_name].vm_model].pop(0)
            self.http_request(f'/dataservice/system/device/bootstrap/device/{cur["uuid"]}?configtype=cloudinit', 'get')
            # device_url = self.base_url + f'/dataservice/system/device/bootstrap/device/{cur["uuid"]}?configtype=cloudinit'
            # response = self.vm_sess_api.get(url=device_url, verify=False)
            # self.__logger.info(f"[cyan]{response}")
            # self.push_cert_to_controllers()
            if self.vedges[vm_name].dv_type == 'vedge':
                cmd_req = f"request vedge-cloud activate chassis-number {cur['uuid']} token {cur['serialNumber']} "
                delay_factor = 2
            else:
                cmd_req = f"request platform software sdwan vedge_cloud activate chassis-number {cur['uuid']} token {cur['serialNumber']}"
                delay_factor = 10
            self.__logger.info(f"Cmd to run: [green]'{cmd_req}'")
            self.__logger.info(f'[magenta]Register {vm_name} on vmanage')
            self.send_command_to_device(self.vedges[vm_name].mgmt_ip, [cmd_req], self.vm_user, self.vm_pass, delay_factor=delay_factor)

    def openssl(self, *args):
        cmdline = [OPENSSL] + list(args)
        subprocess.check_call(cmdline)

    def __get_controllers(self):
        vm = dict()
        self.__logger.info("[orange1]Generate info about vmanage ...[/]")
        vm['vmanage'] = Controller('vmanage', self.sdwan_conf['controllers']['vmanage'])
        vm['vmanage'].init_config = self.__gen_init_config('vmanage', vm['vmanage'], self.site_id)

        self.__logger.info("[orange1]Generate info about vsmart ...[/]")
        vm['vsmart'] = Controller('vsmart', self.sdwan_conf['controllers']['vsmart'])
        vm['vsmart'].init_config = self.__gen_init_config('vsmart', vm['vsmart'], self.site_id)

        self.__logger.info("[orange1]Generate info about vbond ...[/]")
        vm['vbond'] = Controller('vbond', self.sdwan_conf['controllers']['vbond'])
        vm['vbond'].init_config = self.__gen_init_config('vbond', vm['vbond'], self.site_id)

        self.__logger.debug(f"{vm['vmanage']}\n{vm['vsmart']}\n{vm['vbond']}")
        return vm

    def __get_vedges(self):
        vm = dict()
        self.__logger.info("[orange1]Generate info about vedges/cedges ...[/]")
        if 'vedges' in self.sdwan_conf:
            for vdg in self.sdwan_conf['vedges']:
                self.__logger.info(f"Add info vedge: {vdg} ")
                vm[vdg] = Vedge('vedge', self.sdwan_conf['vedges'][vdg])
                vm[vdg].init_config = self.__gen_init_config(vdg, vm[vdg], vm[vdg].site_id)
                self.__logger.debug(f"{vm[vdg]}")

        if 'cedges' in self.sdwan_conf:
            for vdg in self.sdwan_conf['cedges']:
                self.__logger.info(f"Add info cedge: {vdg} ")
                vm[vdg] = Vedge('cedge', self.sdwan_conf['cedges'][vdg])
                vm[vdg].init_config = self.__gen_init_config(vdg, vm[vdg], vm[vdg].site_id)
                self.__logger.debug(f"{vm[vdg]}")
                # self.send_command_to_device(vm[vdg].mgmt_ip, str(vm[vdg].init_config).split("\n"), self.vm_user, self.vm_pass)

        return vm

    def __get_templates(self):
        vm = list()
        self.__logger.info("[orange1]Generate info about templates ...[/]")
        for vdg in self.sdwan_conf['templates']:
            self.__logger.debug(f"{vdg}")
            vm.append(ViptelaTemplate(vdg))

        for tmp in vm:
            self.__logger.debug(f"{str(tmp)}")
        return vm

    def __gen_init_config(self, vm_name, vm_val, site_id):
        self.__logger.info(f'Generate init-config for {vm_name} ')
        src_dir = os.path.dirname(os.path.realpath(__file__))
        self.__logger.debug(f'Source dir: {src_dir}')
        file_loader = FileSystemLoader(src_dir)
        env = Environment(loader=file_loader)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        # env.filters['ipaddr'] = self.ipaddr
        if vm_val.dv_type == 'cedge':
            template = env.get_template(self.init_conf_template_cedges)
        else:
            template = env.get_template(self.init_conf_template_vedges)
        ret_config = template.render(val=vm_val, org=self.org, site_id=site_id, bond_ip=self.vm_bond_vpn0_ip)
        self.__logger.debug(f'{ret_config}')
        return ret_config

    def __vmanage_auth(self):
        login_action = '/j_security_check'
        login_data = {'j_username': self.vm_user, 'j_password': self.vm_pass}
        login_url = self.base_url + login_action
        session = requests.session()
        self.__logger.info(f'Connect to url: [magenta]{login_url}')
        login_response = session.post(url=login_url, data=login_data, verify=False)
        if b'<html>' in login_response.content:
            print("Login Failed")
            exit(1)
        xsrf_token_url = self.base_url + '/dataservice/client/token'
        login_token = session.get(url=xsrf_token_url, verify=False)
        if login_token.status_code == 200:
            if b'<html>' in login_token.content:
                self.__logger.info("Login Token Failed")
                exit(1)

            session.headers['X-XSRF-TOKEN'] = login_token.content
            session.headers['Content-Type'] = 'application/json'
            self.__logger.info("Token of session save")
        return session

    def __generate_rootca(self):
        self.__logger.info(f'Generate Root Certificate')
        self.openssl('genrsa', '-out', f'{self.cert_path}/CA.key', '2048')
        self.openssl(
            'req',
            '-x509',
            '-new',
            '-nodes',
            '-key',
            f'{self.cert_path}/CA.key',
            '-sha256',
            '-days',
            '2000',
            '-subj',
            '/C=RU/ST=MS/L=MS/O=viptela sdwan/CN=SD-WAN',
            '-out',
            f'{self.cert_path}/CA.crt',
        )

    def get_enable_conf(self, vm_config, vm_val):
        env = Environment(loader=BaseLoader).from_string(vm_config)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        ret_config = env.render(val=vm_val)
        return ret_config

    def initialize_controllers(self):
        # Generate Bootstrap configuration for controllers from template jinja2
        self.__logger.info("[orange1]Configure controllers with init-config ")
        for vm_name in self.controllers:
            self.__logger.info(f"[magenta]Configure {vm_name} with init-config ")
            self.send_command_to_device(self.controllers[vm_name].mgmt_ip, str(self.controllers[vm_name].init_config).split("\n"), self.vm_user, self.vm_pass)
            # print(vm_name)
        time.sleep(30)
        # Copy root certificate to controllers
        self.__logger.info("[orange1]Copy rootCA to controllers ")
        for vm_name in self.controllers:
            self.__logger.info(f"[magenta]Copy rootCA to {vm_name}")
            self.__copy_cert_root_to_controller(
                self.controllers[vm_name].mgmt_ip, f'{self.cert_path}/{self.rootca_name}', f'{self.rootca_name}', self.vm_user, self.vm_pass
            )
        self.__logger.info("[orange1]Change settings on vmanage")
        # Set Organization, certificate root ca for vmanage
        self.__set_vmanage_setting()
        # Install root certificate for vbond, vmanage, vsmart
        self.__logger.info("[orange1]Install root certificate on controllers")
        for vm_name in self.controllers:
            self.__logger.info(f"[magenta]Install rootCA on {vm_name}")
            req_install_rootca = f'request root-cert-chain install /home/admin/{self.rootca_name}'
            self.__logger.debug(f"Cmd to run: [green]'{req_install_rootca}'")
            self.send_command_to_device(self.controllers[vm_name].mgmt_ip, [req_install_rootca], self.vm_user, self.vm_pass)
        self.__logger.info(f"[orange1]Sync rootCA ")
        self.sync_root_cert()
        time.sleep(10)
        # Add vsmart to vmanager
        self.__logger.info(f"[orange1]Add 'vsmart' to vmanage")
        self.__add_controller_to_vmanager(self.controllers["vsmart"].vpn0_ip, "vsmart")
        # Add vbond to vmanager
        self.__logger.info(f"[orange1]Add 'vbond' to vmanage")
        self.__add_controller_to_vmanager(self.controllers["vbond"].vpn0_ip, "vbond")
        # Get CSR certificates for vmanage, vsmart, vmbond and sign this csr with root ca
        self.__logger.info(f"[orange1]Get CSR from controllers")
        for vm_name in self.controllers:
            self.__logger.info(f'[magenta]Get CSR and sign certificat from {vm_name}')
            if vm_name == "vmanage":
                self.get_controllers_csr_cert(self.controllers[vm_name].sys_ip, vm_name, self.vm_mgmt_ip, self.vm_user, self.vm_pass)
            else:
                self.get_controllers_csr_cert(self.controllers[vm_name].vpn0_ip, vm_name, self.vm_mgmt_ip, self.vm_user, self.vm_pass)
        # Enable transport tunnel on controllers
        self.__logger.info(f"[orange1]Enable transport on controllers")
        for vm_name in self.controllers:
            self.__logger.debug(f'[magenta]Send command to {vm_name}')
            gen_config = self.get_enable_conf(enable_tunnel, self.controllers[vm_name])
            self.__logger.info(gen_config)
            self.send_command_to_device(self.controllers[vm_name].mgmt_ip, gen_config.split("\n"), self.vm_user, self.vm_pass)

    def get_controllers_csr_cert(self, client_ip, cntrl_type, vm_mgmt_host, vm_user, vm_pass):
        auth = Authentication(host=vm_mgmt_host, user=vm_user, password=vm_pass).login()
        cert = Certificate(auth, vm_mgmt_host)
        self.__logger.info(f'Get CSR certificate for {client_ip}')
        cert_csr = cert.generate_csr(client_ip)
        with open(f'{self.cert_path}/{cntrl_type}.csr', mode="w") as fn:
            fn.write(cert_csr)
        self.openssl(
            'x509',
            '-req',
            '-in',
            f'{self.cert_path}/{cntrl_type}.csr',
            '-CA',
            f'{self.cert_path}/{self.rootca_name}',
            '-CAkey',
            f'{self.cert_path}/CA.key',
            '-CAcreateserial',
            '-out',
            f'{self.cert_path}/{cntrl_type}.crt',
            '-days',
            '2000',
            '-sha256',
        )
        # cn.log(cert_csr)
        self.__logger.info(f'Write CRT to file [green]{cntrl_type}.crt')
        with open(f'{self.cert_path}/{cntrl_type}.crt', mode="r") as fn:
            cert_crt = fn.read()
        self.__logger.info(f'Install CRT certificate [green]{cntrl_type}.crt to {client_ip}')
        cert.install_device_cert(cert_crt)

    def __add_controller_to_vmanager(self, client_ip, cntrl_type):
        dev_descr = {"deviceIP": client_ip, "username": self.vm_user, "password": self.vm_pass, "personality": cntrl_type, "generateCSR": False}
        self.http_request('/dataservice/system/device', 'post', val_json=json.dumps(dev_descr))
        # device_url = self.base_url + '/dataservice/system/device'
        # # device_url = base_url + '/dataservice/system/device/controllers'
        # self.__logger.debug(f'device url: {device_url}')
        # self.__logger.debug(f'device descr: {dev_descr}')
        # self.__logger.debug(f'{self.vm_sess_api.headers}')
        # response = self.vm_sess_api.post(url=device_url, data=json.dumps(dev_descr), verify=False)

        # if response.status_code == 200:
        #     self.__logger.debug(json.dumps(response.json(), indent=4))
        #     self.__logger.info(f"{cntrl_type} added successful")
        # else:
        #     self.__logger.info(f"{cntrl_type} Failed added to vmanage ")
        #     exit()

    def sync_root_cert(self):
        res = self.http_request('/dataservice/system/device/sync/rootcertchain', 'get')
        # device_url = self.base_url + '/dataservice/system/device/sync/rootcertchain'
        # # device_url = base_url + '/dataservice/system/device/controllers'
        # self.__logger.info(f'device url: {device_url}')
        # self.__logger.debug(f'{self.vm_sess_api.headers}')
        # response = self.vm_sess_api.get(url=device_url, verify=False)

        # self.__logger.info(f'Response code: {response.status_code}')
        # # print(f'response: {response.content}')

        if res.status_code != 200:
            self.__logger.error("[red]Failed to sync root certificate ")
            exit()

    def __set_vmanage_setting(self):
        auth = Authentication(host=self.vm_mgmt_ip, user=self.vm_user, password=self.vm_pass).login()
        with open(f'{self.cert_path}/{self.rootca_name}', "r") as fn:
            vmanage_cert_root = fn.read()
        vm_setting = Settings(auth, self.vm_mgmt_ip)
        if vm_setting.get_vmanage_org() != self.org.strip():
            vm_setting.set_vmanage_org(self.org)
        if vm_setting.get_vmanage_ca_type() != "enterprise":
            vm_setting.set_vmanage_ca_type("enterprise")
        vm_setting.set_vmanage_root_cert(vmanage_cert_root)
        vm_setting.set_vmanage_vbond(self.vm_bond_vpn0_ip)
        self.__logger.info(vm_setting.get_vmanage_ca_type())
        self.__logger.info(vm_setting.get_vmanage_org())
        self.__logger.info(vm_setting.get_vmanage_vbond())
        self.__logger.info(vm_setting.get_vmanage_ca_type())

    def __copy_cert_root_to_controller(self, client_ip, src_file_copy, dst_file_copy, vm_user, vm_pass):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(client_ip, 22, vm_user, vm_pass)
        # scp = SCPClient(ssh.get_transport())
        self.__logger.info(f"Copy rootCA to {client_ip}")
        with SCPClient(client.get_transport()) as scp:
            scp.put(src_file_copy, dst_file_copy)
        client.close()

    def send_command_to_device(self, client_ip, list_commands, vm_user, vm_pass, exp_str="\#", delay_factor=1):
        # logging.getLogger('netmiko').propagate = False
        # netmiko.log.setLevel(logging.ERROR)
        logging.getLogger('netmiko').setLevel(logging.CRITICAL)
        dict_netmiko = dict()
        dict_netmiko["ip"] = client_ip
        dict_netmiko["device_type"] = "cisco_ios"
        dict_netmiko["username"] = self.vm_user
        dict_netmiko["password"] = self.vm_pass
        # dict_netmiko["allow_auto_change"] = True
        dict_netmiko["global_delay_factor"] = delay_factor
        # dict_netmiko["cmd_verify"] = False
        return_message = ""
        self.__logger.debug(f'Send commands to ip: [magenta]{client_ip}')
        try:
            id_ssh = netmiko.ConnectHandler(**dict_netmiko)
            id_ssh.read_channel()
            for cmd in list_commands:
                if len(cmd.strip()) == 0:
                    continue
                self.__logger.debug(f'Send command: [magenta]{cmd}')
                # cmd_return = id_ssh.send_command(cmd, expect_string="\?")

                # cmd_return = id_ssh.send_command(cmd, expect_string=exp_str)
                cmd_return = id_ssh.send_command(cmd, expect_string=exp_str)
                # , cmd_verify=False
                self.__logger.debug(f'return: [magenta]{cmd_return}')
                if len(cmd_return.strip()) > 0:
                    self.__logger.debug(f'cmd_return is > 0')
                    return_message += "{}\n".format(cmd_return)
                if exp_str != "\#":
                    self.__logger.debug(f'exp_str not equal #')
                    cmd_return = id_ssh.send_command("\n", expect_string="\#")
        except Exception as error:
            return_message += "!#host_error:{}\n".format(client_ip)
            return_message += "{}\n".format(error)
            if re.search("timed-out", str(error)):
                return return_message
            else:
                return_message += "!#host_error:{}\n".format(client_ip)
                return_message += "{}\n".format(error)
            self.__logger.error(f'[red]{return_message}')
        else:
            if len(return_message.strip()) > 0:
                self.__logger.debug(f'[green]{return_message.strip()}')
        id_ssh.disconnect()
        return return_message

    def import_templates(self):
        for vp_template in self.templates:
            self.__logger.info(f"[orange1]Import template name: '{vp_template.name}' type: '{vp_template.t_type}' scope: '{vp_template.t_scope}'[/]")
            self.__logger.debug(f"{vp_template}")
            if vp_template.t_scope == 'vpn_cfg':
                gn_template = self.__gen_template("template_feature_vpn.j2", vp_template)
            elif vp_template.t_scope == 'vpn_interfaces':
                gn_template = self.__gen_template("template_feature_interfaces.j2", vp_template)
            elif vp_template.t_scope == 'aaa':
                gn_template = self.__gen_template("template_feature_aaa.j2", vp_template)
            self.__logger.debug(f"{gn_template}")
            # with open("test.json", mode='w') as fn:
            #     fn.write(gn_template)
            self.http_request('/dataservice/template/feature/', 'post', val_json=gn_template)
            # self.__logger.debug(f'device url: {device_url}')

            # response = self.vm_sess_api.post(url=device_url, data=gn_template, verify=False)

            # if response.status_code == 200:
            #     self.__logger.info(json.dumps(response.json(), indent=4))
            #     self.__logger.info(f"Template added successful")
            # else:
            #     self.__logger.debug(json.dumps(response.json(), indent=4))
            #     if 'error' in response.json():
            #         self.__logger.error(response.json()['error']['details'])
            #     self.__logger.error(f"Template Failed added to vmanage ")

        # self.__logger.info(f"{json.dumps(tmp_cont, indent=4)}")

    def __gen_template(self, t_name, vm_val):
        self.__logger.info(f'Generate template {t_name} ')
        src_dir = os.path.dirname(os.path.realpath(__file__))
        self.__logger.debug(f'Source dir: {src_dir}')
        file_loader = FileSystemLoader(src_dir)
        env = Environment(loader=file_loader)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        # env.filters['ipaddr'] = self.ipaddr
        template = env.get_template(t_name)
        ret_config = template.render(val=vm_val)
        self.__logger.debug(f'{ret_config}')
        return ret_config

    def http_request(self, add_url, val_action, val_json=""):
        device_url = self.base_url + add_url
        self.__logger.debug(f'device url: {device_url}')
        response = ""
        if val_action == 'post':
            response = self.vm_sess_api.post(url=device_url, data=val_json, verify=False)
        elif val_action == 'get':
            response = self.vm_sess_api.get(url=device_url, verify=False)
        else:
            self.__logger.error("Did find action put/get/post ")
            exit()
        if response.status_code == 200:
            self.__logger.debug(json.dumps(response.json(), indent=4))
            self.__logger.info(f"HTTP request to vmanage successful")
        else:
            self.__logger.debug(json.dumps(response.json(), indent=4))
            if 'error' in response.json():
                self.__logger.error(response.json()['error']['details'])
            self.__logger.error(f"HTTP request to vmanage Failed ")
        return response

    def __str__(self):
        st = f"""
        org: {self.org}
        vm_user: {self.vm_user}
        vm_pass: {self.vm_pass}
        site_id: {self.site_id}
        cert_path: {self.cert_path}
        gen_rootca: {self.gen_rootca}
        base_url: {self.base_url}
        """
        return st
