# main.py
from fastapi import FastAPI
from bacnet_client import BACnetReader
from config_utils import load_config, get_node_info
import os
import sys

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

# Ensure the correct utils.py is imported (local, not PyPI)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Original-Code/Common')))
from bacnet_client_orig import Bacnet_Client

@app.get("/read_property")
def read_property(target_ip: str, obj_type: str, instance: int, prop: str):
    bacnet = BACnetReader("10.4.20.198/20:47809", "LivingLabs", 599)
    result = bacnet.read_property(target_ip, obj_type, instance, prop)
    return {"response": result}

@app.get("/read_node_92")
def read_node_92():
    # Use the original Bacnet_Client to get all node data
    bacnet_client = Bacnet_Client(CONFIG_PATH)
    all_data = bacnet_client.get_data()
    # Find node_92 data
    node_92_data = next((item for item in all_data if item['node_id'] == 'node_92'), None)
    if not node_92_data:
        return {"error": "node_92 not found in data"}
    # Convert sensors object to dict if needed
    sensors = node_92_data['sensors']
    if hasattr(sensors, 'to_dict'):
        sensors = sensors.to_dict()
    return {"node_92": sensors}
