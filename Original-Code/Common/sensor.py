# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2020, Sam Babu, Godithi.
# All rights reserved.
#
#
# IIIT Hyderabad

# }}}

import json
import logging
import sys
from copy import copy
from typing import Dict

import utils
# Use the correct setup_logging from utils
utils.setup_logging()
_log = logging.getLogger(__name__)


# https://www.oreilly.com/library/view/python-cookbook/0596001673/ch05s12.html
# Making a Fast Copy of an Object. Credit: Alex Martelli
def empty_copy(obj):
    class Empty(obj.__class__):

        def __init__(self): pass


    new_copy = Empty()
    new_copy.__class__ = obj.__class__
    return new_copy


class Sensor:
    _src_name: str = None
    _om2m_cnt: str = None
    _flag: bool = True
    _value = None  # Don't set type, it would be anything, int, float, str

    _mround: float = 0.01  # The multiple to use when rounding.
    _ts_field: str = None
    _data_type: str = "float"
    _no_of_registers: int = 2
    _fn_code: int = 3
    _params = {}

    def __init__(self, src_name, om2m_cnt, flag=True, value=None,
                 ts_field=None, data_type="float", no_of_registers=2,
                 fn_code=3, mround=0.01):
        self._src_name = src_name
        self._om2m_cnt = om2m_cnt
        self._flag = flag
        self._value = value
        self._mround = mround
        self._ts_field = ts_field
        self._data_type = data_type
        self._no_of_registers = no_of_registers
        self._fn_code = fn_code
        return

    ''' 
    str overload to return class attributes as json params
    '''

    def __str__(self):
        # _log.debug('__str__()')
        return json.dumps(self._get_params_dict())

    def __copy__(self):
        new_copy = empty_copy(self)
        new_copy._src_name = copy(self._src_name)
        new_copy._om2m_cnt = copy(self._om2m_cnt)
        new_copy._flag = copy(self._flag)
        new_copy._value = copy(self._value)
        new_copy._mround = copy(self._mround)
        new_copy._ts_field = copy(self._ts_field)
        new_copy._data_type = copy(self._data_type)
        new_copy._no_of_registers = copy(self._no_of_registers)
        new_copy._fn_code = copy(self._fn_code)
        return new_copy

    # getters
    def get_src_name(self):
        return self._src_name

    def get_om2m_cnt(self):
        return self._om2m_cnt

    def enabled(self):
        return self._flag

    def get_value(self):
        return self._value

    def get_mround(self):
        return self._mround

    def get_ts_field(self):
        return self._ts_field

    def get_data_type(self):
        return self._data_type

    def get_no_of_registers(self):
        return self._no_of_registers

    def get_fn_code(self):
        return self._fn_code

    # setters
    def set_src_name(self, src_name):
        self._src_name = src_name

    def set_om2m_cnt(self, om2m_cnt):
        self._om2m_cnt = om2m_cnt

    def enable(self, flag):
        self._flag = flag

    def set_value(self, value):
        self._value = utils.mround(value, self._mround)

    def set_mround(self, mround):
        self._mround = mround

    def set_ts_field(self, ts_field):
        self._ts_field = ts_field

    def set_data_type(self, data_type):
        self._data_type = data_type

    def set_no_of_registers(self, no_of_registers):
        self._no_of_registers = no_of_registers

    def set_fn_code(self, fn_code):
        self._fn_code = fn_code

    def get_json_params(self):
        # return json.dumps(self._get_params_dict())
        return self._get_params_dict()

    def _get_params_dict(self):
        self._params['src_name'] = self._src_name
        self._params['om2m_cnt'] = self._om2m_cnt
        self._params['flag'] = self._flag
        self._params['value'] = self._value
        self._params['mround'] = self._mround
        self._params['ts_field'] = self._ts_field
        self._params['data_type'] = self._data_type
        self._params['no_of_registers'] = self._no_of_registers
        self._params['fn_code'] = self._fn_code
        return self._params

    pass


class Sensors:
    _sensors_list: Dict[str, Sensor] = {}

    def __init__(self, sensors_list):
        for k, v in sensors_list.items():
            self.set_sensor(k, v)

    def __str__(self):
        tmp_dict = {}
        for k, v in self._sensors_list.items():
            tmp_dict[k] = str(v)
        return json.dumps(tmp_dict)

    def __copy__(self):
        new_copy = empty_copy(self)
        new_copy._sensors_list = {}
        for k, v in self._sensors_list.items():
            new_copy._sensors_list[k] = copy(v)
        return new_copy

    def get_sensor(self, k: str) -> Sensor:
        return self._sensors_list[k]

    def set_sensor(self, k: str, v):
        if type(v) == str:
            self._sensors_list[k] = Sensor(**(json.loads(v)))
        else:
            self._sensors_list[k] = Sensor(**v)
        return

    def set_sensor_value(self, src_name: str, value):
        for k, v in self._sensors_list.items():
            if v.get_src_name().lower() == src_name.lower():
                v.set_value(value)
                return
        raise KeyError("Key doesn't exist")

    def enable(self, sensor_id: str, flag):
        for k, v in self._sensors_list.items():
            if k == sensor_id:
                v.enable(flag)
                return
        raise KeyError("Key ({}) doesn't exist!!!".format(k))

    def items(self):
        return self._sensors_list.items()

    def keys(self):
        return self._sensors_list.keys()

    def values(self):
        return self._sensors_list.values()

    def get_sensor_values(self, enable_check: bool = True) -> list:
        """

        :type enable_check: bool, include sensor value only if sensor is enable
        :rtype: list[values]
        """
        values = []
        for sensor in self._sensors_list.values():
            if enable_check and not sensor.enabled():
                continue

            value = sensor.get_value()
            if value is None:
                # do nothing
                values.append("None")
            elif type(value) is int:
                # handle int type
                fmt_str = '{:d}'
                values.append(fmt_str.format(sensor.get_value()))
            elif type(value) is float:
                # handle float type
                no_of_digits = utils.get_decimal_digits(sensor.get_mround())
                fmt_str = '{:.' + str(no_of_digits) + 'f}'
                values.append(fmt_str.format(sensor.get_value()))
            elif type(value) is dict:
                values.append(str(value))
            elif type(value) is list:
                values.append(str(value))
            else:
                raise TypeError("unhandled type err!")
        return values

    def get_sensor_keys(self, enable_check: bool = True) -> list:
        keys = []
        for sensor in self._sensors_list.values():

            if enable_check and not sensor.enabled():
                continue
            key = sensor.get_src_name()
            if key is None:
                # do nothing
                keys.append("None")
            keys.append(key)
        return keys


def main(argv=None):
    if argv is None:
        argv = sys.argv
    _log.debug('main(), argv: {}'.format(argv))

    config = {
        "sensors": {
            "sensor_1": {
                "src_name": "Wind_Direction",
                "om2m_cnt": "Wind_Direction",
                "flag": True
            },
            "sensor_2": {
                "src_name": "Wind_Speed",
                "om2m_cnt": "Wind_Speed",
                "flag": True
            }
        }
    }

    print('Test-1')
    for k, v in config['sensors'].items():
        sensor = Sensor(**v)
        sensor.set_value(123)
        _log.debug('sensor: {}'.format(sensor))

    print('Test-2')
    sensors = Sensors(config['sensors'])
    print('value: {}'.format(sensors.get_sensor('sensor_2').get_value()))
    sensors.get_sensor('sensor_2').set_value(567)
    print('value: {}'.format(sensors.get_sensor('sensor_2').get_value()))

    print('Test-3')
    _log.debug('sensors: {}'.format(sensors))

    print('Test-4')
    sensors_str = str(sensors)
    n_sensors = json.loads(sensors_str)
    for k, v in n_sensors.items():
        sensor = Sensor(**(json.loads(v)))
        sensor.set_value(123)
        _log.debug('sensor: {}'.format(sensor))

    print('Test-5')
    new_sensors = Sensors(n_sensors)
    print('value: {}'.format(new_sensors.get_sensor('sensor_1').get_value()))
    new_sensors.get_sensor('sensor_1').set_value('[12,45,78,10]')
    print('value: {}'.format(sensors.get_sensor('sensor_1').get_value()))

    print('Test-6')
    _log.debug('sensors: {}'.format(sensors))

    return


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        pass