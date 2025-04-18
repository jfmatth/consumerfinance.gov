import os
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from wagtail.documents.models import Document

from cdntools.backends import (
    MOCK_PURGED,
    AkamaiBackend,
    AkamaiDeletingBackend,
)
from cdntools.signals import cloudfront_cache_invalidation


class TestAkamaiBackend(TestCase):
    def setUp(self):
        self.credentials = {
            "CLIENT_TOKEN": "token",
            "CLIENT_SECRET": "secret",
            "ACCESS_TOKEN": "access token",
        }

    def test_no_credentials_raises(self):
        credentials = {
            "CLIENT_TOKEN": None,
            "CLIENT_SECRET": None,
            "ACCESS_TOKEN": None,
        }
        with self.assertRaises(ValueError):
            AkamaiBackend(credentials)

    def test_some_credentials_raises(self):
        credentials = {
            "CLIENT_TOKEN": "some-arbitrary-token",
            "CLIENT_SECRET": None,
            "ACCESS_TOKEN": None,
        }
        with self.assertRaises(ValueError):
            AkamaiBackend(credentials)

    def test_all_credentials_get_set(self):
        akamai_backend = AkamaiBackend(self.credentials)
        self.assertEqual(akamai_backend.client_token, "token")
        self.assertEqual(akamai_backend.client_secret, "secret")
        self.assertEqual(akamai_backend.access_token, "access token")

    @mock.patch("requests.post")
    @mock.patch.dict(
        os.environ,
        {
            "AKAMAI_OBJECT_ID": "12345",
            "AKAMAI_PURGE_ALL_URL": "http://purge",
        },
    )
    def test_post_all(self, mock_post):
        mock_post.return_value.status_code.return_value = 200
        mock_post.return_value.text = "response text"
        akamai_backend = AkamaiBackend(self.credentials)
        akamai_backend.post_all("invalidate")
        mock_post.assert_called_once_with(
            "http://purge",
            headers=akamai_backend.headers,
            data='{"action": "invalidate", "objects": ["12345"]}',
            auth=akamai_backend.auth,
        )

    @mock.patch("requests.post")
    @mock.patch.dict(
        os.environ,
        {
            "AKAMAI_OBJECT_ID": "12345",
            "AKAMAI_FAST_PURGE_URL": "http://fast_purge",
        },
    )
    def test_post(self, mock_post):
        mock_post.return_value.status_code.return_value = 200
        mock_post.return_value.text = "response text"
        akamai_backend = AkamaiBackend(self.credentials)
        akamai_backend.post("http://my/url", "invalidate")
        mock_post.assert_called_once_with(
            "http://fast_purge",
            headers=akamai_backend.headers,
            data='{"action": "invalidate", "objects": ["http://my/url"]}',
            auth=akamai_backend.auth,
        )

    def test_purge(self):
        akamai_backend = AkamaiBackend(self.credentials)
        with mock.patch.object(AkamaiBackend, "post") as mock_post:
            akamai_backend.purge("http://my/url")
        mock_post.assert_called_once_with("http://my/url", "invalidate")

    def test_purge_all(self):
        akamai_backend = AkamaiBackend(self.credentials)
        with mock.patch.object(AkamaiBackend, "post_all") as mock_post_all:
            akamai_backend.purge_all()
        mock_post_all.assert_called_once_with("invalidate")

    def test_purge_cache_tags(self):
        akamai_backend = AkamaiBackend(self.credentials)
        with mock.patch.object(AkamaiBackend, "post_tags") as mock_post_tags:
            akamai_backend.purge_by_tags(["test_slug"], action="invalidate")
        mock_post_tags.assert_called_once_with(
            ["test_slug"], action="invalidate"
        )

    @mock.patch.dict(
        os.environ,
        {
            "AKAMAI_FAST_PURGE_URL": "",
        },
    )
    def test_post_tags_no_url_config(self):
        akamai_backend = AkamaiBackend(self.credentials)
        self.assertIs(
            akamai_backend.post_tags(["test_slug"], action="delete"), None
        )

    @mock.patch.dict(
        os.environ,
        {
            "AKAMAI_FAST_PURGE_URL": "http://my/url/",
        },
    )
    @mock.patch("requests.post")
    def test_post_tags_with_url_config(self, mock_post):
        akamai_backend = AkamaiBackend(self.credentials)
        akamai_backend.post_tags(["test_slug"], action="delete")
        mock_post.assert_called_once_with(
            "http://my/tag/",
            headers=akamai_backend.headers,
            data='{"action": "delete", "objects": ["test_slug"]}',
            auth=akamai_backend.auth,
        )


class TestAkamaiDeletingBackend(TestCase):
    def setUp(self):
        self.credentials = {
            "CLIENT_TOKEN": "token",
            "CLIENT_SECRET": "secret",
            "ACCESS_TOKEN": "access token",
        }

    def test_purge(self):
        akamai_backend = AkamaiDeletingBackend(self.credentials)
        with mock.patch.object(AkamaiDeletingBackend, "post") as mock_post:
            akamai_backend.purge("http://my/url")
        mock_post.assert_called_once_with("http://my/url", "delete")

    def test_purge_all(self):
        akamai_backend = AkamaiDeletingBackend(self.credentials)
        with self.assertRaises(NotImplementedError):
            akamai_backend.purge_all()


@override_settings(
    WAGTAILFRONTENDCACHE={
        "files": {
            "BACKEND": "cdntools.backends.MockCacheBackend",
        },
    },
)
class CloudfrontInvalidationTest(TestCase):
    def setUp(self):
        self.document = Document(title="Test document")
        self.document_without_file = Document(title="Document without file")
        self.document.file.save(
            "example.txt", ContentFile("A boring example document")
        )
        MOCK_PURGED[:] = []

    def tearDown(self):
        self.document.file.delete()

    def test_document_saved_cache_purge_disabled(self):
        cloudfront_cache_invalidation(None, self.document)
        self.assertEqual(MOCK_PURGED, [])

    @override_settings(ENABLE_CLOUDFRONT_CACHE_PURGE=True)
    def test_document_saved_cache_purge_without_file(self):
        cloudfront_cache_invalidation(None, self.document_without_file)
        self.assertEqual(MOCK_PURGED, [])

    @override_settings(ENABLE_CLOUDFRONT_CACHE_PURGE=True)
    def test_document_saved_cache_invalidation(self):
        cloudfront_cache_invalidation(None, self.document)
        self.assertIn(self.document.file.url, MOCK_PURGED)
