# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

# }}}


"""
    App to download data from IDUc and push to OneM2M
"""

'''
    monkey patch at the start before calling any other imports
'''
from gevent import monkey

monkey.patch_all(thread=False, select=False)

import argparse
import logging
import os
import sys
import time

'''
    import from Common repo
'''
sys.path.insert(1, os.getenv('SCRC_COMMON', '../Common'))
sys.path.insert(1, os.getenv('SCRC_SR', '../SmartRoom'))

import utils
utils.setup_logging(level=logging.INFO)
_log = logging.getLogger(__name__)

from sensor import Sensors
from OneM2M_Client import OneM2M_Client
from ThingSpeak_Client import ThingSpeak_Client
from Bacnet_Client import Bacnet_Client

# todo: rework to get this from config
log = logging.getLogger('urllib3')
log.setLevel(logging.INFO)
log = logging.getLogger('bacpypes')
log.setLevel(logging.INFO)
log = logging.getLogger('OneM2M_Client')
log.setLevel(logging.INFO)
log = logging.getLogger('onem2m')
log.setLevel(logging.INFO)
log = logging.getLogger('Bacnet_Client')
log.setLevel(logging.INFO)


_log.debug('Kohli AC IDUs App')


def parse_argv():
    parser = argparse.ArgumentParser(description='Main ')

    parser.add_argument('--config', metavar='path', required=True,
                        help='config file of the node')
    args = parser.parse_args()

    return args.config


def _print_stats(new_data):
    """

    :type new_data: dict{om2m_sub_cnt, Sensors}
    """
    _log.info(
        'Records received from the d-bacs interface'
        + ': {}'.format(len(new_data))
    )

    # TODO: _log.info other statistics

    return


def _pre_process_data(config, new_data):
    if len(new_data) == 0:
        return

    nodes = config.get('nodes')
    for v in new_data:
        node_id = v['node_id']
        sensors = v['sensors']      # type: Sensors
        src_name = v['src_name']

        # deactivate inactive sensors, (dont put nan for these inactive sensors)
        inactive_sensors = config['nodes'][node_id].get('inactive', [])
        for inactive_sensor in inactive_sensors:
            sensors.enable(inactive_sensor, False)

        # append onem2m sub container to the data
        om2m_sub_cnt = utils.get_om2m_sub_cnt(nodes, src_name)
        v['om2m_sub_cnt'] = om2m_sub_cnt

    return


def main(argv=None):
    if argv is None:
        argv = sys.argv
    _log.debug('main(), argv: {}'.format(argv))

    '''
        load config, if not valid config file return
    '''
    try:
        config_path = parse_argv()
        config = utils.load_config(config_path)
        run_forever = config.get('run_forever', True)
        read_interval = config.get('read_interval', 60)
        pub_thingspeak = config.get('pub_thingspeak', False)

        # setup D BACS client
        d_bacs_client = Bacnet_Client(config_path)

        # setup onem2m client
        onem2m_client = OneM2M_Client(config_path)

        # setup thingspeak client
        thingspeak_client = (
            ThingSpeak_Client(config_path)
            if pub_thingspeak else None
        )

    except Exception as e:
        print(e)
        _log.exception('unhandled exception')
        return -1

    '''
        main loop
    '''
    while True:
        # connect to D-BACs interface and
        # retrieve the  IDUs data -- bacnet
        new_data = d_bacs_client.get_data()

        # pre process data
        _pre_process_data(config, new_data)

        total_records = len(new_data)
        if total_records <= 0:
            _log.warning('No new data from the bacnet interface!!!')
        else:
            _print_stats(new_data)
            utils.publish_data(config, new_data,
                               onem2m_client,
                               thingspeak_client,
                               )

            _log.info('done.')

        if not run_forever:
            _log.info('run_forever: {}, stopping!'.format(run_forever))
            return 0

        _log.info('Going to sleeping...')
        time.sleep(read_interval)
        _log.info('...Awake')


def _main():
    """ Entry point for scripts."""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log.debug('received a keyboard interrupt, stopping!')
        pass


if __name__ == '__main__':
    _main()