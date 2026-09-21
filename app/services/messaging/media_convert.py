"""Outbound-image normalization shared by the Meta-backed adapters.

The composer accepts whatever ALLOWED_PHOTO_EXTENSIONS allows (jpg/jpeg/png/
webp/heic — see app/services/photo_service.py for the same set used
elsewhere), but WhatsApp's Cloud API only accepts image/jpeg or image/png,
and heic in particular isn't accepted by either Meta platform. Re-encoding
every outbound photo to JPEG sidesteps format-support guesswork entirely.
"""
from __future__ import annotations

import io

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()


def to_jpeg_bytes(file_path: str, quality: int = 90) -> bytes:
    img = Image.open(file_path)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=quality)
    return buf.getvalue()
