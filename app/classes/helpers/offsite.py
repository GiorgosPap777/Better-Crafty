"""Off-site copies of backups: a folder on another disk or a mounted network
share, or S3-compatible cloud storage (Amazon S3, Backblaze B2, Cloudflare R2,
Wasabi and others).

The copies of a backup live in "<root>/<backup id>/", the layout of Crafty's
own backup folder, so a folder of copies also works as a backup location.
"""

import datetime
import hashlib
import hmac
import logging
import math
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

KINDS = ("folder", "s3")
SUFFIX = ".zip"
# Written by a successful test. A folder without it may be the empty mount
# point of a disk that is not connected, and copying there would fill the
# main disk instead.
MARKER = ".better-crafty-offsite"
MARKER_TEXT = (
    "Better Crafty copies backups here. Keep this file: without it the panel\n"
    "thinks the disk is not connected and stops copying.\n"
)
PART_SIZE = 16 * 1024 * 1024
MAX_PARTS = 9000
CHUNK = 1024 * 1024
TIMEOUT = (15, 300)
TRIES = 3
EMPTY_HASH = hashlib.sha256(b"").hexdigest()
# Crafty names zip backups after the time they were made
LOCAL_NAME = re.compile(r"(\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.zip)$")
COPY_NAME = re.compile(r"^[^/\\\x00-\x1f]{1,200}\.zip$")
BUCKET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,62}$")
REGION = re.compile(r"^[a-z0-9-]{1,40}$")
PREFIX = re.compile(r"^[\w ./+=@-]{0,200}$")
REGION_HOSTS = (
    (re.compile(r"(^|\.)r2\.cloudflarestorage\.com$"), "auto"),
    (re.compile(r"^s3[.-](?:dualstack\.)?([a-z0-9-]+)\.amazonaws\.com$"), None),
    (re.compile(r"^s3\.([a-z0-9-]+)\.backblazeb2\.com$"), None),
    (re.compile(r"^s3\.([a-z0-9-]+)\.wasabisys\.com$"), None),
    (re.compile(r"^([a-z0-9]+)\.your-objectstorage\.com$"), None),
)
S3_HINTS = {
    "InvalidAccessKeyId": "The access key is wrong.",
    "SignatureDoesNotMatch": "The secret key is wrong.",
    "NoSuchBucket": "There is no bucket with that name.",
    "AccessDenied": "The key is not allowed to do this in that bucket.",
    "RequestTimeTooSkewed": "This computer's clock is wrong.",
    "AuthorizationHeaderMalformed": "The region is wrong.",
    "PermanentRedirect": "The bucket is in another region; check the address.",
}


class OffsiteError(Exception):
    """A copy that could not be made, with a short code for the API."""

    def __init__(self, code: str, message: str, retry: bool = False):
        super().__init__(message)
        self.code = code
        # Worth trying again: the connection broke or the storage was busy
        self.retry = retry


def copy_name(server_name: str, backup_name: str) -> str:
    """The copy's name: the server's name in front of the backup's, so the
    files say which server they are from in the cloud's own file list."""
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", server_name).strip("-.")[:40]
    return f"{slug or 'server'}_{backup_name}"


def local_name(name: str) -> str:
    """The backup a copy was made from (the copy's name without the server's)"""
    found = LOCAL_NAME.search(name)
    return found.group(1) if found else name


def has_copy(copies: list, name: str) -> bool:
    return any(local_name(copy["name"]) == name for copy in copies)


def guess_region(host: str) -> str:
    for pattern, region in REGION_HOSTS:
        found = pattern.search(host)
        if found:
            return region or found.group(1)
    return "us-east-1"


def clean_settings(kind: str, data: dict, old: dict | None = None) -> dict:
    """The settings to store for a place to copy to. A secret key left empty
    keeps the old one."""
    if not isinstance(data, dict):
        raise OffsiteError("INVALID_SETTINGS", "The settings must be an object")

    def text(key: str) -> str:
        value = data.get(key, "")
        if not isinstance(value, str):
            raise OffsiteError("INVALID_SETTINGS", f"{key} must be text")
        return value.strip()

    if kind == "folder":
        path = text("path")
        if not path or not os.path.isabs(path):
            raise OffsiteError(
                "INVALID_SETTINGS", "Give the folder's full path, like /mnt/backups"
            )
        return {"path": os.path.normpath(path)}
    if kind != "s3":
        raise OffsiteError("INVALID_SETTINGS", "The type must be folder or s3")

    endpoint = text("endpoint").rstrip("/")
    if endpoint and "://" not in endpoint:
        endpoint = "https://" + endpoint
    parts = urllib.parse.urlsplit(endpoint)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.path:
        raise OffsiteError(
            "INVALID_SETTINGS",
            "The address must be like https://s3.us-west-004.backblazeb2.com",
        )
    settings = {
        "endpoint": endpoint,
        "bucket": text("bucket"),
        "prefix": text("prefix").strip("/"),
        "region": text("region"),
        "access_key": text("access_key"),
        "secret_key": text("secret_key") or (old or {}).get("secret_key", ""),
    }
    if not BUCKET.match(settings["bucket"]):
        raise OffsiteError("INVALID_SETTINGS", "The bucket name is not valid")
    if not PREFIX.match(settings["prefix"]) or ".." in settings["prefix"].split("/"):
        raise OffsiteError("INVALID_SETTINGS", "The folder in the bucket is not valid")
    if settings["region"] and not REGION.match(settings["region"]):
        raise OffsiteError("INVALID_SETTINGS", "The region is not valid")
    if not settings["access_key"] or not settings["secret_key"]:
        raise OffsiteError("INVALID_SETTINGS", "Give the access key and secret key")
    return settings


def public_settings(kind: str, settings: dict) -> dict:
    """The settings without the secret key, for the browser"""
    shown = {key: value for key, value in settings.items() if key != "secret_key"}
    if kind == "s3":
        shown["has_secret"] = bool(settings.get("secret_key"))
    return shown


def describe(kind: str, settings: dict) -> str:
    """Where the copies go, in a few words"""
    if kind == "folder":
        return settings.get("path", "")
    host = urllib.parse.urlsplit(settings.get("endpoint", "")).hostname or ""
    where = "/".join(x for x in (settings.get("bucket"), settings.get("prefix")) if x)
    return f"{where} on {host}"


def target(kind: str, settings: dict):
    if kind == "folder":
        return FolderTarget(settings)
    return S3Target(settings)


def _copy_file(source, dest, total: int, progress=None) -> None:
    done = 0
    while True:
        block = source.read(CHUNK)
        if not block:
            return
        dest.write(block)
        done += len(block)
        if progress:
            progress(done, total)


class FolderTarget:
    """Copies in a folder: another disk, or a network share mounted here."""

    def __init__(self, settings: dict):
        self.root = Path(settings["path"])

    def _ready(self) -> None:
        if not self.root.is_dir():
            raise OffsiteError(
                "NOT_CONNECTED",
                f"The folder {self.root} is not there. Is the disk connected?",
            )
        if not (self.root / MARKER).is_file():
            raise OffsiteError(
                "NOT_CONNECTED",
                f"{self.root} is not the folder that was tested, so the disk "
                "may not be connected. Connect it, then press Test under "
                "Off-site storage.",
            )

    def _folder(self, folder: str) -> Path:
        return self.root / folder

    def put(self, source: Path, folder: str, name: str, progress=None) -> None:
        self._ready()
        target_dir = self._folder(folder)
        part = target_dir / (name + ".part")
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            total = source.stat().st_size
            with open(source, "rb") as src, open(part, "wb") as dst:
                _copy_file(src, dst, total, progress)
            try:
                # The copy keeps the backup's time
                stat = source.stat()
                os.utime(part, (stat.st_atime, stat.st_mtime))
            except OSError:
                pass
            os.replace(part, target_dir / name)
        except OSError as ex:
            part.unlink(missing_ok=True)
            raise OffsiteError("COPY_FAILED", str(ex)) from ex

    def list(self, folder: str) -> list:
        self._ready()
        copies = []
        try:
            entries = list(os.scandir(self._folder(folder)))
        except FileNotFoundError:
            return []
        except OSError as ex:
            raise OffsiteError("LIST_FAILED", str(ex)) from ex
        for entry in entries:
            if entry.name.endswith(SUFFIX) and entry.is_file():
                stat = entry.stat()
                copies.append(
                    {"name": entry.name, "size": stat.st_size, "time": stat.st_mtime}
                )
        return sorted(copies, key=lambda copy: (copy["time"], copy["name"]))

    def delete(self, folder: str, name: str) -> None:
        try:
            (self._folder(folder) / name).unlink(missing_ok=True)
        except OSError as ex:
            raise OffsiteError("DELETE_FAILED", str(ex)) from ex

    def get(self, folder: str, name: str, dest: Path, progress=None) -> None:
        self._ready()
        source = self._folder(folder) / name
        try:
            with open(source, "rb") as src, open(dest, "wb") as dst:
                _copy_file(src, dst, source.stat().st_size, progress)
            stat = source.stat()
            os.utime(dest, (stat.st_atime, stat.st_mtime))
        except OSError as ex:
            raise OffsiteError("FETCH_FAILED", str(ex)) from ex

    def test(self, backups_dir: str | None = None) -> list:
        """Write, read and delete a small file. Returns warnings."""
        if not self.root.is_dir():
            raise OffsiteError("NOT_FOUND", f"There is no folder {self.root}")
        probe = self.root / f"{MARKER}-test"
        try:
            (self.root / MARKER).write_text(MARKER_TEXT, encoding="utf-8")
            probe.write_bytes(b"test")
            if probe.read_bytes() != b"test":
                raise OffsiteError("TEST_FAILED", "The test file came back changed")
        except OSError as ex:
            raise OffsiteError("TEST_FAILED", f"Could not write there: {ex}") from ex
        finally:
            probe.unlink(missing_ok=True)
        warnings = []
        try:
            if backups_dir and os.stat(backups_dir).st_dev == self.root.stat().st_dev:
                warnings.append(
                    "This folder is on the same disk as the backups, so the "
                    "copies are lost if that disk breaks."
                )
        except OSError:
            pass
        return warnings


def sign_v4(request: dict, access_key: str, secret_key: str, region: str) -> str:
    """The Authorization header of an AWS Signature Version 4 request.

    request holds method, path (already encoded), query (a dict), headers
    (lower-case names; every one is signed), payload_hash and amz_date.
    """
    query = "&".join(
        f"{key}={value}"
        for key, value in sorted(
            (_quote(key, ""), _quote(value, ""))
            for key, value in request["query"].items()
        )
    )
    names = sorted(request["headers"])
    headers = "".join(
        f"{name}:{' '.join(str(request['headers'][name]).split())}\n" for name in names
    )
    signed = ";".join(names)
    canonical = "\n".join(
        [
            request["method"],
            request["path"],
            query,
            headers,
            signed,
            request["payload_hash"],
        ]
    )
    date = request["amz_date"][:8]
    scope = f"{date}/{region}/s3/aws4_request"
    to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            request["amz_date"],
            scope,
            hashlib.sha256(canonical.encode()).hexdigest(),
        ]
    )
    key = ("AWS4" + secret_key).encode()
    for part in (date, region, "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},"
        f"SignedHeaders={signed},Signature={signature}"
    )


def _quote(value: str, safe: str = "/") -> str:
    return urllib.parse.quote(str(value), safe=safe)


def _tag(element, name: str):
    """The first child called name, whatever its XML namespace"""
    for child in element:
        if child.tag == name or child.tag.endswith("}" + name):
            return child
    return None


def _text(element, name: str) -> str:
    child = _tag(element, name)
    return (child.text or "") if child is not None else ""


def _children(element, name: str) -> list:
    return [
        child
        for child in element
        if child.tag == name or child.tag.endswith("}" + name)
    ]


def _parse_time(value: str) -> float:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class S3Target:
    """Copies in a bucket of S3-compatible storage"""

    def __init__(self, settings: dict, session=None):
        parts = urllib.parse.urlsplit(settings["endpoint"])
        self.scheme = parts.scheme
        self.netloc = parts.netloc
        self.bucket = settings["bucket"]
        self.prefix = settings.get("prefix", "")
        self.access_key = settings["access_key"]
        self.secret_key = settings["secret_key"]
        self.region = settings.get("region") or guess_region(parts.hostname)
        # Amazon wants the bucket in the host name; the others take both
        self.virtual_host = parts.hostname.endswith(".amazonaws.com") and (
            "." not in self.bucket
        )
        self.session = session or requests.Session()

    def _key(self, folder: str, name: str = "") -> str:
        return "/".join(x for x in (self.prefix, folder, name) if x)

    def _request(self, method: str, key: str = "", query=None, body=b"", **kwargs):
        query = query or {}
        if self.virtual_host:
            host = f"{self.bucket}.{self.netloc}"
            path = "/" + _quote(key)
        else:
            host = self.netloc
            path = "/" + _quote(self.bucket) + ("/" + _quote(key) if key else "")
        payload_hash = hashlib.sha256(body).hexdigest() if body else EMPTY_HASH
        headers = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y%m%dT%H%M%SZ"
            ),
        }
        headers["authorization"] = sign_v4(
            {
                "method": method,
                "path": path,
                "query": query,
                "headers": headers,
                "payload_hash": payload_hash,
                "amz_date": headers["x-amz-date"],
            },
            self.access_key,
            self.secret_key,
            self.region,
        )
        url = f"{self.scheme}://{host}{path}"
        if query:
            url += "?" + "&".join(
                f"{_quote(name, '')}={_quote(value, '')}"
                for name, value in query.items()
            )
        try:
            response = self.session.request(
                method,
                url,
                data=body or None,
                headers=headers,
                timeout=TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as ex:
            raise OffsiteError(
                "CONNECTION_FAILED", f"Could not reach {self.netloc}: {ex}", True
            ) from ex
        if response.status_code >= 300:
            raise self._error(response)
        return response

    def _error(self, response) -> OffsiteError:
        code, message = f"HTTP {response.status_code}", response.reason or ""
        try:
            root = ET.fromstring(response.content)
            code = _text(root, "Code") or code
            message = _text(root, "Message") or message
        except ET.ParseError:
            pass
        hint = S3_HINTS.get(code)
        text = f"{code}: {message}" if message else code
        return OffsiteError(
            "STORAGE_ERROR",
            f"{hint} ({text})" if hint else text,
            response.status_code >= 500 or code in ("SlowDown", "RequestTimeout"),
        )

    def _retry(self, action):
        for attempt in range(TRIES):
            try:
                return action()
            except OffsiteError as ex:
                if attempt == TRIES - 1 or not ex.retry:
                    raise
                logger.warning(f"Off-site copy: trying again after: {ex}")
                time.sleep(2**attempt)
        return None

    def put(self, source: Path, folder: str, name: str, progress=None) -> None:
        key = self._key(folder, name)
        total = source.stat().st_size
        if total <= PART_SIZE:
            body = source.read_bytes()
            self._retry(lambda: self._request("PUT", key, body=body))
            if progress:
                progress(total, total)
            return
        part_size = max(PART_SIZE, math.ceil(total / MAX_PARTS / CHUNK) * CHUNK)
        started = self._request("POST", key, {"uploads": ""})
        upload_id = _text(ET.fromstring(started.content), "UploadId")
        if not upload_id:
            raise OffsiteError("STORAGE_ERROR", "The storage did not start the upload")
        try:
            tags = []
            with open(source, "rb") as src:
                done = 0
                while True:
                    body = src.read(part_size)
                    if not body:
                        break
                    query = {"partNumber": str(len(tags) + 1), "uploadId": upload_id}
                    response = self._retry(
                        lambda body=body, query=query: self._request(
                            "PUT", key, query, body=body
                        )
                    )
                    tags.append(response.headers.get("ETag", ""))
                    done += len(body)
                    if progress:
                        progress(done, total)
            listing = "".join(
                f"<Part><PartNumber>{number}</PartNumber><ETag>{tag}</ETag></Part>"
                for number, tag in enumerate(tags, 1)
            )
            body = (
                f"<CompleteMultipartUpload>{listing}</CompleteMultipartUpload>"
            ).encode()
            response = self._request("POST", key, {"uploadId": upload_id}, body=body)
            # The answer can be an error even with status 200
            if b"<Error>" in response.content[:200]:
                raise self._error(response)
        except BaseException:
            try:
                self._request("DELETE", key, {"uploadId": upload_id})
            except OffsiteError:
                logger.warning(f"Could not cancel the upload of {key}")
            raise

    def list(self, folder: str) -> list:
        prefix = self._key(folder) + "/"
        copies = []
        token = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if token:
                query["continuation-token"] = token
            root = ET.fromstring(self._request("GET", "", query).content)
            for item in _children(root, "Contents"):
                name = _text(item, "Key")[len(prefix) :]
                if name.endswith(SUFFIX) and "/" not in name:
                    copies.append(
                        {
                            "name": name,
                            "size": int(_text(item, "Size") or 0),
                            "time": _parse_time(_text(item, "LastModified")),
                        }
                    )
            token = _text(root, "NextContinuationToken")
            if _text(root, "IsTruncated") != "true" or not token:
                break
        return sorted(copies, key=lambda copy: (copy["time"], copy["name"]))

    def delete(self, folder: str, name: str) -> None:
        self._request("DELETE", self._key(folder, name))

    def get(self, folder: str, name: str, dest: Path, progress=None) -> None:
        response = self._request("GET", self._key(folder, name), stream=True)
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        try:
            with open(dest, "wb") as dst:
                for block in response.iter_content(CHUNK):
                    dst.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
        except (OSError, requests.RequestException) as ex:
            raise OffsiteError("FETCH_FAILED", str(ex)) from ex
        finally:
            response.close()

    def test(self, backups_dir: str | None = None) -> list:
        """Write, list and delete a small file. Returns warnings."""
        del backups_dir
        key = self._key("", f"{MARKER}-test")
        self._request("PUT", key, body=b"test")
        try:
            self._request("GET", "", {"list-type": "2", "prefix": key})
        finally:
            self._request("DELETE", key)
        if self.scheme == "http":
            return [
                "The address starts with http://, so the backups travel"
                " unencrypted. Use https:// unless the storage is on your own"
                " network."
            ]
        return []


def keep_newest(target_place, folder: str, keep: int) -> list:
    """Delete the oldest copies so that keep are left (0 keeps them all).
    Returns the names deleted."""
    if keep <= 0:
        return []
    copies = target_place.list(folder)
    removed = []
    for copy in copies[: max(0, len(copies) - keep)]:
        target_place.delete(folder, copy["name"])
        removed.append(copy["name"])
    return removed


def fetch_name(name: str) -> str:
    """Check a copy's name from the browser"""
    if not isinstance(name, str) or not COPY_NAME.match(name) or name.startswith("."):
        raise OffsiteError("INVALID_NAME", "That is not the name of a copy")
    return name
