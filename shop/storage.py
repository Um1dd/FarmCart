"""Signed Cloudinary uploads with stable image/video resource routing."""

from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.files.uploadedfile import UploadedFile
import cloudinary.uploader


class CatalogCloudinaryStorage(MediaCloudinaryStorage):
    def _get_resource_type(self, name):
        return "video" if "/videos/" in "/" + name else "image"

    def _save(self, name, content):
        name = self._prepend_prefix(self._normalise_name(name))
        result = self._upload(name, UploadedFile(content, name))
        # Retain an extension for FileExtensionValidator when editing existing videos.
        return result["public_id"] + "." + result["format"]

    def delete(self, name):
        public_id = name.rsplit(".", 1)[0]
        response = cloudinary.uploader.destroy(
            public_id, invalidate=True, resource_type=self._get_resource_type(name)
        )
        return response["result"] == "ok"
