"""Verify models and schemas are importable."""
import sys
sys.path.insert(0, r"c:\dev\garbage-app\backend")

from app.models import UploadedImage, User
from app.schemas import ImageUploadResponse, ImageErrorResponse

print("Models and schemas imported successfully")
print("UploadedImage columns:", [c.name for c in UploadedImage.__table__.columns])
print("ImageUploadResponse fields:", list(ImageUploadResponse.model_fields.keys()))
print("ImageErrorResponse fields:", list(ImageErrorResponse.model_fields.keys()))
