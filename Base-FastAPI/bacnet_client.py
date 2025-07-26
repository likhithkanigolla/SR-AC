# bacnet_client.py
from bacpypes.app import BIPSimpleApplication
from bacpypes.local.device import LocalDeviceObject
from bacpypes.pdu import Address
from bacpypes.apdu import ReadPropertyRequest
from bacpypes.core import run, stop
from bacpypes.task import TaskManager
import threading

class BACnetReader:
    def __init__(self, device_address, object_name, object_id):
        self.device_address = device_address
        self.device = LocalDeviceObject(
            objectName=object_name,
            objectIdentifier=('device', object_id),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        self.application = BIPSimpleApplication(self.device, device_address)

    def read_property(self, target_ip, object_type, instance_number, property_id):
        request = ReadPropertyRequest(
            objectIdentifier=(object_type, instance_number),
            propertyIdentifier=property_id,
            destination=Address(target_ip)
        )
        response_container = []

        def send_and_wait():
            iocb = self.application.submit_request(request)
            iocb.wait()
            if iocb.ioError:
                response_container.append(f"Error: {iocb.ioError}")
            else:
                response_container.append(iocb.ioResponse)

        thread = threading.Thread(target=send_and_wait)
        thread.start()
        thread.join(timeout=5)
        stop()
        return str(response_container[0]) if response_container else "No response"

