"""
RunPod CLIP Endpoint Smoke Test

This script tests the RunPod CLIP endpoint end-to-end:
1. Validates RunPod configuration
2. Uploads a test image to Supabase Storage
3. Generates signed URL
4. Calls RunPod endpoint with HMAC authentication
5. Validates response structure and embedding

Usage:
    # Set environment variables first
    export RUNPOD_API_KEY="your-api-key"
    export RUNPOD_CLIP_ENDPOINT_ID="your-endpoint-id"
    export EMBEDDING_HMAC_SECRET="your-secret"
    export SUPABASE_URL="your-supabase-url"
    export SUPABASE_SERVICE_ROLE_KEY="your-service-key"

    # Run smoke test
    python -m src.scripts.test_runpod_clip

    # Or with custom test image
    python -m src.scripts.test_runpod_clip --image /path/to/test.jpg
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.adapters import clip_inference
from src.adapters.supabase import storage
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def validate_configuration() -> bool:
    """
    Validate that all required environment variables are set.

    Returns:
        True if configuration is valid, False otherwise
    """
    logger.info("Validating configuration...")

    required_vars = {
        "RUNPOD_API_KEY": settings.runpod_api_key,
        "RUNPOD_CLIP_ENDPOINT_ID": settings.runpod_clip_endpoint_id,
        "EMBEDDING_HMAC_SECRET": settings.embedding_hmac_secret,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
    }

    missing = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing.append(var_name)
            logger.error(f"✗ {var_name} not set")
        else:
            # Show first 10 chars for verification
            preview = str(var_value)[:10] + "..." if len(str(var_value)) > 10 else str(var_value)
            logger.info(f"✓ {var_name}: {preview}")

    if missing:
        logger.error(f"\nMissing required environment variables: {', '.join(missing)}")
        return False

    # Check backend configuration
    if settings.clip_inference_backend != "runpod":
        logger.warning(
            f"⚠ CLIP_INFERENCE_BACKEND is '{settings.clip_inference_backend}' "
            f"(expected 'runpod')"
        )

    logger.info("✓ Configuration valid\n")
    return True


def upload_test_image(image_path: Path) -> tuple[str, str]:
    """
    Upload test image to Supabase Storage and generate signed URL.

    Args:
        image_path: Path to local test image

    Returns:
        Tuple of (storage_path, signed_url)

    Raises:
        Exception: If upload or signed URL generation fails
    """
    logger.info(f"Uploading test image: {image_path.name}")

    # Generate unique storage path
    timestamp = int(time.time())
    storage_path = f"test/clip-smoke-test-{timestamp}.jpg"

    try:
        # Upload to Supabase Storage
        public_url = storage.upload_file(
            image_path,
            storage_path,
            content_type="image/jpeg",
        )
        logger.info(f"✓ Image uploaded: {public_url[:60]}...")

        # Generate signed URL
        signed_url = storage.create_signed_url(
            storage_path,
            expires_in=300,  # 5 minutes
        )
        logger.info(f"✓ Signed URL created: {signed_url[:60]}...\n")

        return storage_path, signed_url

    except Exception as e:
        logger.error(f"✗ Upload failed: {e}")
        raise


def call_runpod_endpoint(signed_url: str, request_id: str = "smoke-test") -> dict:
    """
    Call RunPod CLIP endpoint with test image.

    Args:
        signed_url: Signed URL to test image
        request_id: Request identifier for tracking

    Returns:
        RunPod response dict

    Raises:
        clip_inference.ClipInferenceError: If request fails
    """
    logger.info(f"Calling RunPod CLIP endpoint (request_id={request_id})...")

    start_time = time.time()

    try:
        result = clip_inference.embed_image_url(
            image_url=signed_url,
            request_id=request_id,
        )

        duration = time.time() - start_time
        logger.info(f"✓ RunPod request completed in {duration:.3f}s\n")

        return result

    except clip_inference.ClipInferenceAuthError as e:
        logger.error(f"✗ Authentication error: {e}")
        raise
    except clip_inference.ClipInferenceTimeoutError as e:
        logger.error(f"✗ Timeout error: {e}")
        raise
    except clip_inference.ClipInferenceError as e:
        logger.error(f"✗ Inference error: {e}")
        raise


def validate_response(result: dict) -> bool:
    """
    Validate RunPod response structure and content.

    Args:
        result: RunPod response dict

    Returns:
        True if response is valid, False otherwise
    """
    logger.info("Validating response...")

    all_valid = True

    # Check required fields
    required_fields = ["embedding", "dim", "model", "normalized", "request_id"]
    for field in required_fields:
        if field in result:
            logger.info(f"✓ Field '{field}' present")
        else:
            logger.error(f"✗ Field '{field}' missing")
            all_valid = False

    # Validate embedding
    embedding = result.get("embedding")
    if embedding:
        if isinstance(embedding, list):
            logger.info(f"✓ Embedding is a list")

            expected_dim = 512
            actual_dim = len(embedding)
            if actual_dim == expected_dim:
                logger.info(f"✓ Embedding dimension: {actual_dim}")
            else:
                logger.error(
                    f"✗ Embedding dimension mismatch: {actual_dim} (expected {expected_dim})"
                )
                all_valid = False

            # Check that values are floats in reasonable range
            if all(isinstance(x, (int, float)) for x in embedding[:10]):
                logger.info(f"✓ Embedding values are numeric")
            else:
                logger.error(f"✗ Embedding contains non-numeric values")
                all_valid = False

            # Check normalization (L2 norm should be ~1.0 if normalized)
            import math
            norm = math.sqrt(sum(x * x for x in embedding))
            if 0.99 <= norm <= 1.01:
                logger.info(f"✓ Embedding is normalized (L2 norm: {norm:.4f})")
            else:
                logger.warning(f"⚠ Embedding may not be normalized (L2 norm: {norm:.4f})")

        else:
            logger.error(f"✗ Embedding is not a list (type: {type(embedding)})")
            all_valid = False
    else:
        logger.error(f"✗ Embedding is missing or None")
        all_valid = False

    # Log timing information if available
    timings = result.get("timings", {})
    if timings:
        logger.info("\nTiming breakdown:")
        logger.info(f"  Download: {timings.get('download_ms', 'N/A')}ms")
        logger.info(f"  Inference: {timings.get('inference_ms', 'N/A')}ms")
        logger.info(f"  Total: {timings.get('total_ms', 'N/A')}ms")

    # Log model information
    logger.info(f"\nModel information:")
    logger.info(f"  Model: {result.get('model', 'N/A')}")
    logger.info(f"  Pretrained: {result.get('pretrained', 'N/A')}")
    logger.info(f"  Normalized: {result.get('normalized', 'N/A')}")

    return all_valid


def cleanup_test_image(storage_path: str) -> None:
    """
    Clean up test image from Supabase Storage.

    Args:
        storage_path: Storage path to delete

    Note:
        Failures are logged but not raised (cleanup is best-effort)
    """
    try:
        logger.info(f"\nCleaning up test image: {storage_path}")
        # Note: Supabase Python client doesn't have a straightforward delete method
        # We'll leave the test image in place or you can manually delete it
        logger.info("ℹ Test image left in storage for manual cleanup if needed")
    except Exception as e:
        logger.warning(f"⚠ Cleanup failed (non-critical): {e}")


def create_test_image() -> Path:
    """
    Create a simple test image if none provided.

    Returns:
        Path to test image

    Raises:
        ImportError: If PIL not available
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError(
            "PIL (Pillow) required to generate test image. "
            "Install with: pip install pillow"
        )

    logger.info("Generating test image...")

    # Create a simple 512x512 test image
    img = Image.new("RGB", (512, 512), color=(73, 109, 137))
    draw = ImageDraw.Draw(img)

    # Draw text
    text = "CLIP Smoke Test"
    try:
        # Try to use a font if available
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except Exception:
        # Fall back to default font
        font = ImageFont.load_default()

    # Calculate text position (center)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((512 - text_width) // 2, (512 - text_height) // 2)

    draw.text(position, text, fill=(255, 255, 255), font=font)

    # Save to temp file
    test_image_path = Path("/tmp/clip_smoke_test.jpg")
    img.save(test_image_path, "JPEG", quality=95)

    logger.info(f"✓ Test image created: {test_image_path}\n")
    return test_image_path


def main():
    """Main smoke test execution."""
    parser = argparse.ArgumentParser(description="RunPod CLIP Endpoint Smoke Test")
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to test image (default: generate test image)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't clean up test image after test",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("RunPod CLIP Endpoint Smoke Test")
    logger.info("=" * 60 + "\n")

    try:
        # Step 1: Validate configuration
        if not validate_configuration():
            logger.error("\n❌ Smoke test FAILED: Invalid configuration")
            sys.exit(1)

        # Step 2: Get test image
        if args.image:
            if not args.image.exists():
                logger.error(f"✗ Test image not found: {args.image}")
                sys.exit(1)
            test_image_path = args.image
        else:
            test_image_path = create_test_image()

        # Step 3: Upload test image and get signed URL
        storage_path, signed_url = upload_test_image(test_image_path)

        # Step 4: Call RunPod endpoint
        result = call_runpod_endpoint(signed_url, request_id="smoke-test")

        # Step 5: Validate response
        is_valid = validate_response(result)

        # Step 6: Cleanup (optional)
        if not args.no_cleanup:
            cleanup_test_image(storage_path)

        # Final result
        logger.info("\n" + "=" * 60)
        if is_valid:
            logger.info("✅ Smoke test PASSED")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("❌ Smoke test FAILED: Response validation errors")
            logger.info("=" * 60)
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n\n⚠ Smoke test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ Smoke test FAILED: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
