#!/usr/bin/env python3
"""
Test script to verify RunPod Pod is using GPU.

Usage:
    export RUNPOD_POD_URL="https://your-pod-id-8000.proxy.runpod.net"
    export EMBEDDING_HMAC_SECRET="your-secret"
    python test_runpod_gpu.py
"""

import hashlib
import hmac
import json
import os
import sys
import time

import requests


def main():
    # Get configuration
    pod_url = os.getenv("RUNPOD_POD_URL")
    secret = os.getenv("EMBEDDING_HMAC_SECRET")

    if not pod_url:
        print("❌ RUNPOD_POD_URL environment variable not set")
        print("\nUsage:")
        print('  export RUNPOD_POD_URL="https://your-pod-id-8000.proxy.runpod.net"')
        print('  export EMBEDDING_HMAC_SECRET="your-secret"')
        print("  python test_runpod_gpu.py")
        sys.exit(1)

    if not secret:
        print("❌ EMBEDDING_HMAC_SECRET environment variable not set")
        sys.exit(1)

    # Remove trailing slash
    pod_url = pod_url.rstrip("/")

    print("=" * 70)
    print("RunPod Pod GPU Verification Test")
    print("=" * 70)
    print()

    # Step 1: Health check
    print("1️⃣  Checking health endpoint for GPU status...")
    print(f"   URL: {pod_url}/health")
    print()

    try:
        response = requests.get(f"{pod_url}/health", timeout=30)
        response.raise_for_status()
        health = response.json()

        print("   Response:")
        print(f"   {json.dumps(health, indent=2)}")
        print()

        # Verify GPU
        device = health.get("device")
        cuda_version = health.get("cuda_version")

        if device == "cuda":
            print(f"   ✅ GPU ENABLED - Device: {device}")
            print(f"   ✅ CUDA Version: {cuda_version}")
            print(f"   ✅ PyTorch: {health.get('torch_version')}")
            print(f"   ✅ Model: {health.get('model_name')} ({health.get('pretrained')})")
        elif device == "cpu":
            print(f"   ❌ GPU NOT ENABLED - Device: {device}")
            print("   ⚠️  Your Pod is running on CPU, not GPU!")
            print()
            print("   Possible causes:")
            print("   - RunPod Pod not configured with GPU")
            print("   - Docker image not using CUDA base")
            print("   - PyTorch not built with CUDA support")
            print()
            sys.exit(1)
        else:
            print(f"   ⚠️  Unknown device: {device}")
            sys.exit(1)

    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        sys.exit(1)

    print()
    print("-" * 70)
    print()

    # Step 2: Inference timing test
    print("2️⃣  Running inference test to verify GPU performance...")
    print()

    image_url = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"
    ts = int(time.time())
    canonical = f"POST|/v1/embed/image|{image_url}"
    message = f"{canonical}|{ts}"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    payload = {
        "image_url": image_url,
        "request_id": "gpu-test",
        "normalize": True,
        "auth": {"ts": ts, "sig": sig},
    }

    try:
        start = time.time()
        response = requests.post(f"{pod_url}/v1/embed/image", json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        elapsed = time.time() - start

        print(f"   Total request time: {elapsed * 1000:.1f}ms")
        print()

        # Extract timings
        timings = data.get("timings", {})
        download_ms = timings.get("download_ms", 0)
        inference_ms = timings.get("inference_ms", 0)
        total_ms = timings.get("total_ms", 0)

        print("   Detailed timings:")
        print(f"   - Download:  {download_ms:>7.1f}ms")
        print(f"   - Inference: {inference_ms:>7.1f}ms  ⚡ GPU-accelerated")
        print(f"   - Total:     {total_ms:>7.1f}ms")
        print()

        # Verify device in response
        response_device = data.get("device")
        if response_device == "cuda":
            print(f"   ✅ Response confirms GPU device: {response_device}")
        else:
            print(f"   ⚠️  Response device: {response_device}")

        print()

        # Performance benchmark
        print("   Performance analysis:")
        if inference_ms < 100:
            print(f"   ✅ EXCELLENT - Inference time {inference_ms:.1f}ms is GPU-tier performance")
            print("      (GPU typically: 20-100ms, CPU typically: 500-2000ms)")
        elif inference_ms < 300:
            print(f"   ⚠️  ACCEPTABLE - Inference time {inference_ms:.1f}ms")
            print("      This could be GPU, but performance seems slower than expected")
            print("      Check GPU utilization in RunPod dashboard")
        else:
            print(f"   ❌ SLOW - Inference time {inference_ms:.1f}ms is CPU-tier performance")
            print("      GPU should be 20-100ms, this looks like CPU")
            print("      Your Pod may not be using the GPU properly!")

        print()

        # Verify embedding
        embedding = data.get("embedding", [])
        print(f"   ✅ Embedding dimension: {data.get('dim')} (expected 512)")
        print(f"   ✅ First 5 values: {embedding[:5]}")

    except Exception as e:
        print(f"   ❌ Inference test failed: {e}")
        sys.exit(1)

    print()
    print("=" * 70)
    print("✅ GPU Verification Complete")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  • Device: {device}")
    print(f"  • CUDA Version: {cuda_version}")
    print(f"  • Inference Time: {inference_ms:.1f}ms")
    print()

    if device == "cuda" and inference_ms < 100:
        print("🎉 Your RunPod Pod is successfully using GPU acceleration!")
    elif device == "cuda":
        print("⚠️  GPU is enabled but performance seems slower than expected")
        print("   Check RunPod dashboard for GPU utilization")
    else:
        print("❌ GPU is not being used - check your RunPod Pod configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()
