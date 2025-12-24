"""
Image download utilities with safety limits and concurrency control.
"""

import asyncio
import io
import logging
from typing import List, Optional, Tuple

import aiohttp
from PIL import Image

from app.settings import settings

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Image download error."""

    pass


async def download_image(
    session: aiohttp.ClientSession, image_url: str, request_id: Optional[str] = None
) -> Image.Image:
    """
    Download image from URL with safety limits.

    Args:
        session: aiohttp ClientSession for connection pooling
        image_url: URL to download from
        request_id: Optional request ID for logging

    Returns:
        PIL Image object (RGB)

    Raises:
        DownloadError: If download fails or exceeds limits
    """
    try:
        logger.info(f"Downloading image: url={image_url[:100]}..., request_id={request_id}")

        timeout = aiohttp.ClientTimeout(total=settings.image_download_timeout_s)

        async with session.get(image_url, timeout=timeout) as response:
            response.raise_for_status()

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > settings.max_image_size_bytes:
                raise DownloadError(
                    f"Image too large: {content_length} bytes > {settings.max_image_size_bytes}"
                )

            # Download with size limit
            image_data = io.BytesIO()
            downloaded_bytes = 0

            async for chunk in response.content.iter_chunked(8192):
                downloaded_bytes += len(chunk)
                if downloaded_bytes > settings.max_image_size_bytes:
                    raise DownloadError(
                        f"Image download exceeded {settings.max_image_size_bytes} bytes"
                    )
                image_data.write(chunk)

            image_data.seek(0)
            image = Image.open(image_data).convert("RGB")

            logger.info(
                f"Image downloaded successfully: size={image.size}, "
                f"bytes={downloaded_bytes}, request_id={request_id}"
            )
            return image

    except asyncio.TimeoutError as e:
        logger.error(f"Image download timeout: url={image_url[:100]}..., request_id={request_id}")
        raise DownloadError(f"Image download timeout after {settings.image_download_timeout_s}s")
    except aiohttp.ClientError as e:
        logger.error(
            f"Image download HTTP error: {e}, url={image_url[:100]}..., request_id={request_id}"
        )
        raise DownloadError(f"Image download failed: {e}")
    except Exception as e:
        logger.error(
            f"Image processing error: {e}, url={image_url[:100]}..., request_id={request_id}"
        )
        raise DownloadError(f"Image processing failed: {e}")


async def download_images_batch(
    image_urls: List[str], request_ids: List[str]
) -> List[Tuple[Optional[Image.Image], Optional[str]]]:
    """
    Download multiple images concurrently with controlled parallelism.

    Args:
        image_urls: List of image URLs to download
        request_ids: List of request IDs (parallel to image_urls)

    Returns:
        List of tuples: (Image | None, error_message | None)
        - Success: (Image, None)
        - Failure: (None, error_message)
    """
    if len(image_urls) != len(request_ids):
        raise ValueError("image_urls and request_ids must have same length")

    results: List[Tuple[Optional[Image.Image], Optional[str]]] = [
        (None, None) for _ in image_urls
    ]

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(settings.download_concurrency)

    async def download_with_semaphore(
        idx: int, url: str, request_id: str
    ) -> None:
        """Download single image with semaphore."""
        async with semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    image = await download_image(session, url, request_id)
                    results[idx] = (image, None)
            except DownloadError as e:
                logger.warning(
                    f"Download failed for request_id={request_id}: {e}"
                )
                results[idx] = (None, str(e))
            except Exception as e:
                logger.error(
                    f"Unexpected download error for request_id={request_id}: {e}"
                )
                results[idx] = (None, f"Unexpected error: {e}")

    # Create tasks for all downloads
    tasks = [
        download_with_semaphore(idx, url, request_id)
        for idx, (url, request_id) in enumerate(zip(image_urls, request_ids))
    ]

    # Wait for all downloads to complete
    await asyncio.gather(*tasks)

    return results
