#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Libs for extract information from KVM using libvirt
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
from .akarlogging import AkarLogging
import xml.etree.ElementTree as et
import libvirt
import logging
import sys


class KvmInterfaceInfo:
    def __init__(self, name="", int_type="", mac_addr="", dev="", bridge="", mtu="", model="", dbg=logging.INFO):
        self.name = name
        self.int_type = int_type
        self.mac_addr = mac_addr
        self.dev = dev
        self.bridge = bridge
        self.mtu = mtu
        self.model = model
        self.__logger = AkarLogging(dbg, "kvminterfaceinfo").get_color_logger()

    def __str__(self):
        msg = f"name: {self.name:8s} mac: {self.mac_addr:15s} dev: {self.dev:16s} br: {self.bridge:16s} model: {self.model:10s} mtu: {self.mtu:5s} "
        return msg


class KvmInstanceInfo:
    """ Class of Flavors """

    def __init__(self, xml_string="", name_instance="", uri_qemu="", dbg=logging.INFO):
        self.name = name_instance
        self.uri_qemu = uri_qemu
        self.xml = xml_string
        self.uuid = ""
        self.nova_name = ""
        self.interfaces = dict()
        self.__logger = AkarLogging(dbg, "kvminstanceinfo").get_color_logger()
        if self.name and self.uri_qemu:
            self.xml = self.get_xml_description()
        if self.xml:
            self.analize_xml()

    def __str__(self):
        msg = f"{self.name:5s} {self.uuid:20s} {self.nova_name:4d}"
        return msg

    def analize_xml(self):
        tree = et.fromstring(self.xml)
        elements = tree.find("name")
        self.name = elements.text
        self.__logger.info(elements.text)

        ns = {"nova": "http://openstack.org/xmlns/libvirt/nova/1.0"}
        name_nova = tree.find(".//nova:name", ns)
        self.nova_name = name_nova.text
        self.__logger.info(f"Nova name: {name_nova.text}")
        # get all info of interfaces
        elements = tree.findall("./devices/interface", ns)
        self.__logger.info(f"Total found interfaces: {len(elements)}")
        for elem in elements:
            self.__logger.info(f"Analyze next interface ... =====>>>>>>>")
            mac_addr = elem.find(".mac").get("address")
            int_dev = elem.find(".target").get("dev")
            alias_name = elem.find(".alias").get("name")
            source_bridge = elem.find(".source").get("bridge")
            model = elem.find(".model").get("type")
            mtu = elem.find(".mtu").get("size")
            self.__logger.debug(f"alias_name: {alias_name}")
            self.__logger.debug(f"int_dev: {int_dev}")
            self.__logger.debug(f"mac_address: {mac_addr}")
            self.interfaces[alias_name] = KvmInterfaceInfo(name=alias_name, mac_addr=mac_addr, dev=int_dev, bridge=source_bridge, model=model, mtu=mtu)

    def get_xml_description(self):
        conn = libvirt.open(self.uri_qemu)
        if conn == None:
            self.__logger.error("Failed to open connection to qemu:///system", file=sys.stderr)
            exit(1)
        self.__logger.info(f"Connection to {self.uri_qemu} successful.")
        if not self.name:
            self.__logger.error("Did not find name of instance")
            exit(1)
        dom = conn.lookupByName(self.name)
        xml = dom.XMLDesc()
        conn.close()
        self.__logger.info("Connection closed.")
        return xml
