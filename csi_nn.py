#!/usr/bin/env3
"""
CSI-based Person Presence Detection NN
Uses raw CSI amplitude data from multiple ESP32s to identify who is in which room.

Usage:
    python csi_nn.py --mode collect --person prasidh --room living_room --duration 120
    python csi_nn.py --mode train
    python csi_nn.py --mode run
    python csi_nn.py --mode status
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ── Configuration ──────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / "csi_nn"
MODEL_FILE = DATA_DIR / "csi_model.npz"
TRAINING_DATA_FILE = DATA_DIR / "csi_training_data.jsonl"
METADATA_FILE = DATA_DIR / "metadata.json"

# CSI configuration
NUM_SUBCARRIERS = 52
WINDOW_SIZE = 50  # 50 packets = ~0.5 seconds at 100Hz

# People to track
PEOPLE = ["prasidh", "amma", "rakshu", "appa"]

# Rooms
ROOMS = ["living_room", "bedroom"]

# ── Data Collection ────────────────────────────────────────────────────────────

def collect_training_data(person, room, duration_seconds=120):
    """
    Collect CSI training data by reading from the raw CSI log file.
    The CSI receiver must be running and logging data.
    """
    print(f"Collecting CSI data: {person} in {room} for {duration_seconds}s")
    print(f"Make sure ONLY {person} is in the {room}.")
    print("Starting in 5 seconds...")
    time.sleep(5)
    
    # Find the latest CSI log file
    log_dir = Path.home() / "csi_data"
    log_files = sorted(log_dir.glob("csi_raw_*.jsonl"), reverse=True)
    
    if not log_files:
        print("No CSI log files found. Make sure csi_receiver.py is running.")
        return
    
    log_file = log_files[0]
    print(f"Reading from: {log_file}")
    
    # Collect samples for the specified duration
    samples = []
    start_time = time.time()
    
    with open(log_file, "r") as f:
        # Seek to end of file
        f.seek(0, 2)
        
        while time.time() - start_time < duration_seconds:
            line = f.readline()
            if not line:
                time.sleep(0.01)
                continue
            
            try:
                packet = json.loads(line.strip())
                if packet.get("room") == room:
                    samples.append({
                        "timestamp": packet["timestamp"],
                        "amplitudes": packet["amplitudes"],
                        "rssi": packet["rssi"],
                        "person": person,
                        "room": room,
                    })
            except (json.JSONDecodeError, KeyError):
                continue
            
            if len(samples) % 100 == 0:
                elapsed = time.time() - start_time
                print(f"  Collected {len(samples)} samples ({elapsed:.1f}s / {duration_seconds}s)")
    
    # Save training data
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_DATA_FILE, "a") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")
    
    print(f"Saved {len(samples)} CSI samples for {person} in {room}")
    return samples


# ── Feature Extraction ─────────────────────────────────────────────────────────

def extract_features_from_samples(samples, window_size=WINDOW_SIZE):
    """
    Extract NN features from raw CSI samples.
    
    For each window of packets, compute per-subcarrier statistics:
    - Mean, std, max, min, range of amplitude
    """
    if len(samples) < window_size:
        return None, None
    
    feature_list = []
    label_list = []
    
    for i in range(len(samples) - window_size + 1):
        window = samples[i:i + window_size]
        
        # Stack amplitudes: (window_size, num_subcarriers)
        amp_matrix = np.array([s["amplitudes"] for s in window], dtype=np.float32)
        
        # Statistical features per subcarrier
        mean_amp = np.mean(amp_matrix, axis=0)
        std_amp = np.std(amp_matrix, axis=0)
        max_amp = np.max(amp_matrix, axis=0)
        min_amp = np.min(amp_matrix, axis=0)
        range_amp = max_amp - min_amp
        
        # Combine all features: 5 stats * 52 subcarriers = 260 features
        features = np.concatenate([mean_amp, std_amp, max_amp, min_amp, range_amp])
        
        feature_list.append(features)
        label_list.append(window[0]["person"])
    
    if not feature_list:
        return None, None
    
    return np.array(feature_list, dtype=np.float32), np.array(label_list)


# ── Neural Network ─────────────────────────────────────────────────────────────

class CSIPresenceNN:
    """Neural network for person presence detection from raw CSI data."""
    
    def __init__(self, input_size, num_classes, hidden1=256, hidden2=128, hidden3=64):
        self.input_size = input_size
        self.num_classes = num_classes
        
        # Xavier initialization
        self.W1 = np.random.randn(input_size, hidden1).astype(np.float32) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros(hidden1, dtype=np.float32)
        self.W2 = np.random.randn(hidden1, hidden2).astype(np.float32) * np.sqrt(2.0 / hidden1)
        self.b2 = np.zeros(hidden2, dtype=np.float32)
        self.W3 = np.random.randn(hidden2, hidden3).astype(np.float32) * np.sqrt(2.0 / hidden2)
        self.b3 = np.zeros(hidden3, dtype=np.float32)
        self.W4 = np.random.randn(hidden3, num_classes).astype(np.float32) * np.sqrt(2.0 / hidden3)
        self.b4 = np.zeros(num_classes, dtype=np.float32)
    
    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1
        self.a1 = np.maximum(0, self.z1)
        self.z2 = self.a1 @ self.W2 + self.b2
        self.a2 = np.maximum(0, self.z2)
        self.z3 = self.a2 @ self.W3 + self.b3
        self.a3 = np.maximum(0, self.z3)
        self.z4 = self.a3 @ self.W4 + self.b4
        exp_z = np.exp(self.z4 - np.max(self.z4, axis=1, keepdims=True))
        self.a4 = exp_z / np.sum(exp_z, axis=1, keepdims=True)
        return self.a4
    
    def predict(self, X):
        return self.forward(X)
    
    def predict_class(self, X):
        probs = self.predict(X)
        return np.argmax(probs, axis=1)
    
    def train(self, X, y, epochs=100, lr=0.001, batch_size=32, verbose=True):
        n_samples = X.shape[0]
        y_onehot = np.zeros((n_samples, self.num_classes), dtype=np.float32)
        y_onehot[np.arange(n_samples), y] = 1.0
        
        for epoch in range(epochs):
            indices = np.random.permutation(n_samples)
            X_shuffled = X[indices]
            y_shuffled = y_onehot[indices]
            
            epoch_loss = 0
            n_batches = 0
            
            for i in range(0, n_samples, batch_size):
                X_batch = X_shuffled[i:i + batch_size]
                y_batch = y_shuffled[i:i + batch_size]
                
                probs = self.forward(X_batch)
                loss = -np.mean(np.sum(y_batch * np.log(probs + 1e-8), axis=1))
                epoch_loss += loss
                n_batches += 1
                
                # Backward pass
                dz4 = probs - y_batch
                dW4 = self.a3.T @ dz4 / X_batch.shape[0]
                db4 = np.mean(dz4, axis=0)
                
                da3 = dz4 @ self.W4.T
                dz3 = da3 * (self.z3 > 0).astype(np.float32)
                dW3 = self.a2.T @ dz3 / X_batch.shape[0]
                db3 = np.mean(dz3, axis=0)
                
                da2 = dz3 @ self.W3.T
                dz2 = da2 * (self.z2 > 0).astype(np.float32)
                dW2 = self.a1.T @ dz2 / X_batch.shape[0]
                db2 = np.mean(dz2, axis=0)
                
                da1 = dz2 @ self.W2.T
                dz1 = da1 * (self.z1 > 0).astype(np.float32)
                dW1 = X_batch.T @ dz1 / X_batch.shape[0]
                db1 = np.mean(dz1, axis=0)
                
                self.W4 -= lr * dW4
                self.b4 -= lr * db4
                self.W3 -= lr * dW3
                self.b3 -= lr * db3
                self.W2 -= lr * dW2
                self.b2 -= lr * db2
                self.W1 -= lr * dW1
                self.b1 -= lr * db1
            
            if verbose and (epoch + 1) % 10 == 0:
                avg_loss = epoch_loss / n_batches
                preds = self.predict_class(X)
                accuracy = np.mean(preds == y)
                print(f"  Epoch {epoch + 1}/{epochs} — Loss: {avg_loss:.4f} — Accuracy: {accuracy:.2%}")
    
    def save(self, path):
        np.savez(path, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2,
                 W3=self.W3, b3=self.b3, W4=self.W4, b4=self.b4)
        print(f"Model saved to {path}")
    
    def load(self, path):
        data = np.load(path)
        self.W1 = data["W1"]
        self.b1 = data["b1"]
        self.W2 = data["W2"]
        self.b2 = data["b2"]
        self.W3 = data["W3"]
        self.b3 = data["b3"]
        self.W4 = data["W4"]
        self.b4 = data["b4"]
        print(f"Model loaded from {path}")


# ── Training Pipeline ──────────────────────────────────────────────────────────

def train_model():
    """Train the CSI-based presence detection model."""
    print("=" * 60)
    print("Training CSI Presence Detection Model")
    print("=" * 60)
    
    if not TRAINING_DATA_FILE.exists():
        print("No training data found. Run collection first.")
        return
    
    # Load training data
    samples = []
    with open(TRAINING_DATA_FILE) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"Loaded {len(samples)} CSI samples")
    
    # Group by person
    by_person = {}
    for s in samples:
        p = s.get("person", "unknown")
        if p not in by_person:
            by_person[p] = []
        by_person[p].append(s)
    
    for person, data in sorted(by_person.items()):
        print(f"  {person}: {len(data)} samples")
    
    # Extract features per person
    all_features = []
    all_labels = []
    class_names = sorted(by_person.keys())
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    
    for person, data in by_person.items():
        features, labels = extract_features_from_samples(data)
        if features is not None:
            all_features.append(features)
            all_labels.append(np.full(len(features), class_to_idx[person]))
    
    if not all_features:
        print("Not enough data to extract features")
        return
    
    X = np.concatenate(all_features, axis=0)
    y = np.concatenate(all_labels, axis=0)
    
    print(f"\nFeature matrix: {X.shape}")
    print(f"Classes: {class_to_idx}")
    
    # Normalize
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0) + 1e-8
    X_norm = (X - mean) / std
    
    # Split train/val
    n_train = int(0.8 * len(X))
    indices = np.random.permutation(len(X))
    X_train = X_norm[indices[:n_train]]
    y_train = y[indices[:n_train]]
    X_val = X_norm[indices[n_train:]]
    y_val = y[indices[n_train:]]
    
    print(f"Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Create and train model
    input_size = X.shape[1]
    num_classes = len(class_names)
    
    model = CSIPresenceNN(input_size=input_size, num_classes=num_classes)
    
    print("\nTraining...")
    model.train(X_train, y_train, epochs=100, lr=0.001, batch_size=32)
    
    # Evaluate
    val_preds = model.predict_class(X_val)
    val_accuracy = np.mean(val_preds == y_val)
    print(f"\nValidation accuracy: {val_accuracy:.2%}")
    
    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_FILE)
    
    metadata = {
        "classes": class_names,
        "class_to_idx": class_to_idx,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "window_size": WINDOW_SIZE,
        "num_subcarriers": NUM_SUBCARRIERS,
        "input_size": input_size,
        "val_accuracy": float(val_accuracy),
        "trained_at": datetime.now().isoformat(),
    }
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nModel and metadata saved to {DATA_DIR}")
    return model, metadata


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CSI Person Presence Detection NN")
    parser.add_argument("--mode", choices=["collect", "train", "run", "status"], required=True)
    parser.add_argument("--person", choices=PEOPLE, help="Person name")
    parser.add_argument("--room", choices=ROOMS, help="Room name")
    parser.add_argument("--duration", type=int, default=120, help="Collection duration in seconds")
    
    args = parser.parse_args()
    
    if args.mode == "status":
        print("CSI Presence Detection Status")
        if TRAINING_DATA_FILE.exists():
            samples = [json.loads(l) for l in open(TRAINING_DATA_FILE) if l.strip()]
            by_person = {}
            for s in samples:
                p = s.get("person", "unknown")
                by_person[p] = by_person.get(p, 0) + 1
            print(f"Training samples: {len(samples)}")
            for p, c in sorted(by_person.items()):
                print(f"  {p}: {c}")
        else:
            print("No training data")
        
        if MODEL_FILE.exists():
            print("Model: trained")
        else:
            print("Model: not trained")
    
    elif args.mode == "collect":
        if not args.person or not args.room:
            print("ERROR: --person and --room required")
            sys.exit(1)
        collect_training_data(args.person, args.room, args.duration)
    
    elif args.mode == "train":
        train_model()
    
    elif args.mode == "run":
        print("Real-time inference not yet implemented")
        print("Use --mode train first after collecting data")


if __name__ == "__main__":
    main()
