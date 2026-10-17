import hashlib
import os
import urllib.parse
import xml.etree.ElementTree as ET

import pytest

from app.classes.helpers import offsite

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_DATE = "20130524T000000Z"
AWS_HOST = "examplebucket.s3.amazonaws.com"


def _aws_request(method, path, query=None, payload_hash=offsite.EMPTY_HASH, **extra):
    headers = {
        "host": AWS_HOST,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": AWS_DATE,
        **extra,
    }
    return {
        "method": method,
        "path": path,
        "query": query or {},
        "headers": headers,
        "payload_hash": payload_hash,
        "amz_date": AWS_DATE,
    }


# Amazon's own examples of signed S3 requests
@pytest.mark.parametrize(
    "request_data, signed, signature",
    [
        (
            _aws_request("GET", "/test.txt", range="bytes=0-9"),
            "host;range;x-amz-content-sha256;x-amz-date",
            "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41",
        ),
        (
            _aws_request(
                "PUT",
                "/test%24file.text",
                payload_hash=hashlib.sha256(b"Welcome to Amazon S3.").hexdigest(),
                date="Fri, 24 May 2013 00:00:00 GMT",
                **{"x-amz-storage-class": "REDUCED_REDUNDANCY"},
            ),
            "date;host;x-amz-content-sha256;x-amz-date;x-amz-storage-class",
            "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd",
        ),
        (
            _aws_request("GET", "/", {"lifecycle": ""}),
            "host;x-amz-content-sha256;x-amz-date",
            "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543",
        ),
        (
            _aws_request("GET", "/", {"max-keys": "2", "prefix": "J"}),
            "host;x-amz-content-sha256;x-amz-date",
            "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7",
        ),
    ],
)
def test_sign_v4_matches_amazons_examples(request_data, signed, signature) -> None:
    assert offsite.sign_v4(request_data, AWS_KEY, AWS_SECRET, "us-east-1") == (
        f"AWS4-HMAC-SHA256 Credential={AWS_KEY}/20130524/us-east-1/s3/aws4_request,"
        f"SignedHeaders={signed},Signature={signature}"
    )


def test_copy_names() -> None:
    name = offsite.copy_name("My <World> 1.21!", "2026-10-17_09-42-54.zip")
    assert name == "My-World-1.21_2026-10-17_09-42-54.zip"
    assert offsite.copy_name("§§§", "a.zip") == "server_a.zip"
    assert offsite.local_name(name) == "2026-10-17_09-42-54.zip"
    assert offsite.local_name("other.zip") == "other.zip"
    assert offsite.has_copy([{"name": name}], "2026-10-17_09-42-54.zip")
    assert not offsite.has_copy([{"name": name}], "2026-10-17_09-42-55.zip")


@pytest.mark.parametrize(
    "name", ["../x.zip", "a/b.zip", ".marker.zip", "x.txt", "", None, 3]
)
def test_fetch_name_refuses_paths(name) -> None:
    with pytest.raises(offsite.OffsiteError):
        offsite.fetch_name(name)


@pytest.mark.parametrize(
    "host, region",
    [
        ("abc.r2.cloudflarestorage.com", "auto"),
        ("s3.eu-west-2.amazonaws.com", "eu-west-2"),
        ("s3.eu-central-003.backblazeb2.com", "eu-central-003"),
        ("s3.ap-northeast-1.wasabisys.com", "ap-northeast-1"),
        ("fsn1.your-objectstorage.com", "fsn1"),
        ("minio.home.lan", "us-east-1"),
    ],
)
def test_guess_region(host, region) -> None:
    assert offsite.guess_region(host) == region


def test_clean_settings() -> None:
    folder = offsite.clean_settings("folder", {"path": " /mnt/usb/../usb2/ "})
    assert folder == {"path": os.path.normpath("/mnt/usb2")}
    with pytest.raises(offsite.OffsiteError):
        offsite.clean_settings("folder", {"path": "relative/folder"})

    s3 = {
        "endpoint": "s3.eu-west-2.amazonaws.com/",
        "bucket": "my-bucket",
        "prefix": "/crafty/",
        "access_key": "AK",
        "secret_key": "SK",
    }
    cleaned = offsite.clean_settings("s3", s3)
    assert cleaned["endpoint"] == "https://s3.eu-west-2.amazonaws.com"
    assert cleaned["prefix"] == "crafty"
    assert cleaned["secret_key"] == "SK"
    # An empty secret key keeps the saved one
    kept = offsite.clean_settings("s3", {**s3, "secret_key": ""}, cleaned)
    assert kept["secret_key"] == "SK"
    for bad in (
        {"endpoint": "https://host/path"},
        {"bucket": "a/b"},
        {"prefix": "../up"},
        {"secret_key": ""},
        {"access_key": ""},
    ):
        with pytest.raises(offsite.OffsiteError):
            offsite.clean_settings("s3", {**s3, **bad})

    shown = offsite.public_settings("s3", cleaned)
    assert "secret_key" not in shown and shown["has_secret"] is True
    assert (
        offsite.describe("s3", cleaned)
        == "my-bucket/crafty on s3.eu-west-2.amazonaws.com"
    )


def _backup(folder, name, data, when):
    path = folder / name
    path.write_bytes(data)
    os.utime(path, (when, when))
    return path


def test_folder_target(tmp_path) -> None:
    disk = tmp_path / "disk"
    disk.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()
    place = offsite.FolderTarget({"path": str(disk)})
    # Not tested yet: it may be the empty mount point of a missing disk
    with pytest.raises(offsite.OffsiteError) as caught:
        place.list("b1")
    assert caught.value.code == "NOT_CONNECTED"

    warnings = place.test(str(backups))
    assert (disk / offsite.MARKER).is_file()
    assert len(warnings) == 1 and "same disk" in warnings[0]
    assert sorted(os.listdir(disk)) == [offsite.MARKER]

    progress = []
    for number in range(3):
        source = _backup(
            backups,
            f"2026-10-1{number}_00-00-00.zip",
            b"x" * (number + 1),
            1000 + number,
        )
        place.put(
            source,
            "b1",
            offsite.copy_name("S", source.name),
            lambda done, total: progress.append((done, total)),
        )
    assert progress[-1] == (3, 3)
    copies = place.list("b1")
    assert [copy["name"] for copy in copies] == [
        "S_2026-10-10_00-00-00.zip",
        "S_2026-10-11_00-00-00.zip",
        "S_2026-10-12_00-00-00.zip",
    ]
    assert [copy["time"] for copy in copies] == [1000, 1001, 1002]

    assert not offsite.keep_newest(place, "b1", 0)
    assert offsite.keep_newest(place, "b1", 2) == ["S_2026-10-10_00-00-00.zip"]
    assert len(place.list("b1")) == 2

    dest = tmp_path / "back.zip"
    place.get("b1", "S_2026-10-12_00-00-00.zip", dest)
    assert dest.read_bytes() == b"xxx"

    (disk / offsite.MARKER).unlink()
    with pytest.raises(offsite.OffsiteError):
        place.put(dest, "b1", "S_again.zip")


class FakeResponse:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.reason = "OK" if status < 300 else "Error"

    def iter_content(self, size):
        for start in range(0, len(self.content), size):
            yield self.content[start : start + size]

    def close(self):
        pass


class FakeS3:
    """Just enough of an S3 bucket, path style, to copy to"""

    def __init__(self):
        self.objects = {}
        self.uploads = {}
        self.calls = []
        # (method, query key) -> how many more times to fail with 500
        self.fail = {}
        self.complete_error = False

    def request(self, method, url, data=None, headers=None, **_kwargs):
        assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=AK/")
        if data:
            assert headers["x-amz-content-sha256"] == hashlib.sha256(data).hexdigest()
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        bucket, _, key = parts.path.lstrip("/").partition("/")
        key = urllib.parse.unquote(key)
        assert bucket == "bucket"
        self.calls.append((method, key, sorted(query)))
        which = (method, "partNumber" if "partNumber" in query else "")
        if self.fail.get(which):
            self.fail[which] -= 1
            return FakeResponse(500, b"<Error><Code>InternalError</Code></Error>")
        if method == "POST" and "uploads" in query:
            self.uploads["u1"] = {}
            return FakeResponse(
                content=b"<InitiateMultipartUploadResult "
                b'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<UploadId>u1</UploadId></InitiateMultipartUploadResult>"
            )
        if method == "PUT" and "partNumber" in query:
            self.uploads[query["uploadId"]][int(query["partNumber"])] = data
            return FakeResponse(headers={"ETag": f'"{query["partNumber"]}"'})
        if method == "POST" and "uploadId" in query:
            if self.complete_error:
                return FakeResponse(
                    content=b"<Error><Code>InternalError</Code></Error>"
                )
            parts_sent = self.uploads.pop(query["uploadId"])
            numbers = [int(x.text) for x in ET.fromstring(data).iter("PartNumber")]
            assert numbers == sorted(parts_sent)
            self.objects[key] = b"".join(parts_sent[n] for n in numbers)
            return FakeResponse(content=b"<CompleteMultipartUploadResult/>")
        if method == "DELETE" and "uploadId" in query:
            self.uploads.pop(query["uploadId"], None)
            return FakeResponse(204)
        if method == "PUT":
            self.objects[key] = data or b""
            return FakeResponse()
        if method == "GET" and query.get("list-type") == "2":
            items = "".join(
                f"<Contents><Key>{name}</Key><Size>{len(body)}</Size>"
                f"<LastModified>2026-10-17T09:00:0{index}.000Z</LastModified>"
                "</Contents>"
                for index, (name, body) in enumerate(sorted(self.objects.items()))
                if name.startswith(query["prefix"])
            )
            return FakeResponse(
                content=(
                    '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                    f"{items}<IsTruncated>false</IsTruncated></ListBucketResult>"
                ).encode()
            )
        if method == "GET":
            if key not in self.objects:
                return FakeResponse(404, b"<Error><Code>NoSuchKey</Code></Error>")
            body = self.objects[key]
            return FakeResponse(
                content=body, headers={"Content-Length": str(len(body))}
            )
        if method == "DELETE":
            self.objects.pop(key, None)
            return FakeResponse(204)
        raise AssertionError(f"unexpected {method} {url}")


def _s3(fake, **settings):
    return offsite.S3Target(
        {
            "endpoint": "https://storage.example.com",
            "bucket": "bucket",
            "prefix": "my backups",
            "access_key": "AK",
            "secret_key": "SK",
            **settings,
        },
        session=fake,
    )


def test_s3_target_copies(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(offsite, "PART_SIZE", 1024)
    monkeypatch.setattr(offsite, "CHUNK", 1024)
    monkeypatch.setattr(offsite.time, "sleep", lambda _seconds: None)
    fake = FakeS3()
    place = _s3(fake)
    assert not place.test()
    assert not fake.objects

    small = tmp_path / "2026-10-17_09-00-00.zip"
    small.write_bytes(b"small")
    place.put(small, "b1", "S_" + small.name)
    assert fake.objects["my backups/b1/S_2026-10-17_09-00-00.zip"] == b"small"

    # Bigger than a part: sent in parts, and a part that fails once is sent again
    big = tmp_path / "2026-10-17_09-00-01.zip"
    big.write_bytes(os.urandom(2500))
    fake.fail[("PUT", "partNumber")] = 1
    progress = []
    place.put(big, "b1", "S_" + big.name, lambda done, total: progress.append(done))
    assert fake.objects["my backups/b1/S_2026-10-17_09-00-01.zip"] == big.read_bytes()
    assert progress == [1024, 2048, 2500]

    copies = place.list("b1")
    assert [copy["name"] for copy in copies] == [
        "S_2026-10-17_09-00-00.zip",
        "S_2026-10-17_09-00-01.zip",
    ]
    assert copies[1]["size"] == 2500

    dest = tmp_path / "back.zip"
    place.get("b1", "S_2026-10-17_09-00-01.zip", dest)
    assert dest.read_bytes() == big.read_bytes()

    assert offsite.keep_newest(place, "b1", 1) == ["S_2026-10-17_09-00-00.zip"]
    assert list(fake.objects) == ["my backups/b1/S_2026-10-17_09-00-01.zip"]


def test_s3_target_failures(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(offsite, "PART_SIZE", 1024)
    monkeypatch.setattr(offsite, "CHUNK", 1024)
    monkeypatch.setattr(offsite.time, "sleep", lambda _seconds: None)
    fake = FakeS3()
    place = _s3(fake)
    big = tmp_path / "big.zip"
    big.write_bytes(os.urandom(2500))

    # An error in a 200 answer to the last step cancels the upload
    fake.complete_error = True
    with pytest.raises(offsite.OffsiteError):
        place.put(big, "b1", "S_big.zip")
    assert not fake.uploads and not fake.objects
    assert fake.calls[-1][0] == "DELETE"

    # A part that keeps failing gives up after a few tries
    fake.complete_error = False
    fake.fail[("PUT", "partNumber")] = offsite.TRIES
    with pytest.raises(offsite.OffsiteError):
        place.put(big, "b1", "S_big.zip")
    assert not fake.uploads

    def broken(*_args, **_kwargs):
        return FakeResponse(
            403,
            b"<Error><Code>SignatureDoesNotMatch</Code><Message>No.</Message></Error>",
        )

    fake.request = broken
    with pytest.raises(offsite.OffsiteError) as caught:
        place.test()
    assert "The secret key is wrong" in str(caught.value)
    assert not caught.value.retry


def test_s3_addressing() -> None:
    fake = FakeS3()
    seen = []
    fake.request = lambda method, url, **kwargs: seen.append(url) or FakeResponse()
    _s3(fake, endpoint="https://s3.eu-west-2.amazonaws.com").delete("b1", "a b.zip")
    _s3(
        fake, endpoint="https://s3.eu-west-2.amazonaws.com", bucket="dotted.bucket"
    ).delete("b1", "a.zip")
    assert seen == [
        "https://bucket.s3.eu-west-2.amazonaws.com/my%20backups/b1/a%20b.zip",
        "https://s3.eu-west-2.amazonaws.com/dotted.bucket/my%20backups/b1/a.zip",
    ]
    assert len(_s3(FakeS3(), endpoint="http://127.0.0.1:7070").test()) == 1
