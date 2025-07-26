# main.py
from fastapi import FastAPI
from bacnet_client import BACnetReader
from config_utils import load_config, get_node_info
import os

app = FastAPI()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../default-sr-arc.config')

# Load config and create BACnetReader once at startup
config = load_config(CONFIG_PATH)
node_92_info = get_node_info(config, 'node_92')
raw_addr = config['bacnet']['local_interface']['device_address']
device_address = raw_addr.split('/')[0] if '/' in raw_addr else raw_addr
object_name = config['bacnet']['local_interface']['object_name']
object_id = config['bacnet']['local_interface']['object_id']
bacnet_reader = BACnetReader(device_address, object_name, object_id)

@app.get("/read_property")
def read_property(target_ip: str, obj_type: str, instance: int, prop: str):
    bacnet = BACnetReader("10.4.20.198/20:47809", "LivingLabs", 599)
    result = bacnet.read_property(target_ip, obj_type, instance, prop)
    return {"response": result}

@app.get("/read_node_92")
def read_node_92():
    if not node_92_info:
        return {"error": "node_92 not found in config"}
    sensor = config['sensors']['sensor_1']
    target_ip = config['bacnet']['dest']['device_address'].split(':')[0]
    obj_type = sensor['data_type'] if 'data_type' in sensor else 'analogInput'
    instance = int(node_92_info['src_name'])
    prop = 'presentValue'
    result = bacnet_reader.read_property(target_ip, obj_type, instance, prop)
    return {"node_92_response": result}
