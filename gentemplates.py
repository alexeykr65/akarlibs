#!/usr/bin/env python3

from pathlib import Path
from netaddr import IPNetwork
from jinja2 import Template, Environment, FileSystemLoader


class GenTemplates:
    def __init__(self, template_file, template_data) -> None:
        self.template_file = Path(template_file).name
        self.template_data = template_data
        self.template_dir = Path(template_file).parent

    def _ipaddr(self, input_str, net_cfg):
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

    def generate_template(self):
        # src_dir = os.path.dirname(os.path.realpath(__file__))
        file_loader = FileSystemLoader(self.template_dir)
        env = Environment(loader=file_loader)
        env.filters['ipaddr'] = self._ipaddr
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True
        template = env.get_template(self.template_file)
        output = template.render(data=self.template_data)
        return output
