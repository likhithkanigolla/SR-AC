#!/bin/bash
# Install BACnet tools and Wireshark for BACnet monitoring

sudo apt update
sudo apt install -y git build-essential cmake wireshark

# Clone BACnet-stack (official repo)
git clone https://github.com/bacnet-stack/bacnet-stack.git
cd bacnet-stack

# Build the tools
make clean
make

echo "BACnet tools built. Binaries are in ./bin"
echo "Example: ./bin/bacrp <device-ip> <object-type> <object-instance> <property>"

echo "Wireshark installed. You can use filter: bacnet"