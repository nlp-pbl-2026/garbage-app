import base64

import pytest
from pydantic import ValidationError

from app.schemas import MAX_SEARCH_IMAGE_BYTES, WasteGuideRequest


def _image(data: bytes = b"image", media_type: str = "image/png") -> dict:
    return {
        "media_type": media_type,
        "data_base64": base64.b64encode(data).decode(),
    }


def test_image_only_request_is_valid():
    request = WasteGuideRequest(image=_image())

    assert request.query == ""
    assert request.image is not None
    assert request.image.bedrock_format == "png"
    assert request.image.decoded_bytes() == b"image"


def test_request_requires_text_or_image():
    with pytest.raises(ValidationError, match="query or image is required"):
        WasteGuideRequest(query="   ")


def test_image_rejects_unsupported_media_type():
    with pytest.raises(ValidationError):
        WasteGuideRequest(image=_image(media_type="image/heic"))


def test_image_rejects_invalid_base64():
    with pytest.raises(ValidationError, match="valid base64"):
        WasteGuideRequest(
            image={"media_type": "image/png", "data_base64": "not-base64"}
        )


def test_image_rejects_payload_over_three_megabytes():
    with pytest.raises(ValidationError, match="3 MB or smaller"):
        WasteGuideRequest(image=_image(b"x" * (MAX_SEARCH_IMAGE_BYTES + 1)))
