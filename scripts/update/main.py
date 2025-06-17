from minecraft.api_requests import MinecraftRequests, DownloadType, MinecraftDownloadType
from configs import BEDROCK_DIR, DEDICATED_METADATA, TORCHCS_VERSIONS_JSON_FILE, TORCHCS_META_FILE
from logger import log
import time
import hashlib
import requests
import json
from copy import deepcopy
import os
from pathlib import Path

def patch_torchcs_data(version: str, app: str):
    if app not in ("release", "preview"):
        log.warning(f"Invalid app type: {app}")
        return

    with open(TORCHCS_VERSIONS_JSON_FILE, "r", encoding="utf-8") as f:
        versions = json.load(f)

    with open(TORCHCS_META_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if version not in versions[app]:
        versions[app].insert(0, version)
        with open(TORCHCS_VERSIONS_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(versions, f, indent=2)
        log.info(f"Added new version to versions.json: {app} {version}")
    else:
        log.info(f"Version already exists in versions.json: {app} {version}")

    metadata["latest"]["binary"]["version"][app] = version
    with open(TORCHCS_META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    log.info(f"Updated latest version in metadata.json: {app} {version}")

def get_sha256_from_url(url: str) -> str | None:
    try:
        sha256_hash = hashlib.sha256()
        with requests.get(url, stream=True, headers={"User-Agent": "TorchCS"}) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        log.error(f"Failed to download or hash from URL: {url} | Error: {e}")
        return None

def create_metadata(app: str, version: str, win_url: str, linux_url: str):
    folder = BEDROCK_DIR / app / version
    folder.mkdir(parents=True, exist_ok=True)

    metadata = deepcopy(DEDICATED_METADATA)
    metadata["version"] = version

    win_sha = get_sha256_from_url(win_url)
    linux_sha = get_sha256_from_url(linux_url)

    metadata["minecraft"]["binary"]["windows"]["url"] = win_url
    metadata["minecraft"]["binary"]["windows"]["sha256"] = win_sha or ""

    metadata["minecraft"]["binary"]["linux"]["url"] = linux_url
    metadata["minecraft"]["binary"]["linux"]["sha256"] = linux_sha or ""

    meta_path = folder / "metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    log.info(f"Created metadata for {app} version {version}")

def check_new_versions():
    log.info("Checking for new Minecraft versions...")

    downloads = MinecraftRequests.fetch()

    win_url = MinecraftRequests.get_by_type(downloads, DownloadType.SERVER_BEDROCK_WINDOWS)
    linux_url = MinecraftRequests.get_by_type(downloads, DownloadType.SERVER_BEDROCK_LINUX)
    preview_win_url = MinecraftRequests.get_by_type(downloads, DownloadType.SERVER_BEDROCK_PREVIEW_WINDOWS)
    preview_linux_url = MinecraftRequests.get_by_type(downloads, DownloadType.SERVER_BEDROCK_PREVIEW_LINUX)

    release_version = MinecraftDownloadType.get_version(win_url) if win_url else None
    preview_version = MinecraftDownloadType.get_version(preview_win_url) if preview_win_url else None

    release_versions = os.listdir(BEDROCK_DIR / "release")
    preview_versions = os.listdir(BEDROCK_DIR / "preview")

    if release_version and release_version not in release_versions:
        log.info(f"New release version detected: {release_version}")
        create_metadata("release", release_version, win_url, linux_url)
        patch_torchcs_data(release_version, "release")
    else:
        log.info("No new release version found.")

    if preview_version and preview_version not in preview_versions:
        log.info(f"New preview version detected: {preview_version}")
        create_metadata("preview", preview_version, preview_win_url, preview_linux_url)
        patch_torchcs_data(preview_version, "preview")
    else:
        log.info("No new preview version found.")

def main():
    check_new_versions()

if __name__ == "__main__":
    main()