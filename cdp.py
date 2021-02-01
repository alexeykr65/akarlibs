"""This Module provides a simple parsing function of cisco cdp output.

It requires 'show cdp neighbor detail' output
"""

import json
import re

_KEYS = {
    'device_id': 'Device ID:',
    'ip_address': r'(?:IP address|IPv4 Address):',
    'platform': r'Platform: (?:cisco)?',
    'capabilities': 'Capabilities:',
    'local_port': 'Interface:',
    'remote_port': r'Port ID \(outgoing port\):',
}


class CDPEntry():

    """This Class represents a CDP Entry
    """

    def __init__(self):
        self.device_id = None
        self.ip_address = None
        self.platform = None
        self.capabilities = None
        self.local_port = None
        self.remote_port = None

    def __repr__(self):
        return 'CDP Entry: {}'.format(self.device_id)

    @property
    def local_port_short(self):
        '''
        returns the local interface in short
        '''
        return self.shorten_interface(self.local_port)

    @property
    def remote_port_short(self):
        '''
        returns the remote interface in short
        '''
        return self.shorten_interface(self.remote_port)

    @property
    def dict(self):
        '''
        returns a dictionary of the CDPEntry object
        '''
        resp = {
            'device_id': self.remove_domain(),
            'ip_address': self.ip_address,
            'platform': self.platform,
            'capabilities': self.capabilities,
            'local_port': self.local_port,
            'remote_port': self.remote_port
        }
        return resp

    @property
    def dict_short(self):
        '''
        returns a dictionary of the CDPEntry object
        '''
        resp = {
            'device_id': self.remove_domain(),
            'ip_address': self.ip_address,
            'platform': self.platform,
            'capabilities': self.capabilities,
            'local_port': self.shorten_interface(self.local_port, length=3),
            'remote_port': self.shorten_interface(self.remote_port, length=3)
        }
        return resp

    @property
    def json(self):
        '''
        returns a json string of the CDPEntry object
        '''
        return json.dumps(self.dict)

    @staticmethod
    def _extract_keys(pattern, string):
        res = re.search(r'{}\s?(.*)'.format(pattern), string)
        if res:
            return res.group(1).split(',')[0].strip()
        return None

    @staticmethod
    def shorten_interface(port, length=2):
        """
        Shortens the Interface Description.
        """
        prefix_re = r'^\w{%s}' % length
        prefix = re.search(prefix_re, port).group(0)
        suffix = re.search(r'\d.*$', port).group(0)
        return '{0}{1}'.format(prefix, suffix)

    def get_all_properties(self, block):
        """
        This method takes in a block and extract out of it the values
        """
        for key, val in _KEYS.items():
            self.__dict__[key] = self._extract_keys(val, block)

    def remove_domain(self):
        """
        Removes the domain portion of the device_id
        """
        return self.device_id.split('.')[0]

    def create_interface_description(self, length=2, remove_domain=True, delimiter=':'):
        """
        Creates an interface description
        """
        remote_port = self.shorten_interface(self.remote_port, length)
        if remove_domain:
            device_id = self.remove_domain()
        else:
            device_id = self.device_id
        return 'interface {}\n  description {}{}{}'.format(self.local_port,
                                                           remote_port,
                                                           delimiter,
                                                           device_id)


class Device():
    """
    This Class represents a Device that has one or multiple CDP Entries (Neighbors)
    """

    def __init__(self, cdp_input, hostname=None):
        self.hostname = hostname
        self.cdp_entries = []
        self.cdp_input = cdp_input
        self._split_to_blocks()
        self._get_all_entries()

    def __repr__(self):
        return 'Device: {}'.format(self.hostname)

    def _split_to_blocks(self):
        self.blocks = re.findall(r'-----+((?:.*|\n+)+?)(?:-|$)', self.cdp_input)

    def _get_all_entries(self):
        for block in self.blocks:
            cdp_entry = CDPEntry()
            cdp_entry.get_all_properties(block)
            self.cdp_entries.append(cdp_entry)

    @property
    def dict(self):
        '''
        returns a dictionary of the Device object
        '''
        resp = [cdp_entry.dict for cdp_entry in self.cdp_entries]
        return resp

    @property
    def dict_short(self):
        '''
        returns a dictionary of the Device object
        '''
        resp = [cdp_entry.dict_short for cdp_entry in self.cdp_entries]
        return resp

    @property
    def json(self):
        '''
        returns a json string of the Device object
        '''
        return json.dumps(self.dict)
