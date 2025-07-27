# main.py
from fastapi import FastAPI, Request
import os
import sys

app = FastAPI()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../default-sr-arc.config')

# Ensure the correct utils.py is imported (local, not PyPI)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../Original_Code/Common')))
from bacnet_client_orig import Bacnet_Client

@app.on_event("startup")
def startup_event():
    app.state.bacnet_client = Bacnet_Client(CONFIG_PATH)

@app.get("/read_node_92")
def read_node_92(request: Request):
    bacnet_client = request.app.state.bacnet_client
    all_data = bacnet_client.get_data()
    node_92_data = next((item for item in all_data if item['node_id'] == 'node_92'), None)
    if not node_92_data:
        return {"error": "node_92 not found in data"}
    sensors = node_92_data['sensors']
    if hasattr(sensors, 'to_dict'):
        sensors = sensors.to_dict()
    return {"node_92": sensors}
