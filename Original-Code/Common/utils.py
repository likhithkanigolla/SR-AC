# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

# }}}
""""""

'''
    monkey patch at the start before calling any other imports
'''
import gevent
from gevent import monkey

monkey.patch_all(thread=False, select=False)

from gevent import Greenlet

import json
import logging
import math
import os
import re
import stat
import sys
import traceback
import time

import requests
import yaml
from zmq.utils import jsonapi

_comment_re = re.compile(
    r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))',
    re.MULTILINE | re.DOTALL)


class JsonFormatter(logging.Formatter):

    def format(self, record):
        dct = record.__dict__.copy()
        dct["msg"] = record.getMessage()
        dct.pop('args')
        exc_info = dct.pop('exc_info', None)
        if exc_info:
            dct['exc_text'] = ''.join(traceback.format_exception(*exc_info))
        return jsonapi.dumps(dct)


def isapipe(fd):
    fd = getattr(fd, 'fileno', lambda: fd)()
    return stat.S_ISFIFO(os.fstat(fd).st_mode)


def setup_logging(level=logging.DEBUG):
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if isapipe(sys.stderr) and '_LAUNCHED_BY_PLATFORM' in os.environ:
            handler.setFormatter(JsonFormatter())
        else:
            fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s'
            handler.setFormatter(logging.Formatter(fmt))

        root.addHandler(handler)
    root.setLevel(level)


setup_logging()
_log = logging.getLogger(__name__)


def do_rpc(
        msg_id,
        url_root,
        header=None,
        method=None,
        params=None,
        request_method='POST'
):
    # global authentication
    # _log.debug('do_rpc()')
    result = False
    json_package = {'jsonrpc': '2.0',
                    'id': msg_id,
                    # 'method': method,
                    }

    if header:
        json_package['header'] = header
    if params:
        json_package['params'] = params

    try:
        if request_method.upper() == 'POST':
            # https://2.python-requests.org/en/v3.0.0/user/advanced/#timeouts
            _log.debug('http_data: {}'.format(json.dumps(json_package)))
            response = requests.post(
                url_root,
                data=json.dumps(json_package),
                timeout=(30, 30)
            )
        elif request_method.upper() == 'DELETE':
            response = requests.delete(
                url_root,
                data=json.dumps(json_package),
                timeout=(3.05, 3.05)
            )
        else:
            if request_method.upper() != 'GET':
                _log.warning('unimplemented'
                             + ' request_method: {}'.format(request_method)
                             + ', trying "GET"!!!'
                             )
            response = requests.get(
                url_root,
                data=json.dumps(json_package),
                timeout=(3.05, 3.05)
            )

        if response.ok:
            if 'result' in response.json().keys():
                success = response.json()['result']
                if request_method.upper() not in ['POST', 'DELETE']:
                    result = success
                elif success:
                    # _log.debug('response - ok'
                    #    + ', {} result success: {}'.format(method, success)
                    # )
                    result = True
                else:
                    _log.debug('response - ok'
                               + ', {} result success: {}'.format(method,
                                                                  success)
                               )
            elif 'error' in response.json().keys():
                error = response.json()['error']
                _log.warning('{} returned error'.format(method)
                             + ', Error: {}'.format(error)
                             )
        else:
            _log.warning('no response, url_root:{}'.format(url_root)
                         + ' method:{}'.format(method)
                         + ' response: {}'.format(response)
                         )
    except requests.exceptions.HTTPError as rhe:
        _log.warning('do_rpc() requests http error occurred.'
                     + ' Check the url'
                     + ', message: {}'.format(rhe)
                     )
        pass
    except requests.exceptions.ConnectTimeout as rcte:
        _log.warning('do_rpc() requests connect timed out'
                     + ' while trying connect to remote.'
                     + ' Maybe set up for a retry or continue in a retry loop'
                     + ', message: {}'.format(rcte)
                     )
        pass
    except requests.exceptions.ConnectionError as rce:
        _log.warning('do_rpc() requests connection error.'
                     + ' Most likely dest is down'
                     + ', message: {}'.format(rce)
                     )
        pass
    except requests.exceptions.ReadTimeout as rrte:
        _log.warning('do_rpc() requests read timed out.'
                     + ' Dst did not send any data in the allotted amount of '
                       'time'
                     + ', message: {}'.format(rrte)
                     )
        pass
    except requests.exceptions.Timeout as rte:
        _log.warning('do_rpc() requests timed out.'
                     + ' Maybe set up for a retry or continue in a retry loop'
                     + ', message: {}'.format(rte)
                     )
        pass
    except requests.exceptions.TooManyRedirects as rre:
        _log.warning('do_rpc() too many redirects exception.'
                     + ' Most likely URL was bad'
                     + ', message: {}'.format(rre)
                     )
        pass
    except requests.exceptions.RequestException as lre:
        _log.warning('do_rpc() unhandled requests exception.'
                     + ' Bailing out'
                     + ', message: {}'.format(lre)
                     )
        pass
    except Exception as e:
        print(e)
        _log.warning('do_rpc() unhandled exception, most likely dest is down'
                     + ', message: {}'.format(e)
                     )
        pass
    return result


# code from volttron, 'volttron/platform/agent/utils.py'
def load_config(config_path):
    """Load a JSON-encoded configuration file."""
    if config_path is None:
        _log.info("CONFIG does not exist in environment."
                  + " load_config returning empty configuration.")
        return {}

    if not os.path.exists(config_path):
        _log.info("Config file specified by CONFIG does not exist."
                  + " load_config returning empty configuration.")
        return {}

    # First attempt parsing the file with a yaml parser
    # (allows comments natively)
    # Then if that fails we fallback to our modified json parser.
    try:
        with open(config_path) as f:
            return yaml.safe_load(f.read())
    # except yaml.scanner.ScannerError as e:
    except yaml.YAMLError as e:
        _log.warning('YAMLError: {}'.format(e))
        try:
            with open(config_path) as f:
                return parse_json_config(f.read())
        except Exception as e:
            print(e)
            _log.error("Problem parsing configuration: {}".format(e))
            raise


def parse_json_config(config_str):
    """Parse a JSON-encoded configuration file."""
    return jsonapi.loads(strip_comments(config_str))


def strip_comments(string):
    """Return string with all comments stripped.

    Both JavaScript-style comments (//... and /*...*/) and hash (#...)
    comments are removed.
    """
    return _comment_re.sub(_repl, string)


def _repl(match):
    """Replace the matched group with an appropriate string."""
    # If the first group matched, a quoted string was matched and should
    # be returned unchanged.  Otherwise a comment was matched and the
    # empty string should be returned.
    return match.group(1) or ''


def get_server_addr(cse_ip, cse_port='', in_cse='/~/in-cse/in-name/', https=True):
    """

    :param cse_ip: str
    :param cse_port: str
    :param in: str
    :param https: bool
    :return: url: str
    """
    return (
            'http' + ('://' if not https else 's://')
            + cse_ip
            + (':' + cse_port if cse_port is not None else '')
            + (  in_cse  if in_cse is not None else '/~/in-cse/in-name/')
    )


def get_node_id(nodes, src_name):
    """

    :param nodes: dict
    :param src_name: src
    :return: node_id: str
    """
    for k in nodes.keys():
        if nodes[k]['src_name'] == src_name:
            return k
    # not a valid node src_name
    raise KeyError("Not a valid node src_name")


def get_node_id_om2m_sub_cnt(nodes, om2m_sub_cnt):
    """

    :param nodes: dict
    :param om2m_sub_cnt:
    :return: node_id
    """
    for k in nodes.keys():
        if nodes[k]['om2m_sub_cnt'] == om2m_sub_cnt:
            return k
    # not a valid node om2m_sub_cnt
    raise KeyError("Not a valid node om2m_sub_cnt")


def get_om2m_sub_cnt(nodes, src_name):
    """

    :param nodes: dict
    :param src_name: str
    :return: om2m_sub_cnt: str
    """
    for v in nodes.values():
        if v['src_name'] == src_name:
            return v['om2m_sub_cnt']
    # not a valid node src_name
    raise KeyError("Not a valid node src_name")


def get_thingspeak_write_key(nodes, src_name):
    """

    :param nodes: dict
    :param src_name: str
    :return: thingspeak_write_key: str
    """
    for v in nodes.values():
        if v['src_name'] == src_name:
            return v['ts_write_key']
    # not a valid node src_name
    raise KeyError("Not a valid node src_name")


# function to return key for any value
def get_key(dict_data, val):
    """
    function to return key for any value

    :param dict_data: dict
    :param val: value
    :return: key
    """
    for key, value in dict_data.items():
        if val == value:
            return key

    raise KeyError("key doesn't exist")


def mround(num, multiple_of):
    # _log.debug('mround()')
    if num is None:
        return None
    if type(num) != float:
        return num
    value = math.floor((num + multiple_of / 2) / multiple_of) * multiple_of
    return value


# refer to https://bit.ly/3beuacI
# What is the best way to compare floats for almost-equality in Python?
# comparing floats is mess
def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    # _log.debug('isclose()')
    value = abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
    return value


def get_decimal_digits(x):
    multiplier = 0
    count = 0

    fractional, whole = math.modf(x)

    if fractional != 0:
        multiplier = 1

    while not (x * multiplier).is_integer():
        count += 1
        multiplier = 10 * multiplier

    return count


class BlinkStatusLed(Greenlet):
    """
        usage:
            # start blinking status led
            blink_led = BlinkStatusLed(1, fn_led_on, fn_led_off)
            blink_led.start()

            # stop blinking status led
            blink_led.stop()
    """

    def __init__(self, interval, fn_led_on, fn_led_off):
        Greenlet.__init__(self)
        self.interval = interval
        self._blink = True
        self._fn_led_on = fn_led_on
        self._fn_led_off = fn_led_off
        return

    def _run(self):
        while self._blink:
            # _log.info('LED ON')
            self._fn_led_on()
            gevent.sleep(self.interval)
            # _log.info('LED OFF')
            self._fn_led_off()
        return

    def stop(self):
        self._blink = False
        return

    def set_interval(self, interval):
        self.interval = interval
        return


def divide_10(value, no_of_digits):
    val = value * (10 ** -no_of_digits)
    return val


def publish_data(config, new_data,
                 onem2m_client=None,
                 thingspeak_client=None
                 ):
    _log.info('publish to onem2m server...')
    # publish data to onem2m
    count = 0
    total_records = len(new_data)

    # p_p --> publish using parallel requests
    p_p = config.get('p_p', False)
    p_p_onem2m = config['onem2m'].get('p_p', p_p)
    p_p_thingspeak = config['thingspeak'].get('p_p', p_p)

    if onem2m_client is not None and p_p_onem2m:
        onem2m_client.publish_parallel_all_nodes(config, new_data)
    if thingspeak_client is not None and p_p_thingspeak:
        thingspeak_client.publish_parallel_all_nodes(config, new_data)

    for v in new_data:

        if p_p_onem2m and p_p_thingspeak:
            continue

        node_id = v['node_id']
        label = config['nodes'][node_id]['label']
        cin_labels = tuple(label)

        count += 1
        if onem2m_client is not None and not p_p_onem2m:
            # onem2m_client.publish(v['om2m_sub_cnt'],
            #                       v['sensors'])
            # onem2m_client.publish_parallel(v['om2m_sub_cnt'],
            #                                v['sensors'])
            _log.info('...publishing to onem2m {}/{}'.format(count,
                                                           total_records))
            status,  status_code, cin = onem2m_client.publish_comma_separated(
                v['om2m_sub_cnt'],
                v['sensors'],
                cin_labels=cin_labels
            )
            _log.info(
                'status: {}'.format(status)
                + ', status_code: {}'.format(status_code)
                + ', cin: {}'.format(cin)
            )

            time.sleep(1)

        # TODO: awaiting decision on field structure
        if thingspeak_client is not None and not p_p_thingspeak:
            _log.info('...publishing to thingspeak {}/{}'.format(count,
                                                           total_records))
            thingspeak_client.publish(v['ts_write_key'],
                                      v['sensors'])
            time.sleep(1)

    # TODO: check for return error
    # TODO: if error, implement local storage & publish later

    return