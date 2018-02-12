# -*- coding: utf-8 -*-
# Copyright (C) 2008-2015 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo import http_json_server
from xivo.http_json_server import HttpReqError
from xivo.http_json_server import CMD_R, CMD_RW
from xivo.moresynchro import RWLock
from xivo import xivo_config
from xivo import yaml_json
from xivo import xys
from xivo import json_ops
from xivo import network


NET_LOCK_TIMEOUT = 60  # XXX
NETLOCK = RWLock()


def network_config(args):
    """
    GET /network_config

    Just returns the network configuration
    """
    if not NETLOCK.acquire_read(NET_LOCK_TIMEOUT):
        raise HttpReqError(503, "unable to take NETLOCK for reading after %s seconds" % NET_LOCK_TIMEOUT)
    try:
        netconf = xivo_config.load_current_configuration()
        return yaml_json.stringify_keys(netconf)
    finally:
        NETLOCK.release()


REN_ETH_SCHEMA = xys.load("""
old_name: !~~prefixedDec eth
new_name: !~~prefixedDec eth
""")


def rename_ethernet_interface(args):
    """
    POST /rename_ethernet_interface

    args ex:
    {'old_name': "eth42",
     'new_name': "eth1"}
    """
    if not xys.validate(args, REN_ETH_SCHEMA):
        raise HttpReqError(415, "invalid arguments for command")
    if not NETLOCK.acquire_write(NET_LOCK_TIMEOUT):
        raise HttpReqError(503, "unable to take NETLOCK for writing after %s seconds" % NET_LOCK_TIMEOUT)
    try:
        xivo_config.rename_ethernet_interface(args['old_name'], args['new_name'])
        return True
    finally:
        NETLOCK.release()


SWAP_ETH_SCHEMA = xys.load("""
name1: !~~prefixedDec eth
name2: !~~prefixedDec eth
""")


def swap_ethernet_interfaces(args):
    """
    POST /swap_ethernet_interfaces

    args ex:
    {'name1': "eth0",
     'name2': "eth1"}
    """
    if not xys.validate(args, SWAP_ETH_SCHEMA):
        raise HttpReqError(415, "invalid arguments for command")
    if not NETLOCK.acquire_write(NET_LOCK_TIMEOUT):
        raise HttpReqError(503, "unable to take NETLOCK for writing after %s seconds" % NET_LOCK_TIMEOUT)
    try:
        xivo_config.swap_ethernet_interfaces(args['name1'], args['name2'])
        return True
    finally:
        NETLOCK.release()


def _val_modify_network_config(args):
    """
    ad hoc validation function for modify_network_config command
    """
    if set(args) != set(['rel', 'old', 'chg']):
        return False
    if not isinstance(args['rel'], list):
        return False
    for elt in args['rel']:
        if not isinstance(elt, basestring):
            return False
    return True


def modify_network_config(args):
    """
    POST /modify_network_config
    """
    if not _val_modify_network_config(args):
        raise HttpReqError(415, "invalid arguments for command")
    try:
        check_conf = json_ops.compile_conj(args['rel'])
    except ValueError:
        raise HttpReqError(415, "invalid relation")

    if not NETLOCK.acquire_write(NET_LOCK_TIMEOUT):
        raise HttpReqError(503, "unable to take NETLOCK for writing after %s seconds" % NET_LOCK_TIMEOUT)
    try:
        current_config = xivo_config.load_current_configuration()
        if not check_conf(args['old'], current_config):
            raise HttpReqError(409, "Conflict between state wanted by client and current state")

    finally:
        NETLOCK.release()


def routes(args, options):
    ret = True
    """
        auto eth0
        iface eth0 inet static
            address 192.168.32.242
            netmask 255.255.255.0
            gateway 192.168.32.254
            up ip route add 192.168.30.0/24 via 192.168.32.124 || true
    """
    args.sort(lambda x, y: cmp(x['iface'], y['iface']))
    iface = None

    network.route_flush()

    for route in args:
        if route['disable']:
            continue

        if route['iface'] != iface:
            iface = route['iface']

        try:
            (eid, output) = network.route_set(route['destination'], route['netmask'], route['gateway'], iface)
            if eid != 0 and route['current']:
                ret = False
        except Exception:
            raise HttpReqError(500, 'Cannot apply route')

    network.route_flush_cache()
    return ret


http_json_server.register(network_config, CMD_R)
http_json_server.register(rename_ethernet_interface, CMD_RW)
http_json_server.register(swap_ethernet_interfaces, CMD_RW)
http_json_server.register(routes, CMD_RW)
