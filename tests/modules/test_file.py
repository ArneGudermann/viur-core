import base64
import datetime
import time
from unittest import mock

from abstract import ViURTestCase


class TestFileDownloadUrl(ViURTestCase):

    def setUp(self):
        super().setUp()
        from viur.core import conf
        conf.file_hmac_key = b"test-hmac-key-for-unit-tests"

    def _roundtrip(self, filename, *, derived=False, expires=None):
        """create_download_url → parse_download_url round-trip, returns parsed FilePath."""
        # Lazy import: viur.core.modules.file initializes a GCS client at module level.
        # Importing inside a test method ensures the AppEngine testbed is already active,
        # so google.auth.default() is mocked and storage.Client() won't fail.
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        url = File.create_download_url("testdlkey", filename, derived=derived, expires=expires)
        return File.parse_download_url(url)

    def test_plain_filename(self):
        result = self._roundtrip("document.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "document.pdf")
        self.assertEqual(result.dlkey, "testdlkey")
        self.assertFalse(result.is_derived)

    def test_unescape_short_form_entities(self):
        """Short-form entities &#40; &#41; &#61; must be unescaped in the filepath."""
        result = self._roundtrip("file&#40;1&#41;&#61;x.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "file(1)=x.pdf")

    def test_unescape_long_form_entities(self):
        """Long-form entities &#040; &#041; &#061; must be unescaped in the filepath."""
        result = self._roundtrip("file&#040;1&#041;&#061;x.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "file(1)=x.pdf")

    def test_unescape_other_html_entities(self):
        """html.unescape() also handles &lt; &gt; — consistent with the rename code in the same module."""
        result = self._roundtrip("&lt;test&gt;.pdf")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "<test>.pdf")

    def test_derived_flag(self):
        result = self._roundtrip("thumb.webp", derived=True)
        self.assertIsNotNone(result)
        self.assertTrue(result.is_derived)
        self.assertEqual(result.filename, "thumb.webp")

    def test_expiring_url(self):
        """A signature carrying a lifetime must parse while that lifetime lasts."""
        result = self._roundtrip("document.pdf", expires=datetime.timedelta(hours=1))
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "document.pdf")

    def test_expired_url(self):
        """A signature whose lifetime has passed must not parse."""
        self.assertIsNone(self._roundtrip("document.pdf", expires=datetime.timedelta(hours=-1)))

    def _create_url(self, filename, *, derived=False, expires=None, download_filename=None):
        """Create a download url without parsing it back."""
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        return File.create_download_url(
            "testdlkey", filename, derived=derived, expires=expires,
            download_filename=download_filename)

    def test_absolute_url(self):
        """Admin frontends store the url including scheme and host; it must still parse."""
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        url = self._create_url("document.pdf")
        result = File.parse_download_url(f"https://example.com{url}")
        self.assertIsNotNone(result)
        self.assertEqual(result.dlkey, "testdlkey")
        self.assertEqual(result.filename, "document.pdf")

    def test_trailing_slash_before_query(self):
        """A slash between payload and query string must not break the signature check."""
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        data, _, query = self._create_url("document.pdf").removeprefix(
            File.DOWNLOAD_URL_PREFIX).partition("?")
        result = File.parse_download_url(f"{File.DOWNLOAD_URL_PREFIX}{data}/?{query}")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "document.pdf")

    def test_url_with_download_filename_path_segment(self):
        """`download` accepts the file name as a path segment, so parsing must ignore it."""
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        data, _, query = self._create_url(
            "document.pdf", download_filename="nice-name.pdf").removeprefix(
            File.DOWNLOAD_URL_PREFIX).partition("?")
        result = File.parse_download_url(
            f"{File.DOWNLOAD_URL_PREFIX}{data}/nice-name.pdf?{query}")
        self.assertIsNotNone(result)
        self.assertEqual(result.dlkey, "testdlkey")
        self.assertEqual(result.filename, "document.pdf")

    def test_query_with_additional_parameters(self):
        """Other query parameters next to `sig` must not confuse the parser."""
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        url = self._create_url("document.pdf")
        result = File.parse_download_url(f"{url}&download=1")
        self.assertIsNotNone(result)
        self.assertEqual(result.filename, "document.pdf")

    def test_url_without_query_is_rejected(self):
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        url = self._create_url("document.pdf").split("?", 1)[0]
        self.assertIsNone(File.parse_download_url(url))


class FakeFileSkel(dict):
    """Minimal stand-in for the skeleton returned by ``File.addSkel("leaf")``."""

    def write(self):
        self["key"] = "written-key"
        return self


class TestFileWriteWeakFlag(ViURTestCase):
    """``File.write`` marks a file weak exactly when it ends up without a repository."""

    def _write(self, **kwargs):
        """Run File.write against faked storage and skeletons, return the leaf skeleton."""
        from unittest import mock as _mock
        with _mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File

        blob = mock.Mock(size=4, crc32c=base64.b64encode(b"1234").decode(), md5_hash=base64.b64encode(b"5678").decode())
        bucket = mock.Mock()
        bucket.blob.return_value = blob

        leaf_skel = FakeFileSkel()

        module = mock.Mock()
        module.is_valid_filename = File.is_valid_filename
        module.get_bucket.return_value = bucket
        module.addSkel.side_effect = lambda kind: leaf_skel if kind == "leaf" else mock.Mock()

        File.write(module, "test.txt", b"data", **kwargs)
        return leaf_skel

    def test_file_without_repository_is_weak(self):
        """Documented: "If both are not set, the file is added [...] as a weak file"."""
        skel = self._write()
        self.assertIsNone(skel["parentrepo"])
        self.assertTrue(skel["weak"])

    def test_file_in_a_folder_is_not_weak(self):
        """A file inside a repository must keep its blob lock, so it must not be weak."""
        from unittest import mock as _mock
        with _mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File

        blob = mock.Mock(size=4, crc32c=base64.b64encode(b"1234").decode(), md5_hash=base64.b64encode(b"5678").decode())
        bucket = mock.Mock()
        bucket.blob.return_value = blob

        leaf_skel = FakeFileSkel()
        node_skel = mock.Mock()
        node_skel.all.return_value.getSkel.return_value = {"key": "folder-key"}

        module = mock.Mock()
        module.is_valid_filename = File.is_valid_filename
        module.get_bucket.return_value = bucket
        module.addSkel.side_effect = lambda kind: leaf_skel if kind == "leaf" else node_skel
        module.ensureOwnModuleRootNode.return_value = mock.Mock(key="repo-key")

        File.write(module, "test.txt", b"data", folder="documents")

        self.assertEqual("repo-key", leaf_skel["parentrepo"])
        self.assertFalse(leaf_skel["weak"])


class TestCreateSrcSetLanguageWrapper(ViURTestCase):
    """create_src_set has to unwrap a LanguageWrapper, i.e. a FileBone with languages set."""

    def _file(self):
        return {
            "dlkey": "testdlkey",
            "derived": {
                "files": {
                    "thumb.webp": {"customData": {"width": 100, "height": 50}},
                },
            },
        }

    def _wrapper(self, **values):
        from viur.core import i18n
        wrapper = i18n.LanguageWrapper(["de", "en"])
        wrapper.update(values)
        return wrapper

    def setUp(self):
        super().setUp()
        from viur.core import conf
        conf.file_hmac_key = b"test-hmac-key-for-unit-tests"

    def _create_src_set(self, file, **kwargs):
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        return File.create_src_set(file, width=[100], **kwargs)

    def test_explicit_language_is_used(self):
        wrapper = self._wrapper(de=self._file())
        result = self._create_src_set(wrapper, language="de")
        self.assertIn("100w", result)

    def test_missing_language_yields_empty_string(self):
        wrapper = self._wrapper(de=self._file())
        self.assertEqual("", self._create_src_set(wrapper, language="en"))

    def test_current_language_is_used_when_none_given(self):
        from viur.core import current
        wrapper = self._wrapper(de=self._file())
        current.language.set("de")
        try:
            result = self._create_src_set(wrapper)
        finally:
            current.language.set(None)
        self.assertIn("100w", result)

    def test_without_any_language_yields_empty_string(self):
        wrapper = self._wrapper(de=self._file())
        self.assertEqual("", self._create_src_set(wrapper))


class FakeBlobLockQuery:
    """Stands in for db.Query inside doCheckForUnreferencedBlobs."""

    def __init__(self, kind, state):
        self.kind = kind
        self.state = state
        self.filters = []

    def filter(self, *args):
        self.filters.append(args)
        return self

    def setCursor(self, cursor):
        return self

    def run(self, limit):
        return self.state["locks"]

    def getEntry(self):
        prop, value = self.filters[0]
        if prop == "active_blob_references =":
            return None  # nothing references these blobs any more
        if prop == "dlkey":
            return object() if value in self.state["already_marked"] else None
        raise AssertionError(f"unexpected filter {prop!r}")

    def getCursor(self):
        return None


class TestCheckForUnreferencedBlobs(ViURTestCase):
    """A blob that is already marked must not stop the cleanup of the remaining blobs."""

    def _run(self, blob_keys, already_marked):
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules import file as file_module

        state = {"locks": [mock.Mock(key="lock-1")], "already_marked": already_marked}
        written = []

        with mock.patch.object(file_module.db, "Query", lambda kind: FakeBlobLockQuery(kind, state)), \
                mock.patch.object(file_module.db, "run_in_transaction", lambda fn, key: blob_keys), \
                mock.patch.object(file_module.db, "Key", lambda *a, **kw: mock.Mock()), \
                mock.patch.object(file_module.db, "Entity", lambda key: {}), \
                mock.patch.object(file_module.db, "put", lambda obj: written.append(obj["dlkey"])):
            file_module.doCheckForUnreferencedBlobs.__wrapped__()

        return written

    def test_marks_all_unreferenced_blobs(self):
        self.assertEqual(["blob-a", "blob-b"], self._run(["blob-a", "blob-b"], already_marked=()))

    def test_already_marked_blob_does_not_stop_the_run(self):
        """The first blob is already scheduled; the second one still has to be picked up."""
        self.assertEqual(["blob-b"], self._run(["blob-a", "blob-b"], already_marked=("blob-a",)))

    def test_all_blobs_already_marked(self):
        self.assertEqual([], self._run(["blob-a", "blob-b"], already_marked=("blob-a", "blob-b")))


class FakeLeafSkel(dict):
    """Minimal leaf skeleton: dict access plus a read()/write() like SkeletonInstance."""

    def read(self, key):
        self["_read_key"] = key
        return True

    def write(self, **kwargs):
        self["_written"] = True
        return self

    def patch(self, values, **kwargs):
        """Like Skeleton.patch(): re-read, apply the callable, write."""
        self["_patched"] = True
        self.read(self["key"])
        values(self)
        return self.write()


class TestFileOverwriteUpload(ViURTestCase):
    """getUploadURL(amend=...) + add() overwrite an existing file's blob in place."""

    def _file(self):
        # Lazy import: the module creates a GCS client at import time.
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import File
        return File

    def test_amend_targets_existing_blob_and_keeps_key(self):
        """A resumable session is opened on the EXISTING dlkey/name; the existing key is returned."""
        File = self._file()
        blob = mock.Mock()
        blob.create_resumable_upload_session.return_value = "https://upload/session"
        bucket = mock.Mock()
        bucket.blob.return_value = blob

        skel = FakeLeafSkel(key="file-123", dlkey="abc_pub", name="image.jpg")
        module = mock.Mock()
        module.editSkel.return_value = skel
        module.canEdit.return_value = True
        module.get_bucket.return_value = bucket
        module.render.view.side_effect = lambda payload: payload

        result = File.getUploadURL._func(
            module, "ignored.jpg", "image/jpeg", amend="file-123")

        # Same blob, no new dlkey minted:
        bucket.blob.assert_called_once_with("abc_pub/source/image.jpg")
        blob.create_resumable_upload_session.assert_called_once()
        self.assertEqual(result["uploadKey"], "file-123")
        self.assertEqual(result["uploadUrl"], "https://upload/session")
        module.canEdit.assert_called_once_with("leaf", skel)

    def test_amend_unescapes_name_for_blob_path(self):
        """The stored (escaped) name must be unescaped to hit the real object path."""
        File = self._file()
        blob = mock.Mock()
        blob.create_resumable_upload_session.return_value = "u"
        bucket = mock.Mock()
        bucket.blob.return_value = blob
        skel = FakeLeafSkel(key="k", dlkey="d", name="file&#40;1&#41;.jpg")
        module = mock.Mock()
        module.editSkel.return_value = skel
        module.canEdit.return_value = True
        module.get_bucket.return_value = bucket
        module.render.view.side_effect = lambda payload: payload

        File.getUploadURL._func(module, "x", "image/jpeg", amend="k")
        bucket.blob.assert_called_once_with("d/source/file(1).jpg")

    def test_amend_forbidden_without_edit_rights(self):
        File = self._file()
        from viur.core import errors
        skel = FakeLeafSkel(key="k", dlkey="d", name="x.jpg")
        module = mock.Mock()
        module.editSkel.return_value = skel
        module.canEdit.return_value = False
        with self.assertRaises(errors.Forbidden):
            File.getUploadURL._func(module, "x.jpg", "image/jpeg", amend="k")

    def test_add_overwrite_refreshes_metadata_and_keeps_tree_position(self):
        """add() on a non-pending leaf refreshes size/mimetype/checksums; parent/weak stay."""
        File = self._file()
        blob = mock.Mock(
            size=4242, content_type="image/jpeg",
            crc32c=base64.b64encode(b"1234").decode(),
            md5_hash=base64.b64encode(b"5678").decode())
        bucket = mock.Mock()
        bucket.list_blobs.return_value = [blob]

        skel = FakeLeafSkel(
            key="file-123", dlkey="abc_pub", name="x.jpg",
            pending=False, size=0, mimetype="application/octetstream",
            parententry="folder-1", weak=False)
        module = mock.Mock()
        module.addSkel.return_value = skel
        module.canEdit.return_value = True
        module.get_bucket.return_value = bucket
        module.create_download_url.return_value = "/dl"
        module.render.editSuccess.side_effect = lambda s: s

        File.add._func(module, "leaf", key="file-123")

        self.assertEqual(skel["size"], 4242)
        self.assertEqual(skel["mimetype"], "image/jpeg")
        self.assertEqual(skel["crc32c_checksum"], b"1234".hex())
        self.assertTrue(skel.get("_written"))
        self.assertTrue(skel.get("_patched"), "amending must write via skel.patch(), i.e. transactional")
        # Tree position must NOT change on an overwrite:
        self.assertEqual(skel["parententry"], "folder-1")
        self.assertFalse(skel["weak"])
        module.onEdit.assert_called_once_with("leaf", skel)
        module.onEdited.assert_called_once_with("leaf", skel)

    def test_add_overwrite_forbidden_without_edit_rights(self):
        File = self._file()
        from viur.core import errors
        skel = FakeLeafSkel(key="k", dlkey="d", name="x.jpg", pending=False)
        module = mock.Mock()
        module.addSkel.return_value = skel
        module.canEdit.return_value = False
        with self.assertRaises(errors.Forbidden):
            File.add._func(module, "leaf", key="k")


class TestDownloadUrlExpiryRounding(ViURTestCase):
    """The expiry of download urls is rounded up, so the url stays stable and browsers can cache it."""

    def setUp(self):
        super().setUp()
        from viur.core import conf
        conf.file_hmac_key = b"test-hmac-key-for-unit-tests"
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules import file as file_module
        self.file_module = file_module

    def _expiry_at(self, now, expires):
        """Create a download url at ``now`` and return the expiry encoded into it."""
        real_datetime = datetime.datetime

        class FrozenDatetime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        with mock.patch.object(self.file_module.datetime, "datetime", FrozenDatetime):
            url = self.file_module.File.create_download_url("testdlkey", "document.pdf", expires=expires)

        blob_key = url.removeprefix(self.file_module.File.DOWNLOAD_URL_PREFIX).split("?", 1)[0]
        return base64.urlsafe_b64decode(blob_key).decode("UTF-8").split("\0")[1]

    def test_expiry_is_rounded_up_to_the_step(self):
        self.assertEqual(
            "202611061215",
            self._expiry_at(datetime.datetime(2026, 11, 6, 11, 3, 20), datetime.timedelta(hours=1)),
        )

    def test_url_is_stable_within_a_step(self):
        first = self._expiry_at(datetime.datetime(2026, 11, 6, 11, 0, 1), datetime.timedelta(hours=1))
        second = self._expiry_at(datetime.datetime(2026, 11, 6, 11, 14, 59), datetime.timedelta(hours=1))
        self.assertEqual(first, second)

    def test_expiry_on_a_step_boundary_is_kept(self):
        self.assertEqual(
            "202611061230",
            self._expiry_at(datetime.datetime(2026, 11, 6, 11, 30), datetime.timedelta(hours=1)),
        )

    def test_rounding_crosses_midnight(self):
        self.assertEqual(
            "202611070000",
            self._expiry_at(datetime.datetime(2026, 11, 6, 22, 50), datetime.timedelta(hours=1)),
        )

    def test_short_lifetime_is_not_rounded(self):
        self.assertEqual(
            "202611061108",
            self._expiry_at(datetime.datetime(2026, 11, 6, 11, 3, 20), datetime.timedelta(minutes=5)),
        )

    def test_unlimited_url(self):
        self.assertEqual("0", self._expiry_at(datetime.datetime(2026, 11, 6, 11, 3), None))


class TestSignedUrlCache(ViURTestCase):

    def setUp(self):
        super().setUp()
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules.file import _SignedUrlCache
        self.cache = _SignedUrlCache(max_entries=2)

    def test_hit(self):
        self.cache.set(("a",), "url-a", time.time() + 600)
        self.assertEqual("url-a", self.cache.get(("a",), min_remaining=300)[0])

    def test_miss(self):
        self.assertIsNone(self.cache.get(("a",), min_remaining=300))

    def test_entry_with_too_little_lifetime_left_is_dropped(self):
        self.cache.set(("a",), "url-a", time.time() + 200)
        self.assertIsNone(self.cache.get(("a",), min_remaining=300))
        self.assertIsNone(self.cache.get(("a",), min_remaining=0))

    def test_least_recently_used_entry_is_evicted(self):
        expires_at = time.time() + 600
        self.cache.set(("a",), "url-a", expires_at)
        self.cache.set(("b",), "url-b", expires_at)
        self.cache.get(("a",), min_remaining=0)
        self.cache.set(("c",), "url-c", expires_at)
        self.assertIsNotNone(self.cache.get(("a",), min_remaining=0))
        self.assertIsNone(self.cache.get(("b",), min_remaining=0))
        self.assertIsNotNone(self.cache.get(("c",), min_remaining=0))


class TestDownloadSignedUrlCaching(ViURTestCase):
    """:meth:`File.download` must not sign a new url (IAM call) and look up the blob (GCS call) on every request."""

    def setUp(self):
        super().setUp()
        from viur.core import conf, current
        conf.file_hmac_key = b"test-hmac-key-for-unit-tests"

        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules import file as file_module
        self.file_module = file_module
        File = file_module.File

        file_module._signed_url_cache.clear()
        self.addCleanup(file_module._signed_url_cache.clear)

        self.blob = mock.Mock()
        self.blob.generate_signed_url.return_value = "https://gcs/signed"
        self.bucket = mock.Mock()
        self.bucket.name = "bucket"
        self.bucket.get_blob.return_value = self.blob

        module = mock.Mock()
        module.get_bucket.return_value = self.bucket
        module.hmac_verify = File.hmac_verify
        module.is_valid_filename = File.is_valid_filename
        module.SIGNED_URL_LIFETIME = File.SIGNED_URL_LIFETIME
        module._redirect_to_signed_url = File._redirect_to_signed_url
        module._sign_blob_url = lambda *args, **kwargs: File._sign_blob_url(module, *args, **kwargs)
        self.module = module

        self.signing_credentials = mock.Mock()
        for patcher in (
            mock.patch.object(type(conf.instance), "is_dev_server", False),
            mock.patch.object(file_module, "_get_signing_credentials", return_value=self.signing_credentials),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.request = mock.MagicMock()
        self.request.response.headers = {}
        token = current.request.set(self.request)
        self.addCleanup(current.request.reset, token)

    def _download(self, url, **kwargs):
        from viur.core import errors
        path, query = url.removeprefix(self.file_module.File.DOWNLOAD_URL_PREFIX).split("?sig=")
        self.request.response.headers = {}
        with self.assertRaises(errors.Redirect) as ctx:
            self.file_module.File.download._func(self.module, path, sig=query, **kwargs)
        return ctx.exception

    def test_signed_url_is_reused(self):
        url = self.file_module.File.create_download_url("dlkey", "image.jpg")

        first = self._download(url)
        second = self._download(url)

        self.assertEqual("https://gcs/signed", first.url)
        self.assertEqual(first.url, second.url)
        self.blob.generate_signed_url.assert_called_once()
        self.bucket.get_blob.assert_called_once_with("dlkey/source/image.jpg")
        self.assertIs(self.signing_credentials, self.blob.generate_signed_url.call_args.kwargs["credentials"])

    def test_signed_url_is_cached_per_content_disposition(self):
        url = self.file_module.File.create_download_url("dlkey", "image.jpg")

        self._download(url)
        self._download(url, download=True)

        self.assertEqual(2, self.blob.generate_signed_url.call_count)

    def test_redirect_is_cacheable_by_the_browser(self):
        url = self.file_module.File.create_download_url("dlkey", "image.jpg")

        self._download(url)

        cache_control = self.request.response.headers["Cache-Control"]
        self.assertTrue(cache_control.startswith("private, max-age="))
        max_age = int(cache_control.rsplit("=", 1)[1])
        self.assertLessEqual(max_age, self.file_module.File.SIGNED_URL_LIFETIME.total_seconds() - 60)
        self.assertGreater(max_age, 0)

    def test_browser_cache_does_not_outlive_the_download_url(self):
        url = self.file_module.File.create_download_url("dlkey", "image.jpg", expires=datetime.timedelta(minutes=2))

        self._download(url)

        max_age = int(self.request.response.headers["Cache-Control"].rsplit("=", 1)[1])
        self.assertLessEqual(max_age, 120)

    def test_expired_url_is_gone_without_touching_gcs(self):
        from viur.core import errors
        url = self.file_module.File.create_download_url("dlkey", "image.jpg", expires=datetime.timedelta(hours=-1))
        path, sig = url.removeprefix(self.file_module.File.DOWNLOAD_URL_PREFIX).split("?sig=")

        with self.assertRaises(errors.Gone):
            self.file_module.File.download._func(self.module, path, sig=sig)

        self.bucket.get_blob.assert_not_called()

    def test_missing_blob_is_gone(self):
        from viur.core import errors
        self.bucket.get_blob.return_value = None
        url = self.file_module.File.create_download_url("dlkey", "image.jpg")
        path, sig = url.removeprefix(self.file_module.File.DOWNLOAD_URL_PREFIX).split("?sig=")

        with self.assertRaises(errors.Gone):
            self.file_module.File.download._func(self.module, path, sig=sig)


class TestSigningCredentials(ViURTestCase):

    def test_signing_credentials_are_created_once(self):
        with mock.patch("google.cloud.storage.Client"):
            from viur.core.modules import file as file_module

        with mock.patch.object(file_module, "_signing_credentials", None), \
                mock.patch("google.auth.compute_engine.IDTokenCredentials") as id_token_credentials, \
                mock.patch("google.auth.transport.requests.Request"):
            first = file_module._get_signing_credentials()
            second = file_module._get_signing_credentials()

        self.assertIs(first, second)
        id_token_credentials.assert_called_once()
