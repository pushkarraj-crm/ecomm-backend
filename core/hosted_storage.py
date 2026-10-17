"""Persistent product images and authenticated KYC documents on Cloudinary."""

import os
import time
import cloudinary.uploader
import cloudinary.utils
from cloudinary_storage.storage import MediaCloudinaryStorage


class HostedMediaStorage(MediaCloudinaryStorage):
    @staticmethod
    def _private(name):
        return name.replace("\\", "/").startswith("kyc/")

    def _get_resource_type(self, name):
        return "raw" if self._private(name) else "image"

    def _upload(self, name, content):
        options = {
            "use_filename": True,
            "unique_filename": True,
            "resource_type": self._get_resource_type(name),
            "tags": self.TAG,
        }
        if os.path.dirname(name):
            options["folder"] = os.path.dirname(name)
        if self._private(name):
            options["type"] = "authenticated"
        return cloudinary.uploader.upload(content, **options)

    def _get_url(self, name):
        if self._private(name):
            return cloudinary.utils.private_download_url(
                name,
                None,
                resource_type="raw",
                type="authenticated",
                expires_at=int(time.time()) + 60,
            )
        return super()._get_url(name)

    def delete(self, name):
        if self._private(name):
            return (
                cloudinary.uploader.destroy(
                    name, resource_type="raw", type="authenticated", invalidate=True
                )["result"]
                == "ok"
            )
        return super().delete(name)
