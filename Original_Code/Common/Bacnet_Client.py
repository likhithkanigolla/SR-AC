# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

# }}}
import argparse
import logging
import os
import sys
from collections import deque
from copy import copy
from datetime import datetime
from threading import Thread

from bacpypes.apdu import ReadPropertyRequest
from bacpypes.app import BIPSimpleApplication
from bacpypes.basetypes import BinaryPV
from bacpypes.constructeddata import Array
from bacpypes.core import run, stop, deferred
from bacpypes.debugging import bacpypes_debugging
from bacpypes.iocb import IOCB
from bacpypes.local.device import LocalDeviceObject
from bacpypes.object import get_datatype
from bacpypes.pdu import Address
from bacpypes.primitivedata import Unsigned, ObjectIdentifier

'''
    import from ../Common repo
'''
sys.path.insert(1, os.getenv('SCRC_COMMON', ''))
import utils
from sensor import Sensors

utils.setup_logging()
_log = logging.getLogger(__name__)

# some debugging
_debug = 1  # Enable debug logging for ReadPointListThread


@bacpypes_debugging
class ReadPointListThread(Thread):

    def __init__(self, point_list, this_application):
        if _debug:
            ReadPointListThread._debug("__init__ %r", point_list)
        Thread.__init__(self)

        # turn the point list into a queue
        self.point_queue = deque(point_list)

        # make a list of the response values
        self.response_values = []
        self._this_application = this_application

    def run(self):
        if _debug:
            ReadPointListThread._debug("run")

        # loop through the points
        for addr, obj_id, prop_id, sensor_id in self.point_queue:
            print('.', end='')
            # build a request
            request = ReadPropertyRequest(
                objectIdentifier=ObjectIdentifier(obj_id).value,
                propertyIdentifier=prop_id,
            )
            request.pduDestination = Address(addr)
            if _debug:
                ReadPointListThread._debug("    - request: %r", request)

            # make an IOCB
            iocb = IOCB(request)
            if _debug:
                ReadPointListThread._debug("    - iocb: %r", iocb)

            # give it to the application
            deferred(self._this_application.request_io, iocb)

            # wait for the response
            iocb.wait()

            if iocb.ioResponse:
                apdu = iocb.ioResponse

                _log.debug("io response")

                # find the datatype
                datatype = get_datatype(apdu.objectIdentifier[0],
                                        apdu.propertyIdentifier)
                if _debug:
                    ReadPointListThread._debug("    - datatype: %r", datatype)
                if not datatype:
                    raise TypeError("unknown datatype")

                # special case for array parts, others are managed by cast_out
                if issubclass(datatype, Array) and (
                        apdu.propertyArrayIndex is not None):
                    if apdu.propertyArrayIndex == 0:
                        value = apdu.propertyValue.cast_out(Unsigned)
                    else:
                        value = apdu.propertyValue.cast_out(datatype.subtype)
                else:
                    value = apdu.propertyValue.cast_out(datatype)
                    _log.debug(
                        "datatype: {}".format(datatype)
                        + "value: {}".format(value)
                    )
                    if datatype == BinaryPV:
                        # _log.debug("converting !!!!!!!!!!!!!!!!!!!")
                        value = 0 if value == 'inactive' else 1

                if _debug:
                    ReadPointListThread._debug("    - value: %r", value)

                # save the value
                self.response_values.append(value)

            if iocb.ioError:
                if _debug:
                    ReadPointListThread._debug("    - error: %r",
                                               iocb.ioError)
                # print('')
                # _log.error("Error: {}".format(iocb.ioError))
                self.response_values.append(None)

        print('.')
        # done
        stop()


def bacnet_client(config_path, **kwargs):
    # config = load_config(config_path)
    return Bacnet_Client(config_path, **kwargs)


def get_active_sensors_count(sensors):
    count = 0
    for sensor in sensors.values():
        if sensor.enabled():
            count += 1
    return count


def get_point_list(dest_addrs: str, node_src_name: int, sensors: Sensors):
    pt_list = []
    for sensor_id, sensor in sensors.items():
        src_name = sensor.get_src_name()

        if src_name == 'Time Stamp':
            continue
        elif not sensor.enabled():
            # Inactive at sensor level -  doesn't read the sensor
            continue

        object_type: str = sensor.get_data_type()
        instance_id = int(src_name) + node_src_name * 256
        pt_list.append(
            (
                dest_addrs,
                '{}:{}'.format(object_type, instance_id),
                'presentValue',
                sensor_id
            )
        )
    return pt_list


class Bacnet_Client(object):
    """
    Daikin D-BACS BACnet Gateway Client

    https://github.com/JoelBender/bacpypes/blob/master/samples/MultipleReadPropertyThreaded.py
    """

    def __init__(self, config_path, **kwargs):

        super(Bacnet_Client, self).__init__(**kwargs)
        self._config = utils.load_config(config_path)

        # get configuration params
        self._config_bacnet = self._config.get('bacnet', {})

        self._init_config_params()

        self._nodes = self._config.get('nodes', {})

        self._sensors = self._config.get('sensors', {})

        # make a device object
        this_device = LocalDeviceObject(
            objectName=self._object_name,
            address=self._device_address,
            objectIdentifier=self._object_id,
            maxApduLengthAccepted=self._max_apdu_length,
            segmentationSupported=self._segmentation_supported,
            vendorIdentifier=self._vendor_id,
            foreignTTL=self._foreignTTL,
        )
        _log.debug("    - this_device: %r", this_device)

        # make a simple application
        self._this_application = BIPSimpleApplication(this_device,
                                                      self._device_address)

        return

    def _init_config_params(self):
        self._bacnet_local_interface = self._config_bacnet.get(
            'local_interface',
            {}
        )
        self._bacnet_dest = self._config_bacnet.get(
            'dest',
            {"device_address": "10.2.24.2"}
        )

        self._object_name = self._bacnet_local_interface.get(
            "object_name",
            "LivingLabs, BACnet app running in dev container to interface "
            "Daikin HVAC, SR-AC 47808")
        self._device_address = self._bacnet_local_interface.get(
            "device_address",
            "localhost")
        self._object_id = self._bacnet_local_interface.get("object_id", 599)
        self._max_apdu_length = self._bacnet_local_interface.get(
            "max_apdu_length",
            1024)
        self._segmentation_supported = self._bacnet_local_interface.get(
            "segmentation_supported", "segmentedBoth")
        self._vendor_id = self._bacnet_local_interface.get("vendor_id", 15)
        self._foreignTTL = self._bacnet_local_interface.get("foreignTTL", 30)

        return

    def get_data(self):
        _log.debug("get_data()...")

        sensors = Sensors(self._sensors)

        '''
                prepare data for publishing
                copy data to Sensors
                '''
        new_data = []

        # for k in ['node_0',
        #           'node_1',
        #           #'node_27',    # node not responding
        #           #'node_76', 'node_77',
        #           ]:
        # for k in ['node_27']:
        for k in self._nodes.keys():

            _log.info("get node data: {}".format(k))

            tmp_sensors = copy(sensors)

            # error counter to keep track of communication failures
            # if failure count == sensors count communication completely failed
            # in that case don't save

            err_counter = 0

            bac_id = int(self._nodes[k]['src_name'])
            dest_addrs = self._bacnet_dest['device_address']

            pt_list = get_point_list(
                dest_addrs,
                bac_id,
                tmp_sensors
            )
            # print('pt_list: {}'.format(pt_list))

            '''
            datetime since epoch, the number of seconds that have elapsed 
                since Thursday, 1970 Jan 1 00:00:00 UTC
            _EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
            '''
            ts = datetime.now().timestamp()

            # create a thread and
            read_thread = ReadPointListThread(pt_list, self._this_application)

            # start it running when the core is running
            deferred(read_thread.start)

            _log.debug("%r...", read_thread)
            run()
            _log.debug("%r", read_thread)

            # save the results
            for request, response in zip(pt_list, read_thread.response_values):
                # print(request, response)

                sensor_id = request[3]
                value = response

                _log.debug(
                    "sensor_id: {}".format(sensor_id)
                    + ", value: {}".format(value)
                )

                if value is None:
                    # some error, dont save data
                    err_counter += 1

                # save value
                tmp_sensors.set_sensor_value(
                    self._sensors[sensor_id]['src_name'],
                    utils.mround(value,
                                 self._sensors[sensor_id].get('mround', 0.01))
                )
                continue

            #  check if Failed to read from sensor for all sensors,
            #  if so, dont append
            sensor_count = get_active_sensors_count(sensors)
            if err_counter == sensor_count - 1:
                _log.warning(
                    "err_counter: {}".format(err_counter)
                    + " active sensors: {}, skipping the node!!!".format(
                        sensor_count - 1)
                )

                # try to read the next node
                continue

            # save ts
            tmp_sensors.set_sensor_value(
                'Time Stamp',
                utils.mround(ts,
                             self._sensors['sensor_0'].get('mround', 0.01))
            )

            new_data.append(
                {
                    'node_id': k,
                    'src_name': self._nodes[k]['src_name'],
                    'sensors': tmp_sensors,
                }
            )

        #self._this_application.close_socket()

        return new_data

    def get_node_data(self, node_id):
        _log.debug(f"get_node_data({node_id})...")
        sensors = Sensors(self._sensors)
        if node_id not in self._nodes:
            return None

        tmp_sensors = copy(sensors)
        err_counter = 0
        bac_id = int(self._nodes[node_id]['src_name'])
        dest_addrs = self._bacnet_dest['device_address']

        pt_list = get_point_list(dest_addrs, bac_id, tmp_sensors)
        ts = datetime.now().timestamp()
        read_thread = ReadPointListThread(pt_list, self._this_application)
        deferred(read_thread.start)
        _log.debug("%r...", read_thread)
        run()
        _log.debug("%r", read_thread)

        for request, response in zip(pt_list, read_thread.response_values):
            sensor_id = request[3]
            value = response
            _log.debug("sensor_id: %s, value: %s", sensor_id, value)
            if value is None:
                err_counter += 1
            tmp_sensors.set_sensor_value(
                self._sensors[sensor_id]['src_name'],
                utils.mround(value, self._sensors[sensor_id].get('mround', 0.01))
            )

        sensor_count = get_active_sensors_count(sensors)
        if err_counter == sensor_count - 1:
            _log.warning(
                "err_counter: %s active sensors: %s, skipping the node!!!",
                err_counter, sensor_count - 1
            )
            return None

        tmp_sensors.set_sensor_value(
            'Time Stamp',
            utils.mround(ts, self._sensors['sensor_0'].get('mround', 0.01))
        )

        return {
            'node_id': node_id,
            'src_name': self._nodes[node_id]['src_name'],
            'sensors': tmp_sensors,
        }

    def set_ac_onoff(self, node_id, turn_on):
        """
        Send a BACnet WritePropertyRequest to turn the AC on or off for the given node.
        """
        node_info = self._nodes.get(node_id)
        if not node_info:
            return {"error": f"Node {node_id} not found"}
        bac_id = int(node_info['src_name'])
        dest_addrs = self._bacnet_dest['device_address']
        sensor_id = None
        for sid, sdef in self._sensors.items():
            if sdef.get('om2m_cnt') == 'Start Stop Status':
                sensor_id = sid
                break
        if not sensor_id:
            return {"error": "Start Stop Status sensor not found in config"}
        object_type = self._sensors[sensor_id]['data_type']
        instance_id = int(self._sensors[sensor_id]['src_name']) + bac_id * 256
        value = 1 if turn_on else 0
        from bacpypes.apdu import WritePropertyRequest
        from bacpypes.primitivedata import Boolean
        from bacpypes.pdu import Address
        from bacpypes.core import deferred, run
        from bacpypes.iocb import IOCB
        request_apdu = WritePropertyRequest(
            objectIdentifier=(object_type, instance_id),
            propertyIdentifier='presentValue',
            propertyValue=Boolean(value),
        )
        request_apdu.pduDestination = Address(dest_addrs)
        iocb = IOCB(request_apdu)
        deferred(self._this_application.request_io, iocb)
        run()
        if iocb.ioError:
            return {"error": str(iocb.ioError)}
        return {"status": "success", "node_id": node_id, "turned_on": turn_on}


def parse_argv():
    parser = argparse.ArgumentParser(description='Main ')

    parser.add_argument('--config', metavar='path', required=True,
                        help='config file of the node')
    args = parser.parse_args()

    return args.config


def main(argv=None):
    if argv is None:
        argv = sys.argv
    _log.debug('main(), argv: {}'.format(argv))

    config_path = parse_argv()

    try:
        d_bacs = bacnet_client(config_path)
        new_data = d_bacs.get_data()
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')
        return -1

    return 0


def _main():
    """ Entry point for scripts."""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log.debug('received a keyboard interrupt, stopping!')
        pass


if __name__ == '__main__':
    _main()