import os
from io import BytesIO
from unittest.mock import patch
from django.test import SimpleTestCase

class HostedMediaTests(SimpleTestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'CLOUDINARY_URL': 'cloudinary://test-key:test-secret@test-cloud'})
        self.environment.start()
        from core.hosted_storage import HostedMediaStorage
        self.storage = HostedMediaStorage()

    def tearDown(self):
        self.environment.stop()

    @patch('cloudinary.uploader.upload', return_value={'public_id': 'products/test'})
    def test_product_images_use_public_image_storage(self, upload):
        self.storage._upload('products/photo.png', BytesIO(b'test'))
        options = upload.call_args.kwargs
        self.assertEqual(options['resource_type'], 'image')
        self.assertNotIn('type', options)

    @patch('cloudinary.uploader.upload', return_value={'public_id': 'kyc/test.pdf'})
    def test_kyc_uploads_require_authenticated_raw_delivery(self, upload):
        self.storage._upload('kyc/document.pdf', BytesIO(b'test'))
        self.assertEqual(upload.call_args.kwargs['resource_type'], 'raw')
        self.assertEqual(upload.call_args.kwargs['type'], 'authenticated')

    def test_kyc_downloads_are_signed_and_expiring(self):
        url = self.storage.url('kyc/document.pdf')
        self.assertIn('/raw/download', url)
        self.assertIn('type=authenticated', url)
        self.assertIn('expires_at=', url)
        self.assertIn('signature=', url)
