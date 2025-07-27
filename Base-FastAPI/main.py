# main.py
from fastapi import FastAPI, Request, Body
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
    node_92_data = bacnet_client.get_node_data('node_92')
    if not node_92_data:
        return {"error": "node_92 not found or failed to read"}
    sensors = node_92_data['sensors']
    if hasattr(sensors, 'to_dict'):
        sensors = sensors.to_dict()
    return {"node_92": sensors}

@app.post("/control_ac/{node_id}")
def control_ac(node_id: str, request: Request, turn_on: bool = Body(..., embed=True)):
    bacnet_client = request.app.state.bacnet_client
    node_info = bacnet_client._nodes.get(node_id)
    if not node_info:
        return {"error": f"Node {node_id} not found"}
    bac_id = int(node_info['src_name'])
    dest_addrs = bacnet_client._bacnet_dest['device_address']
    sensor_id = None
    for sid, sdef in bacnet_client._sensors.items():
        if sdef.get('om2m_cnt') == 'Start Stop Status':
            sensor_id = sid
            break
    if not sensor_id:
        return {"error": "Start Stop Status sensor not found in config"}
    object_type = bacnet_client._sensors[sensor_id]['data_type']
    instance_id = int(bacnet_client._sensors[sensor_id]['src_name']) + bac_id * 256
    value = 1 if turn_on else 0
    # Import bacpypes modules here to avoid import errors at startup
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
    deferred(bacnet_client._this_application.request_io, iocb)
    run()
    if iocb.ioError:
        return {"error": str(iocb.ioError)}
    return {"status": "success", "node_id": node_id, "turned_on": turn_on}
