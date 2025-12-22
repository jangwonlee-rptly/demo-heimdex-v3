# RunPod CLIP Worker Dockerfile
# Optimized for GPU inference with CUDA support

# Use NVIDIA CUDA base image for GPU support
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install Python 3.10 and system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3.10 -m pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN python3.10 -m pip install -r requirements.txt

# Copy handler code
COPY handler.py .

# Pre-download CLIP model to reduce cold start time
# This runs at build time and caches the model in the image
RUN python3.10 -c "\
import open_clip; \
import torch; \
print('Pre-downloading CLIP model...'); \
model, _, preprocess = open_clip.create_model_and_transforms( \
    model_name='ViT-B-32', \
    pretrained='openai', \
    device='cpu' \
); \
print('Model downloaded successfully'); \
"

# RunPod expects the handler to be in /app
# The handler will be started by RunPod's infrastructure

# Default command (RunPod will override this)
CMD ["python3.10", "handler.py"]
