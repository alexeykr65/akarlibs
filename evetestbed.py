#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Configure Cisco PyAts.aetest for virify links
#
# alexeykr@gmail.com
# coding=utf-8
# import codecs
import logging
import re
from pyats import aetest
import multiprocessing

logger = logging.getLogger(__name__)


class common_setup(aetest.CommonSetup):
    @aetest.subsection
    def establish_connections(self, steps, testscript, testbed):
        """ Common Setup subsection """
        dev_connected = list()
        for dev_name in testbed.devices.values():
            with steps.start(f'Connect to  {dev_name.name}'):
                try:
                    dev_name.connect(init_exec_commands=[], log_stdout=False)
                except Exception as e:
                    self.failed()
            dev_connected.append(dev_name)
        testscript.parameters['dev_conn'] = dev_connected


class TestConfEveNG(aetest.Testcase):

    @aetest.setup
    def find_ip_to_ping(self, testbed, testscript, dev_conn):
        dest_ping = dict()
        for dev in testbed.devices.values():
            dest_ping[dev.name] = list()
            for intf in dev:
                for remote_dev in intf.remote_devices:
                    remote_net = [remote_dev.interfaces[lnk].ipv4 for lnk in remote_dev.interfaces if remote_dev.interfaces[lnk].link.name == intf.link.name]
                    assert len(remote_net) == 1, f'ip on interface more one'
                    remote_ip = remote_net[0].ip
                    dest_ping[dev.name].append(remote_ip)
            for rt in testbed.custom.postcommands[dev.name]:
                if re.search(r'ip\s*route', rt):
                    routes = rt.split()[4]
                    dest_ping[dev.name].append(routes)
        testscript.parameters['dest_ping'] = dest_ping
        aetest.loop.mark(self.ping, dev_router=dev_conn)

    @aetest.test
    def ping(self, steps, testbed, dev_router, section, dest_ping):
        for dst in dest_ping[dev_router.name]:
            with steps.start(f'Ping from {dev_router.name} to IP: {dst}'):
                try:
                    result = dev_router.ping(dst)
                except Exception as e:
                    self.failed()
                    pass
                else:
                    match = re.search(r'Success rate is (?P<rate>\d+) percent', result)
                    success_rate = match.group('rate')
