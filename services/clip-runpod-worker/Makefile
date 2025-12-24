.PHONY: install run test smoke docker-build docker-run lint format clean help

PYTHON := python3
DOCKER_IMAGE := clip-pod-worker
DOCKER_TAG := 2.0

help:
	@echo "CLIP RunPod Worker - Development Tasks"
	@echo ""
	@echo "Available targets:"
	@echo "  install       - Install Python dependencies"
	@echo "  run           - Run FastAPI server locally (CPU mode)"
	@echo "  test          - Run pytest tests"
	@echo "  smoke         - Run smoke test (health + 1 image + 1 text)"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container locally"
	@echo "  lint          - Run linting (ruff)"
	@echo "  format        - Format code (black)"
	@echo "  clean         - Remove cache and temp files"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
	$(PYTHON) -m pip install pytest ruff black

run:
	@echo "Starting FastAPI server on http://localhost:8000"
	@echo "Set EMBEDDING_HMAC_SECRET or ALLOW_INSECURE_AUTH=1 before running"
	ALLOW_INSECURE_AUTH=1 $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	$(PYTHON) -m pytest tests/ -v

smoke:
	@echo "Running smoke test..."
	@echo ""
	@echo "1. Health check..."
	@curl -f http://localhost:8000/health || (echo "❌ Health check failed" && exit 1)
	@echo ""
	@echo "✓ Health check passed"
	@echo ""
	@echo "2. Single image embedding..."
	@$(PYTHON) -c '\
import hashlib; \
import hmac; \
import time; \
import requests; \
secret = "test-secret"; \
image_url = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=512"; \
ts = int(time.time()); \
canonical = f"POST|/v1/embed/image|{image_url}"; \
message = f"{canonical}|{ts}"; \
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest(); \
r = requests.post("http://localhost:8000/v1/embed/image", json={"image_url": image_url, "request_id": "smoke-img", "normalize": True, "auth": {"ts": ts, "sig": sig}}); \
r.raise_for_status(); \
data = r.json(); \
assert data["dim"] == 512, f"Expected dim=512, got {data[\"dim\"]}"; \
assert len(data["embedding"]) == 512, f"Expected 512 floats, got {len(data[\"embedding\"])}"; \
print(f"✓ Image embedding: dim={data[\"dim\"]}, first 5 values={data[\"embedding\"][:5]}")' || (echo "❌ Image embedding failed" && exit 1)
	@echo ""
	@echo "3. Text embedding..."
	@$(PYTHON) -c '\
import hashlib; \
import hmac; \
import time; \
import requests; \
secret = "test-secret"; \
text = "a person walking in the rain"; \
ts = int(time.time()); \
text_hash = hashlib.sha256(text.encode()).hexdigest(); \
canonical = f"POST|/v1/embed/text|{text_hash}"; \
message = f"{canonical}|{ts}"; \
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest(); \
r = requests.post("http://localhost:8000/v1/embed/text", json={"text": text, "request_id": "smoke-txt", "normalize": True, "auth": {"ts": ts, "sig": sig}}); \
r.raise_for_status(); \
data = r.json(); \
assert data["dim"] == 512, f"Expected dim=512, got {data[\"dim\"]}"; \
assert len(data["embedding"]) == 512, f"Expected 512 floats, got {len(data[\"embedding\"])}"; \
print(f"✓ Text embedding: dim={data[\"dim\"]}, first 5 values={data[\"embedding\"][:5]}")' || (echo "❌ Text embedding failed" && exit 1)
	@echo ""
	@echo "✅ All smoke tests passed!"

docker-build:
	docker build -f Dockerfile.pod -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run:
	docker run --rm -it -p 8000:8000 \
		-e EMBEDDING_HMAC_SECRET=test-secret \
		-e ALLOW_INSECURE_AUTH=1 \
		-e LOG_LEVEL=INFO \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

lint:
	$(PYTHON) -m ruff check app/ tests/

format:
	$(PYTHON) -m black app/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
