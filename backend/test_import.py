"""Quick import test for FileStorageService"""
from app.services.file_storage import FileStorageService

service = FileStorageService(upload_dir="test_uploads")
print(f"Import successful. Upload dir: {service.upload_dir}")

# Test filename generation
filename = service._generate_filename("photo.jpg")
print(f"Generated filename: {filename}")
assert filename.endswith(".jpg")
assert len(filename) == 36  # 32 hex chars + 4 for ".jpg"

filename_png = service._generate_filename("image.png")
print(f"Generated filename (png): {filename_png}")
assert filename_png.endswith(".png")

# Cleanup
import os
import shutil
if os.path.exists("test_uploads"):
    shutil.rmtree("test_uploads")

print("All checks passed!")
