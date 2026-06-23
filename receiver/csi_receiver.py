#!/usr/bin/env3
"""
CSI Streamer Receiver for Windows
Receives raw CSI data from ESP32s via UDP and saves to disk for NN training.

Usage:
    python csi_receiver.py
"""

import argparse
import json
import os
import socket
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

# ── Configuration ──────────────────────────────────────────────────────────────

CSI_MAGIC = 0x43534920  # "CSI "
CSIPkt_FORMAT = "<I Q 6s B B 52B"  # magic, seq, mac, rssi, n_sc, data[52]
CSIPkt_SIZE = struct.calcsize(CSIPkt_FORMAT)

LISTEN_PORTS = [5000, 5001]  # Living room, Bedroom
OUTPUT_DIR = Path.home() / "csi_data"

# ── CSI Packet Parser ─────────────────────────────────────────────────────────

def parse_csi_packet(data):
    """Parse a raw CSI packet from ESP32."""
    if len(data) < CSIPkt_SIZE:
        return None
    
    unpacked = struct.unpack(CSIPkt_FORMAT, data[:CSIPkt_SIZE])
    
    magic = unpacked[0]
    if magic != CSI_MAGIC:
        return None
    
    seq = unpacked[1]
    mac = ":".join(f"{b:02x}" for b in unpacked[2])
    rssi = unpacked[3]
    n_sc = unpacked[4]
    amplitudes = list(unpacked[5:5+min(n_sc, 52)])
    
    return {
        "magic": magic,
        "sequence": seq,
        "mac": mac,
        "rssi": rssi,
        "num_subcarriers": n_sc,
        "amplitudes": amplitudes,
        "timestamp": time.time(),
    }


# ── CSI Receiver ──────────────────────────────────────────────────────────────

class CSIReceiver:
    """Receives CSI data from multiple ESP32s via UDP."""
    
    def __init__(self, listen_ports=LISTEN_PORTS, output_dir=OUTPUT_DIR):
        self.listen_ports = listen_ports
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create UDP sockets for each port
        self.sockets = {}
        for port in listen_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(0.1)
            self.sockets[port] = sock
            print(f"Listening on port {port}")
        
        # Per-device data buffers
        self.device_buffers = defaultdict(list)
        self.device_stats = defaultdict(lambda: {"packets": 0, "errors": 0, "last_seen": 0})
        
        # Raw data log
        self.log_file = None
        self.log_path = self.output_dir / f"csi_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        
    def start(self):
        """Start receiving CSI data."""
        print(f"CSI Receiver started")
        print(f"Output directory: {self.output_dir}")
        print(f"Logging to: {self.log_path}")
        print("Press Ctrl+C to stop\n")
        
        self.log_file = open(self.log_path, "w")
        
        try:
            while True:
                for port, sock in self.sockets.items():
                    try:
                        data, addr = sock.recvfrom(4096)
                        self.process_packet(data, addr, port)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"Error on port {port}: {e}")
                
                # Print stats every 5 seconds
                self.print_stats()
                
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            if self.log_file:
                self.log_file.close()
            for sock in self.sockets.values():
                sock.close()
            self.print_final_stats()
    
    def process_packet(self, data, addr, port):
        """Process a single CSI packet."""
        packet = parse_csi_packet(data)
        if packet is None:
            self.device_stats["unknown"]["errors"] += 1
            return
        
        # Determine room from port
        room = "living_room" if port == 5000 else "bedroom"
        device_key = f"{packet['mac']}_{room}"
        
        # Add room info
        packet["room"] = room
        packet["source_ip"] = addr[0]
        packet["source_port"] = port
        
        # Store in buffer (keep last 1000 packets per device)
        self.device_buffers[device_key].append(packet)
        if len(self.device_buffers[device_key]) > 1000:
            self.device_buffers[device_key] = self.device_buffers[device_key][-500:]
        
        # Update stats
        self.device_stats[device_key]["packets"] += 1
        self.device_stats[device_key]["last_seen"] = time.time()
        
        # Log to file
        if self.log_file:
            self.log_file.write(json.dumps(packet) + "\n")
    
    def print_stats(self):
        """Print receiver statistics."""
        now = time.time()
        active = sum(1 for s in self.device_stats.values() if now - s["last_seen"] < 5)
        total = sum(s["packets"] for s in self.device_stats.values())
        errors = sum(s["errors"] for s in self.device_stats.values())
        
        sys.stdout.write(
            f"\r[CSI] Packets: {total} | Active devices: {active} | "
            f"Errors: {errors} | Buffers: {len(self.device_buffers)}    "
        )
        sys.stdout.flush()
    
    def print_final_stats(self):
        """Print final statistics."""
        print("\n\n=== Final Statistics ===")
        for device_key, stats in sorted(self.device_stats.items()):
            print(f"  {device_key}: {stats['packets']} packets, {stats['errors']} errors")
        
        print(f"\nRaw data saved to: {self.log_path}")
        print(f"Total size: {self.log_path.stat().st_size / 1024 / 1024:.2f} MB")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CSI Streamer Receiver")
    parser.add_argument("--ports", nargs="+", type=int, default=LISTEN_PORTS,
                        help="UDP ports to listen on")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="Output directory for CSI data")
    
    args = parser.parse_args()
    
    receiver = CSIReceiver(
        listen_ports=args.ports,
        output_dir=args.output_dir,
    )
    receiver.start()


if __name__ == "__main__":
    main()
