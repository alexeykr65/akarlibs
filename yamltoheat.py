#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for extract information from openstack
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
import sys
import yaml
import openstack
import os
import graphviz as gv
from netaddr import IPNetwork, IPAddress
from openstack.config import loader
from pythonping import ping


import json
import re
import base64
import logging
from jinja2 import Template, Environment, FileSystemLoader
from yamlinclude import YamlIncludeConstructor
from .akarlogging import AkarLogging


class LinkInfo:
    """ Class of Link """

    def __init__(self, name, num, val):
        self.name = name
        self.num = num
        self.ipv4 = ""
        self.ipv6 = ""
        self.dhcp_srv = False
        self.flag_create = False
        self.all_dvs = list()
        self.connected_link = ""
        if 'connected_link' in val:
            self.connected_link = val['connected_link']
        # print(f'{val}')
        if 'ipv4' in val:
            self.ipv4 = val['ipv4']
        if 'ipv6' in val:
            self.ipv6 = val['ipv6']
        if 'dhcp_srv' in val:
            self.dhcp_srv = val['dhcp_srv']

    def __str__(self):
        msg = f'{str(self.num):5s} {self.name:10s} {self.ipv4:20s} {self.ipv6:20s} dhcp:{self.dhcp_srv} conn_link:{self.connected_link}  AllDvs: {self.all_dvs}'
        return msg


class ImageInfo:
    """ Class of Router Info """

    def __init__(self, name, flavor_id="", image="", dev_type="routers", init_img="", name_intrf="", plat=""):
        self.name = name
        self.dev_type = dev_type
        self.flavor = flavor_id
        self.image = image
        self.init_img = init_img
        self.name_intrf = name_intrf
        self.platform = plat

    def __str__(self):
        msg = f'{self.name:10s} {self.dev_type:20s} {self.flavor:20s} {self.image:20s} {self.init_img:20s}'
        return msg


# class ImagesInfo:
#     """ Class of Images Info """

#     def __init__(self):
#         self.images = dict()

#     def add_img(self, name, flavor_id="", image="", type_dev="routers"):
#         self.images[name] = ImageInfo(name, flavor_id, image, type_dev)

#     def __str__(self):
#         msg = '{:*^5s} {:*^20s} {:*^4s} {:*^7s} {:*^4s}\n'.format("ID", "NAME", "VCPU", "RAM", "DISK")
#         for key, img_info in self.images.items():
#             msg += f'{str(img_info)}\n'
#         return msg


class RouterInfo:
    """ Class of Router Info """

    def __init__(self, name, val, net):
        self.name_router = name
        self.dev_type = val['type']
        self.links = dict()
        self.dev_name = name
        self.dev_group = ""
        self.dev_mgmt_ipv4 = ""
        self.dev_mgmt_ipv6 = ""
        self.dev_host = ""
        self.platform = ""
        if 'os_host' in val:
            self.dev_host = val['os_host']
        if 'group' in val:
            self.dev_group = val['group']
        if 'mgmt_ipv6' in val:
            self.dev_mgmt_ipv6 = val['mgmt_ipv6']
        if 'mgmt_ipv4' in val:
            self.dev_mgmt_ipv4 = val['mgmt_ipv4']
        if 'name' in val:
            self.dev_name = val['name']

        id_rtr = 100 + int(re.match(r'^[^\d]*(\d*)', self.name_router).group(1))
        count = 1
        for ln in val['links']:
            self.links[ln] = dict()
            self.links[ln]['name'] = "link_" + str(ln)
            self.links[ln]['connected_link'] = net[ln].connected_link
            self.links[ln]['count'] = str(count)
            net[ln].all_dvs.append({'name': self.name_router, 'dev_name': self.dev_name, 'intr': str(count)})
            if net[ln].ipv4:
                self.links[ln]['ipv4'] = net[ln].ipv4
                ip = str(IPNetwork(net[ln].ipv4)[id_rtr])
                self.links[ln]['ipv4_addr'] = ip
            if net[ln].ipv6:
                self.links[ln]['ipv6'] = net[ln].ipv6
                ip = str(IPNetwork(net[ln].ipv6)[id_rtr + 156])
                self.links[ln]['ipv6_addr'] = ip
                # print(f'{}')
            count += 1

    def __str__(self):
        msg = f'{self.name_router:10s} {self.dev_type:10s} LINKS: {str(self.links):20s} '
        return msg


class ServerInfo:
    """ List of Server Info """

    def __init__(self, name, val, net):
        self.name_srv = name
        self.dev_type = val['type']
        self.dev_name = name
        self.dev_group = ""
        self.dev_mgmt_ipv4 = ""
        self.dev_mgmt_ipv6 = ""
        self.dev_host = ""
        self.cloud_init_cloudconfig = ""
        if 'cloud_init' in val:
            if 'cloud_config' in val['cloud_init']:
                self.cloud_init_cloudconfig = val['cloud_init']['cloud_config'].split("\n")
        if 'os_host' in val:
            self.dev_host = val['os_host']
        if 'group' in val:
            self.dev_group = val['group']
        if 'mgmt_ipv6' in val:
            self.dev_mgmt_ipv6 = val['mgmt_ipv6']
        if 'mgmt_ipv4' in val:
            self.dev_mgmt_ipv4 = val['mgmt_ipv4']
        if 'name' in val:
            self.dev_name = val['name']
        self.links = dict()
        id_rtr = int(re.match(r'^[^\d]*(\d*)', self.name_srv).group(1))
        count = 1
        for ln in val['links']:
            self.links[ln] = dict()
            self.links[ln]['name'] = "link_" + str(ln)
            self.links[ln]['count'] = str(count)
            net[ln].all_dvs.append({'name': self.name_srv, 'dev_name': self.dev_name, 'intr': str(count)})
            if net[ln].ipv4:
                self.links[ln]['ipv4'] = net[ln].ipv4
                ip = str(IPNetwork(net[ln].ipv4)[id_rtr + 180])
                self.links[ln]['ipv4_addr'] = ip
            if net[ln].ipv6:
                self.links[ln]['ipv6'] = net[ln].ipv6
                ip = str(IPNetwork(net[ln].ipv6)[id_rtr + 512])
                self.links[ln]['ipv6_addr'] = ip
                # print(f'{}')
            count += 1

    def __str__(self):
        msg = f'{self.name_srv:10s} {self.dev_type:10s} {str(self.links):20s} '
        return msg


class DevicesInfo:
    """ List of Devices Info """

    def __init__(self, name_file, dbg=logging.INFO):
        self.yaml_file_name = name_file
        self.rtrs_info = dict()
        self.srvs_info = dict()
        self.imgs_info = dict()
        self.links_info = dict()
        self.__logger = AkarLogging(dbg, "openstacklab").get_color_logger()
        self.__analyze_file_yaml()

    def __analyze_file_yaml(self):
        self.__logger.debug(f"CONFIG_YAML:\n{json.dumps(self.yaml_file_name, indent=2)}")
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir='.')
        with open(self.yaml_file_name) as yml:
            conf_yaml = yaml.load(yml, Loader=yaml.FullLoader)
        self.__logger.debug(f"CONFIG_YAML:\n{json.dumps(conf_yaml, indent=2)}")

        # Analyze images info
        for key, val in conf_yaml["vm"].items():
            for nm, inf in val.items():
                init_img = inf.get('init_img') or ""
                name_intrf = inf.get('name_intrf') or ""
                plat = inf.get('platform') or ""
                # if 'init_img' in inf:
                #     init_img = inf['init_img']
                self.imgs_info[nm] = ImageInfo(
                    name=nm, flavor_id=inf['flavor'], image=inf['image'], dev_type=key, init_img=init_img, name_intrf=name_intrf, plat=plat
                )

        # Analyze network links
        for key, val in conf_yaml["networks"].items():
            # print(f'{key}')
            name = "link_" + str(key)
            self.links_info[key] = LinkInfo(name=name, num=key, val=val)
            self.__logger.debug(f"LinkInfo: {self.links_info[key]}")

        used_net_links = list()
        # Analyze routers
        if 'routers' in conf_yaml:
            for key, val in conf_yaml["routers"].items():
                # self.__logger.info(f"net: {str(self.links_info)}")
                self.rtrs_info[key] = RouterInfo(name=key, val=val, net=self.links_info)
                self.__logger.debug(f'{self.rtrs_info[key]}')

        # Analyze servers
        if 'servers' in conf_yaml:
            for key, val in conf_yaml["servers"].items():
                self.srvs_info[key] = ServerInfo(name=key, val=val, net=self.links_info)
                self.__logger.debug(f'{self.srvs_info[key]}')

        self.__logger.debug(str(self.__str__()))

    def __str__(self):
        msg = '{:*^10s} {:*^20s} {:*^20s} {:*^20s} {:*^20s}\n'.format("NAME", "TYPE", "FLAVOR", "IMG", "INIT_IMG")
        for key, img_info in self.imgs_info.items():
            msg += f'{str(img_info)}\n'
        msg += "\n\n"
        for key, lnk_info in self.links_info.items():
            msg += f'{str(lnk_info)}\n'

        return msg


class YamlToHeat:
    """ List of Devices Info """

    def ipaddr(self, input_str, net_cfg):
        ip_net = IPNetwork(input_str)
        ret = ""
        if net_cfg == "address":
            ret = ip_net.ip
        elif net_cfg == "netmask":
            ret = ip_net.netmask
        elif net_cfg == "hostmask":
            ret = ip_net.hostmask
        elif net_cfg == "network":
            ret = ip_net.network
        elif net_cfg == "prefix":
            ret = ip_net.prefixlen
        return ret

    def __init__(self, dvs_info, net_mgmt="wan0", avail_zone="nova:osc", dbg=logging.INFO):
        self.__logger = AkarLogging(dbg, "openstacklab").get_color_logger()
        self.dvs_info = dvs_info
        self.net_mgmt = net_mgmt
        self.avail_zone = avail_zone
        self.outputdir = "net-stack"
        self.outputmap = "net-maps"
        self.heat_file_name = f"{self.outputdir}/st_{os.path.basename(self.dvs_info.yaml_file_name)}"
        self.draw_file_name = f"{str(self.outputmap)}/st_{os.path.splitext(os.path.basename(self.dvs_info.yaml_file_name))[0]}"

        self.heat_template_file = "template_stack.j2"
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)
        if not os.path.exists(self.outputmap):
            os.makedirs(self.outputmap)
        self.__logger.info(f'{self.heat_file_name }')
        self.__logger.debug(f'{dvs_info}')
        self.__generate_stack_template()
        self.__draw_net()

    def __generate_stack_template(self):
        # file_loader = FileSystemLoader(f"{src_dir}/templates")
        self.__logger.info(f'Generate stack file from template ')
        src_dir = os.path.dirname(os.path.realpath(__file__))
        self.__logger.debug(f'Source dir: {src_dir}')
        file_loader = FileSystemLoader(src_dir)
        env = Environment(loader=file_loader)
        env.filters['ipaddr'] = self.ipaddr
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        # env.filters['ipaddr'] = self.ipaddr
        template = env.get_template(self.heat_template_file)
        output = template.render(dvsinfo=self.dvs_info, net_mgmt=self.net_mgmt, avail_zone=self.avail_zone)
        with open(self.heat_file_name, mode="w") as file_:
            file_.write(output)

    def __draw_net(self):
        f = gv.Graph("Network Map", engine="neato")
        # format='png',  filename='fsm.png'
        f.attr(fontsize="30", fillcolor="red")
        f.attr("node", shape="doublecircle", len="3.0", style="filled", color="lightgrey", size="20", fixedsize="true", fontsize="10", overlap="false")
        # , fillcolor='red'
        f.attr(labelfontsize="5")
        for ii, net in self.dvs_info.links_info.items():
            for dv in net.all_dvs:
                f.edge(dv['dev_name'], net.ipv4, len="2.0", width="2.5", fontsize="10", label=dv['intr'])
                f.node(net.ipv4, shape="octagon", width="2.0", style="rounded", fontsize="9")
        with open(f'{self.draw_file_name}.gv', mode='w') as yml:
            yml.write(f.source)
        f.render(filename=self.draw_file_name, format='pdf', cleanup=True)
