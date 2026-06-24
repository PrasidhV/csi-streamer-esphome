#!/bin/bash
set -e

echo "Creating component directory..."
mkdir -p /config/esphome/components/csi_streamer
cd /config/esphome/components/csi_streamer

echo "Downloading component files from GitHub..."
curl -sL "https://raw.githubusercontent.com/PrasidhV/csi-streamer-esphome/master/components/csi_streamer/__init__.py" > __init__.py
echo "  __init__.py: $(wc -c < __init__.py) bytes"

curl -sL "https://raw.githubusercontent.com/PrasidhV/csi-streamer-esphome/master/components/csi_streamer/csi_streamer.h" > csi_streamer.h
echo "  csi_streamer.h: $(wc -c < csi_streamer.h) bytes"

curl -sL "https://raw.githubusercontent.com/PrasidhV/csi-streamer-esphome/master/components/csi_streamer/csi_streamer.cpp" > csi_streamer.cpp
echo "  csi_streamer.cpp: $(wc -c < csi_streamer.cpp) bytes"

curl -sL "https://raw.githubusercontent.com/PrasidhV/csi-streamer-esphome/master/components/csi_streamer/library.json" > library.json
echo "  library.json: $(wc -c < library.json) bytes"

curl -sL "https://raw.githubusercontent.com/PrasidhV/csi-streamer-esphome/master/components/csi_streamer/sdkconfig.defaults" > sdkconfig.defaults
echo "  sdkconfig.defaults: $(wc -c < sdkconfig.defaults) bytes"

echo ""
echo "Verifying files..."
ls -la

echo ""
echo "Done! Component files are in /config/esphome/components/csi_streamer/"
