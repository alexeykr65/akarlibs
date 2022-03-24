#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for extract information from openstack
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
import sys
import ipdb
import openstack
from openstack.config import loader
from pythonping import ping
from collections import OrderedDict

import json
import re
import base64
import logging
from jinja2 import Template, Environment, BaseLoader
from .akarlogging import AkarLogging
from .kvmlibvirt import KvmInstanceInfo, KvmInterfaceInfo
from datetime import datetime, timedelta
import socket
import time


ansible_template = """---
all:
  hosts:
{% for srv in srvs %}
    {{ srv }}:
      ansible_host: {{ srvs[srv].ipv4 }}
{% endfor %}
  vars:
    ansible_user: root
    ansible_ssh_private_key_file: '~/.ssh/id_rsa'
    ansible_network_os: ios
    ansible_connection: network_cli
    ansible_python_interpreter: "/usr/bin/env python"
"""


class TimedOut(Exception):
    pass


class FlavorInfo:
    """ Class of Flavors """

    def __init__(self, name, flavor_id, ram, disk, vcpus):
        self.name = name
        self.flavor_id = flavor_id
        self.ram = ram
        self.disk = disk
        self.vcpus = vcpus

    def __str__(self):
        msg = f'{self.flavor_id:5s} {self.name:20s} {self.vcpus:4d} {self.ram:7d} {self.disk:4d}'
        return msg


class Flavors:
    """ List of flavors """

    def __init__(self, conn):
        self.flavors = dict()
        self.conn = conn
        self.get_flavors()

    def __str__(self):
        msg = '{:*^5s} {:*^20s} {:*^4s} {:*^7s} {:*^4s}\n'.format("ID", "NAME", "VCPU", "RAM", "DISK")
        for flv_name, flavor in self.flavors.items():
            msg += f'{str(flavor)}\n'
        return msg

    def get_flavors(self):
        for flavor in self.conn.compute.flavors():
            flv = FlavorInfo(name=flavor.name, flavor_id=flavor.id, vcpus=flavor.vcpus, ram=flavor.ram, disk=flavor.disk)
            self.flavors[flavor.name] = flv
            # print(flavor)


class ImageInfo:
    """ Class of image """

    def __init__(self, name, image_id, size, container_format, disk_format, metadata=''):
        self.name = name
        self.image_id = image_id
        self.size = size / 1048576
        self.container_format = container_format
        self.disk_format = disk_format
        self.metadata = metadata

    def __str__(self):
        msg = f' {self.name:30s}{self.image_id:38s}{self.size:8.0f}M' f' {self.container_format:5s} {self.disk_format:5s} {self.metadata}'
        return msg


class Images:
    """ List of images """

    def __init__(self, conn):
        self.images = dict()
        self.conn = conn
        self._get_images()

    def _get_images(self):
        for image in self.conn.image.images():
            img = ImageInfo(
                name=image.name,
                image_id=image.id,
                size=image.size,
                container_format=image.container_format,
                disk_format=image.disk_format,
                metadata=image.metadata,
            )
            self.images[image.name] = img
        for image in self.conn.compute.images():
            self.images[image.name].metadata = image.metadata
            # print(f'metadata: {image.metadata}')

    def __str__(self):
        msg = '{:*^30s} {:*^38s} {:*^8s} {:*^7s} {:*^7s}\n'.format("NAME", "ID", "SIZE", "CONT.FORMAT", "METADATA")
        for key, img in self.images.items():
            msg += f'{str(img)}\n'
        return msg


class ServerInfo:
    """ Class of Server """

    def __init__(self, srv, nets="", img_name="", metdata="", dbg=logging.INFO):
        self.__logger = AkarLogging(dbg, "OS ServerInfo").get_color_logger()
        self.__logger.debug("Create ServerInfo ...")
        self.name = srv.name
        self.server_id = srv.id
        self.flavor = srv.flavor['original_name']
        self.status = srv.vm_state
        self.host = srv.hypervisor_hostname
        self.hostname = srv.hostname
        self.instance = srv.instance_name
        # tm_creted = srv.created_at
        self.time_created = (datetime.strptime(str(srv.created_at), "%Y-%m-%dT%H:%M:%SZ")).strftime("%d %b %Y %H:%M")

        # dt_obj.strftime("%d.%m.%Y %H:%M")
        # self.time_created = srv.created_at
        # ipdb.set_trace()
        self.nets = nets
        self.float_ip = ""
        self.fixed_ip_address = ""
        self.image_name = img_name
        self.mgmt_name = list(nets.keys())[0]
        self.mgmt_ip = nets[self.mgmt_name]['ipv4']
        self.srv_group = srv.metadata.get('group') or ""
        self.ansible_name = srv.metadata.get('ansible_name') or ""
        self.name_intrf = srv.metadata.get('name_intrf') or ""
        self.platform = srv.metadata.get('platform') or ""
        self.img_metadata = metdata.metadata
        # print(f'metdata: {self.img_metadata}')
        # if len(srv.metadata) > 0:
        #     # print(f'name: {self.name} metdata: {srv.metadata}')
        #     self.srv_group = srv.metadata['group']
        #     self.ansible_name = srv.metadata['ansible_name']
        self.srv_metadata = srv.metadata

        self.uri_qemu = f"qemu+ssh://root@{self.host}/system?socket=/var/run/libvirt/libvirt-sock"
        self.__logger.debug(f'URI:{self.uri_qemu}')
        if self.status == "active":
            self.kvminfo = KvmInstanceInfo(uri_qemu=self.uri_qemu, name_instance=self.instance, dbg=logging.WARNING)
        else:
            self.__logger.error(f'Status vm {self.name}: {self.status}')
            self.kvminfo = None
            exit(1)
        self.__logger.debug(f'{self.kvminfo.xml}')
        # self.__get_kvminfo()

    def __str__(self):
        # {self.server_id:38s}
        msg = (
            f'Name: {self.name:10s} Flavor: {self.flavor:15s}'
            f'Stat: {self.status:3s} Host: {self.host:4s} Instance: {self.instance:15s} HName: {self.hostname:10s}'
            f'Net: {self.nets} Float_ip: {self.float_ip} Ips: {self.fixed_ip_address}'
        )
        return msg

    def __get_kvminfo(self):
        pass


# class InstanceInfo:
#     """ Class of Instance KVM  """

#     def __init__(self, name="", id="", flavor="", nets="", status="", host="", hostname="", instance=""):
#         self.name = name
#         self.inst_id = id
#         self.flavor = flavor
#         self.status = status
#         self.host = host
#         self.hostname = hostname
#         self.instance = instance
#         self.nets = nets
#         self.float_ip = ""
#         self.fixed_ip_address = ""


class Servers:
    """ List of Servers """

    def __init__(self, cloud='ops_work', name="", name_underline=True, dbg=logging.WARNING):
        self.servers = list()
        self.dbg = dbg
        if name_underline:
            self.name = f'{name}_'
        else:
            self.name = name
        self.cloud = cloud
        self.config = loader.OpenStackConfig()
        self.conn = openstack.connect(cloud=self.cloud)
        # kvminfo = kv.KvmInstanceInfo(uri_qemu=uri_qemu, name_instance=srv.instance)
        self.__logger = AkarLogging(dbg, "OS Servers").get_color_logger()
        self.__get_info_servers()
        self.__logger.debug(f'Total found servers: {len(self.servers)}')
        self.__get_info_ips()
        self.__logger.info(f'Stack: {name} Total servers: {len(self.servers)}')
        # self.im = Images(self.conn)

    def __str__(self):
        msg = ""
        for srv in self.servers:
            msg += f'{str(srv)}\n'
        return msg

    def __get_info_servers(self):
        self.__logger.debug(f'Find servers ... ')
        if self.name:
            # print(f'name: {self.name}')
            for server in self.conn.compute.servers(name=self.name):
                # print(f'{server.name}  id: {server.id}')
                # print(self.conn.compute.get_server_metadata(server))
                # print(json.dumps(server, indent=2))
                # print(f'metadata: {server.metadata}')
                if server.vm_state == "active":
                    self.__add_server_info(server)
        else:
            for server in self.conn.compute.servers():
                # print(f'{server.name}  id: {server.id}')
                # print(self.conn.compute.get_server_metadata(server))
                # print(json.dumps(server, indent=2))
                if server.vm_state == "active":
                    self.__add_server_info(server)

    def __add_server_info(self, srv):
        self.__logger.debug("Add found server to list ... ")
        nets = dict()
        # ipdb.set_trace()
        for key, net in srv.addresses.items():
            # print(f'Key: {key} Net: {net}')
            nets[key] = dict()
            for nt in net:
                if nt['version'] == 4:
                    nets[key]['ipv4'] = nt['addr']
                elif nt['version'] == 6:
                    nets[key]['ipv6'] = nt['addr']
        # print(f'Net: {nets}')
        #

        img = self.conn.image.find_image(srv.image["id"])
        metdata = self.conn.compute.get_image_metadata(srv.image["id"])
        # print(f'image metadata: {metadt.metadata}')
        # if 'ssh_user' in metadt.metadata:
        #     print(f'name: {nm.name} image metadata: {metadt.metadata["ssh_user"]}')
        img_name = ""
        if img:
            img_name = img.name
            # tt = self.conn.image.get_image_metadata(srv.image["id"])

            # print(f'image metadata: {tt}')
        # print(f'Running: {srv.vm_state}')
        # print(f'{img.name}')
        # dict(net[0])['addr']
        self.servers.append(
            ServerInfo(
                srv,
                nets=nets,
                img_name=img_name,
                metdata=metdata,
                dbg=self.dbg,
            )
        )

    def __get_info_ips(self):
        self.__logger.debug("Analyze information about network ... ")
        for fl in self.conn.list_floating_ips():
            # print(f'list ips: {fl}')
            if fl.port_details:
                self.__logger.info(f'Port: {fl.port_details["device_id"]}')
                for srv in self.servers:
                    print(f'list srv: {srv}')
                    if fl.port_details['device_id'] == srv.server_id:
                        srv.float_ip = fl.floating_ip_address
                        srv.fixed_ip_address = fl.fixed_ip_address

    def get_srv_nets(self, net_name):
        self.__logger.info("Get list servers with ip addresses ... ")
        srv_ips = dict()
        self.__logger.info(f'Total srvs: {len(self.servers)}')

        for srv in self.servers:
            user_name = 'root'
            net_os = ""
            self.__logger.debug(f'list_servers: {srv}')
            self.__logger.info(f'srv: {srv.name}  net: {net_name} ipv4: {srv.nets[net_name]}')

            if re.search(r'bond|smart|vmanage|edge|cedge', srv.image_name):
                user_name = 'admin'
            if 'ssh_user' in srv.img_metadata:
                # print(f'met: {srv.img_metadata["ssh_user"]}')
                user_name = srv.img_metadata["ssh_user"]
            if 'net_os' in srv.img_metadata:
                # print(f'met: {srv.img_metadata["ssh_user"]}')
                net_os = srv.img_metadata["net_os"]
            srv_ips[srv.name] = {'ipv4': srv.nets[net_name]['ipv4'], 'user': user_name, 'group': srv.srv_group, 'net_os': net_os}
            if 'ansible_connection' in srv.img_metadata:
                # print(f'met: {srv.img_metadata["ssh_user"]}')
                srv_ips[srv.name]['ansible_connection'] = srv.img_metadata["ansible_connection"]

        # logger.info(srv_ips)
        # ipdb.set_trace()
        return OrderedDict(sorted(srv_ips.items()))

    def create_ansible_hosts(self, net_name):
        self.__logger.info("Create file ansible hosts ... ")
        env = Environment(loader=BaseLoader).from_string(ansible_template)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        srvs = self.get_srv_nets(net_name)
        self.__logger.info(f'servers: {srvs}')
        ans_result = env.render(srvs=self.get_srv_nets(net_name))
        with open("hosts-example.yml", mode='w') as fn:
            fn.write(ans_result)
        self.__logger.info(ans_result)

    # print(apple_script)

    def get_srv_labs(self, net_name):
        self.__logger.info("Get list servers with ip addresses ... ")
        srv_ips = dict()
        self.__logger.info(f'Total srvs: {len(self.servers)}')

        for srv in self.servers:
            user_name = 'root'
            net_os = ""
            self.__logger.debug(f'list_servers: {srv}')
            self.__logger.info(f'srv: {srv.name}  net: {net_name} ipv4: {srv.nets[net_name]}')
            ind = 1
            for n, val in srv.nets.items():
                self.__logger.info(f'Interface: {srv.name_intrf} {ind} nets: {val["ipv4"]}')
                ind += 1
            if re.search(r'bond|smart|vmanage|edge|cedge', srv.image_name):
                user_name = 'admin'
            srv_ips[srv.ansible_name] = {'ipv4': srv.nets[net_name]['ipv4'], 'groups': srv.srv_group.split(',')}
            srv_ips[srv.ansible_name]['platform'] = srv.platform
            if 'ansible_connection' in srv.img_metadata:
                # print(f'met: {srv.img_metadata["ssh_user"]}')
                srv_ips[srv.ansible_name]['ansible_connection'] = srv.img_metadata["ansible_connection"]
            srv_ips[srv.ansible_name]['connection_options'] = {}

        # logger.info(srv_ips)
        # ipdb.set_trace()
        return OrderedDict(sorted(srv_ips.items()))

    def create_dynamic_inventory(self, net_name):
        self.__logger.info("Create dynamic ansible hosts ... ")
        srvs = self.get_srv_nets(net_name)
        self.__logger.info(f'servers: {srvs}')
        inv_json = dict()
        lst_rtrs = list()
        lst_srvs = list()
        inv_meta = dict()
        self.__logger.debug(f'{srvs}')
        inv_json['_meta'] = dict()
        inv_json['all'] = dict()
        inv_json['all']['children'] = list()
        inv_json['all']['hosts'] = list()
        for srv in srvs:
            self.__logger.debug(f'SRV: {srv}')
            if len(srvs[srv]['group']) > 0:
                self.__logger.debug(f'{srvs[srv]["group"]}')
                srv_group = dict()
                srv_group[srvs[srv]['group']] = dict()
                srv_group[srvs[srv]['group']]['hosts'] = list()
                if srvs[srv]['group'] not in inv_json['all']['children']:
                    inv_json['all']['children'].append(srvs[srv]['group'])
                inv_json[srvs[srv]['group']] = dict()
                inv_json[srvs[srv]['group']]['hosts'] = list()
        # print(f'{json.dumps(inv_json, indent=4)}')
        for srv in srvs:
            nick_srv = str(srv)
            # print(f'srv: {nick_srv} net_os: { srvs[srv]["net_os"] }')
            if srvs[srv]["net_os"] != "win":
                if re.search(r'[^R]*(R\d+)', str(srv)):
                    nick_srv = re.search(r'[^R]*(R\d+)', str(srv)).group(1)
                    self.__logger.info(f'srv: {srv} , nick_srv: {nick_srv}')
                elif re.search(r'SRV', str(srv)):
                    nick_srv = re.search(r'[^(SRV)]*(SRV\d+)', str(srv)).group(1)
                    self.__logger.info(f'srv: {srv} , nick_srv: {nick_srv}')
                elif re.search(r'_', str(srv)):
                    nick_srv = str(srv).split('_')[1]
                    self.__logger.info(f'srv: {srv} , nick_srv: {nick_srv}')
                inv_meta[nick_srv] = dict()
                inv_meta[nick_srv]['ansible_host'] = srvs[srv]['ipv4']
                inv_meta[nick_srv]['ansible_user'] = srvs[srv]['user']
                inv_meta[nick_srv]['net_os'] = srvs[srv]['net_os']
                if 'ansible_connection' in srvs[srv]:
                    inv_meta[nick_srv]['ansible_connection'] = srvs[srv]['ansible_connection']
                # inv_json['all']['hosts'].append(nick_srv)
                # print(f'nick: {nick_srv}')
                inv_json[srvs[srv]['group']]['hosts'].append(nick_srv)
        # inv_json['routers'] = dict()
        if len(inv_json['all']['children']) <= 0:
            inv_json['all']['hosts'].append('localhost')
            # print(f'nick: {inv_json["all"]["hosts"]}')

        inv_json['all']['vars'] = {
            "ansible_user": "root",
            "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
            "ansible_connection": "network_cli",
            "ansible_network_os": "ios",
            "netconf_template_os": "ios",
            "ansible_python_interpreter": "/usr/bin/env python3",
        }
        #             "ansible_connection": "network_cli",
        #             "ansible_network_os": "ios",
        # inv_json['servers'] = dict()
        # inv_json['servers']['hosts'] = lst_srvs
        # inv_json['servers']['vars'] = {
        #     "ansible_user": "root",
        #     "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
        #     "ansible_connection": "ssh",
        #     "ansible_python_interpreter": "/usr/bin/env python3",
        # }
        inv_json['_meta']['hostvars'] = inv_meta
        self.__logger.info(json.dumps(inv_json, indent=2))
        print(json.dumps(inv_json, indent=2))

    def check_hosts_online(self):
        self.__logger.info(f"Wait for connections to hosts ...")
        for srv in self.servers:
            # print(f'nets: {srv.mgmt_name} = {srv.mgmt_ip}')
            self.wait_for_connection(host=srv.mgmt_ip)

    def wait_for_connection(self, port: int = 22, delay: int = 0, timeout: int = 600, interval: int = 1, host: str = None):
        end_time = datetime.now() + timedelta(seconds=timeout) + timedelta(seconds=delay)
        time.sleep(delay)
        while datetime.now() < end_time:
            s = socket.socket()
            s.settimeout(5)
            try:
                status = s.connect_ex((host, port))
                if status == 0:
                    self.__logger.info(f"{host} is online")
                    return 0
                else:
                    time.sleep(interval)
            except (socket.gaierror, socket.timeout, socket.error) as e:
                print(e)
            finally:
                s.close()
        raise TimedOut("Timed out waiting for: {}".format(host))


class NetInfo:
    def __init__(self, name, net_id, state, sec, provider_type, phys_net):
        # , provider_type, phys_net, mtu
        self.name = name
        self.net_id = net_id
        self.admin_state = state
        self.security = sec
        self.provider_type = provider_type
        self.phys_net = phys_net
        # self.mtu = mtu

    def __str__(self):
        return f'{self.name:10s} {self.net_id:38s} {self.admin_state!s:5s} {self.security!s:5s}' f'  {self.provider_type!s:10s} {self.phys_net}'


class Networks:
    def __init__(self, conn):
        self.conn = conn
        self.nets = dict()
        self.get_nets()

    def get_nets(self):
        for net in self.conn.network.networks():
            # print(f'Admin_state: {net.id}')
            # print(json.dumps(net, indent=2))
            self.nets[net.name] = NetInfo(
                name=net.name,
                net_id=net.id,
                state=net.is_admin_state_up,
                sec=net.is_port_security_enabled,
                provider_type=net.provider_network_type,
                phys_net=net.provider_physical_network,
            )

    def __str__(self):
        msg = f'{"NAME":*^10s} {"ID":*^38s} {"ADST":*^5s}{"SEC":*^5s} {"PROV_TYPE":*^10s} {"PHYS_NET":*^10s}\n'
        for key, net in sorted(self.nets.items()):
            msg += f'{str(net)}\n'
        return msg


class Stack:
    """ List of Servers """

    def __init__(self, cloud='ops_work', name="", template_file="", dbg=logging.INFO):
        self.__logger = AkarLogging(dbg, "OS Stack").get_color_logger()
        self.dbg = dbg
        self.name = name
        self.template_file = template_file
        self.timeout = 3600
        self.cloud = cloud
        self.rollback = False
        parameters = dict(default={}, type='dict')
        self.__logger.info(f'Name stack: {self.name} Template file: {self.template_file}')
        self.config = loader.OpenStackConfig()
        self.conn = openstack.connect(cloud=self.cloud)
        self.__logger.info(f'Openstack connected successful')

    def check_status_stack(self):
        # kvminfo = kv.KvmInstanceInfo(uri_qemu=uri_qemu, name_instance=srv.instance)
        self.__logger.info(f'Check stack name: {self.name} ')
        stack = self.conn.get_stack(self.name)
        if stack:
            stat = stack.stack_status
        else:
            stat = ""
        return stat

    def create_stack(self):
        stat = self.check_status_stack()

        if stat == "":
            self.__logger.info(f'Stack not exist and create stack: {self.name} ')
            stack = self.conn.create_stack(self.name, template_file=self.template_file, rollback=self.rollback, wait=True)
            stack = self.conn.get_stack(stack.id, None)
            self.__logger.info(f'Status created stack: {stack.stack_status} ')
        else:
            self.__logger.info(f'Stack {self.name} exist')
        # self.im = Images(self.conn)


#  self.conn.create_stack(
#             self.params['name'],
#             template_file=self.params['template'],
#             environment_files=self.params['environment'],
#             timeout=self.params['timeout'],
#             wait=True,
#             rollback=self.params['rollback'],
#             **parameters)
