# main.py
from fastapi import FastAPI
import os
import sys

app = FastAPI()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../default-sr-arc.config')

# Ensure the correct utils.py is imported (local, not PyPI)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Original_Code/Common')))
from bacnet_client_orig import Bacnet_Client

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
