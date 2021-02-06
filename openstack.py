#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for extract information from openstack
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
import sys
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
        self.size = size/1048576
        self.container_format = container_format
        self.disk_format = disk_format
        self.metadata = metadata

    def __str__(self):
        msg = (
            f' {self.name:30s}{self.image_id:38s}{self.size:8.0f}M'
            f' {self.container_format:5s} {self.disk_format:5s} {self.metadata}'
        )
        return msg


class Images:
    """ List of images """

    def __init__(self, conn):
        self.images = dict()
        self.conn = conn
        self._get_images()

    def _get_images(self):
        for image in self.conn.image.images():
            img = ImageInfo(name=image.name, image_id=image.id, size=image.size,
                            container_format=image.container_format, disk_format=image.disk_format,
                            metadata=image.metadata)
            self.images[image.name] = img
        for image in self.conn.compute.images():
            self.images[image.name].metadata = image.metadata

    def __str__(self):
        msg = '{:*^30s} {:*^38s} {:*^8s} {:*^7s} {:*^7s}\n'.format("NAME", "ID", "SIZE", "CONT.FORMAT", "METADATA")
        for key, img in self.images.items():
            msg += f'{str(img)}\n'
        return msg


class ServerInfo:
    """ Class of Server """

    def __init__(self, name="", id="", flavor="", nets="", status="", host="", hostname="", instance=""):
        self.name = name
        self.server_id = id
        self.flavor = flavor
        self.status = status
        self.host = host
        self.hostname = hostname
        self.instance = instance
        self.nets = nets
        self.float_ip = ""
        self.fixed_ip_address = ""

    def __str__(self):
        # {self.server_id:38s}
        msg = (
            f'{self.name:10s} {self.flavor:15s}'
            f'{self.status:3s} {self.host:4s} {self.instance:15s} {self.hostname:10s}'
            f' {self.nets} {self.float_ip} {self.fixed_ip_address}'
        )
        return msg


class InstanceInfo:
    """ Class of Instance KVM  """

    def __init__(self, name="", id="", flavor="", nets="", status="", host="", hostname="", instance=""):
        self.name = name
        self.inst_id = id
        self.flavor = flavor
        self.status = status
        self.host = host
        self.hostname = hostname
        self.instance = instance
        self.nets = nets
        self.float_ip = ""
        self.fixed_ip_address = ""

class Servers:
    """ List of Servers """

    def __init__(self, cloud='ops_work', name="", dbg=logging.WARNING):
        self.servers = list()
        self.name = name
        self.cloud = cloud
        self.config = loader.OpenStackConfig()
        self.conn = openstack.connect(cloud=self.cloud)
        self.__logger = AkarLogging(dbg, "openstacklab").get_color_logger()
        self.__get_info_servers()
        self.__logger.info(f'Total found servers: {len(self.servers)}')
        self.__get_info_ips()
        self.__logger.info(f'Initilized and total found servers: {len(self.servers)}')

    def __str__(self):
        msg = ""
        for srv in self.servers:
            msg += f'{str(srv)}\n'
        return msg

    def get_srv_nets(self, net_name):
        self.__logger.info("Get list servers with ip addresses ... ")
        srv_ips = dict()
        for srv in self.servers:
            self.__logger.info(f'srv: {srv.name}  net: {net_name} ipv4: {srv.nets[net_name]}')
            srv_ips[srv.name] = {'ipv4': srv.nets[net_name], 'user': 'root'}
        # logger.info(srv_ips)
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

    def create_dynamic_inventory(self, net_name):
        self.__logger.info("Create dynamic ansible hosts ... ")
        srvs = self.get_srv_nets(net_name)
        self.__logger.info(f'servers: {srvs}')
        inv_json = dict()
        lst_srvs = list()
        inv_meta = dict()
        inv_json['_meta'] = dict()
        inv_json['all'] = dict()
        for srv in srvs:
            if re.search(r'[^R]*(R\d+)', str(srv)):
                nick_srv = re.search(r'[^R]*(R\d+)', str(srv)).group(1)
                self.__logger.info(f'srv: {srv} , nick_srv: {nick_srv}')
                lst_srvs.append(nick_srv)
                inv_meta[nick_srv] = dict()
                inv_meta[nick_srv]['ansible_host'] = srvs[srv]['ipv4']
        inv_json['all']['hosts'] = lst_srvs
        inv_json['all']['vars'] = {
            "ansible_user": "root",
            "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
            "ansible_network_os": "ios",
            "ansible_connection": "network_cli",
            "ansible_python_interpreter": "/usr/bin/env python3"
        }
        inv_json['_meta']['hostvars'] = inv_meta
        self.__logger.info(json.dumps(inv_json, indent=2))
        print(json.dumps(inv_json, indent=2))

    def __get_info_servers(self):
        self.__logger.info(f'Find servers ... ')
        if self.name:
            for server in self.conn.compute.servers(name=self.name):
                # print(f'{server.name}  id: {server.id}')
                # print(self.conn.compute.get_server_metadata(server))
                # print(json.dumps(server, indent=2))
                self.__add_server_info(server)
        else:
            for server in self.conn.compute.servers():
                # print(f'{server.name}  id: {server.id}')
                # print(self.conn.compute.get_server_metadata(server))
                # print(json.dumps(server, indent=2))
                self.__add_server_info(server)

    def __add_server_info(self, srv):
        self.__logger.info("Add found server to list ... ")
        nets = dict()
        for key, net in srv.addresses.items():
            nets[key] = net[0]['addr']
            # dict(net[0])['addr']
        self.servers.append(ServerInfo(name=srv.name, id=srv.id,
                                       nets=nets,
                                       flavor=srv.flavor['original_name'],
                                       status=srv.host_status,
                                       host=srv.hypervisor_hostname,
                                       hostname=srv.hostname,
                                       instance=srv.instance_name
                                       ))

    def __get_info_ips(self):
        self.__logger.info("Analyze information about network ... ")
        for fl in self.conn.list_floating_ips():
            # print(f'list ips: {fl}')
            if fl.port_details:
                self.__logger.info(f'Port: {fl.port_details["device_id"]}')
                for srv in self.servers:
                    print(f'list srv: {srv}')
                    if fl.port_details['device_id'] == srv.server_id:
                        srv.float_ip = fl.floating_ip_address
                        srv.fixed_ip_address = fl.fixed_ip_address


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
        return (
            f'{self.name:10s} {self.net_id:38s} {self.admin_state!s:5s} {self.security!s:5s}'
            f'  {self.provider_type!s:10s} {self.phys_net}'
        )


class Networks:

    def __init__(self, conn):
        self.conn = conn
        self.nets = dict()
        self.get_nets()

    def get_nets(self):
        for net in self.conn.network.networks():
            # print(f'Admin_state: {net.id}')
            # print(json.dumps(net, indent=2))
            self.nets[net.name] = NetInfo(name=net.name, net_id=net.id, state=net.is_admin_state_up,
                                          sec=net.is_port_security_enabled, provider_type=net.provider_network_type,
                                          phys_net=net.provider_physical_network)

    def __str__(self):
        msg = f'{"NAME":*^10s} {"ID":*^38s} {"ADST":*^5s}{"SEC":*^5s} {"PROV_TYPE":*^10s} {"PHYS_NET":*^10s}\n'
        for key, net in sorted(self.nets.items()):
            msg += f'{str(net)}\n'
        return msg
