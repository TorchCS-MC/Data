import os
import re
import json
import hashlib
import requests
import logging
from pathlib import Path
from colorama import init, Fore

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("MinecraftUpdater")

ROOT_DIR = Path(__file__).resolve().parent.parent
BEDROCK_DIR = ROOT_DIR / "bedrock"
TORCHCS_META = ROOT_DIR / "torchcs" / "metadata.json"
VERSIONS_JSON = ROOT_DIR / "torchcs" / "versions.json"
TEMP_DIR = Path(os.getenv("TEMP") or "/tmp") / "MinecraftServerHashes"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def version_key(v):
    return [int(x) for x in v.split(".") if x.isdigit()]

def fetch_download_urls():
    url = "https://www.minecraft.net/de-de/download/server/bedrock"
    headers = {"User-Agent": "TorchCS"}
    response = requests.get(url, headers=headers)

    if not response.ok:
        raise ValueError("Error fetching the download page.")

    html = response.text
    pattern = r"https:\/\/www\.minecraft\.net\/bedrockdedicatedserver\/(bin-(win|linux)(-preview)?)\/bedrock-server-([\d.]+)\.zip"

    links = {}

    for match in re.finditer(pattern, html):
        full_url = match.group(0)
        platform = match.group(2)
        is_preview = match.group(3) == "-preview"
        version = match.group(4)
        release_type = "preview" if is_preview else "release"
        platform_key = "windows" if platform == "win" else "linux"

        links.setdefault(release_type, {}).setdefault(version, {})[platform_key] = full_url

    return links

def download_and_hash(url):
    filename = url.split("/")[-1]
    filepath = TEMP_DIR / filename

    log.info(Fore.BLUE + f"Downloading: {url}")
    try:
        response = requests.get(url, stream=True, headers={"User-Agent": "TorchCS"})
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()
    except Exception as e:
        log.error(Fore.RED + f"Error during download or hashing: {str(e)}")
        return None

def save_version_metadata(release_type, version, platform_data):
    if "windows" not in platform_data or "linux" not in platform_data:
        log.warning(Fore.YELLOW + f"Skipping version {version} ({release_type}) due to missing platforms.")
        return False

    version_dir = BEDROCK_DIR / release_type / version
    version_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "version": version,
        "minecraft": {
            "binary": {
                "windows": {},
                "linux": {}
            }
        }
    }

    complete = True

    for platform in ["windows", "linux"]:
        url = platform_data[platform]
        sha256 = download_and_hash(url)
        if sha256:
            metadata["minecraft"]["binary"][platform] = {
                "url": url,
                "sha256": sha256
            }
        else:
            complete = False
            log.warning(Fore.RED + f"Failed to calculate SHA256 for {platform} {version} ({release_type})")

    if complete:
        with open(version_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        log.info(Fore.GREEN + f"Saved metadata for {release_type} {version}")
    return complete

def update_torchcs_metadata(latest_versions):
    if TORCHCS_META.exists():
        with open(TORCHCS_META, "r", encoding="utf-8") as f:
            torchcs_data = json.load(f)
    else:
        torchcs_data = {
            "latest": {
                "shared": {
                    "loader": "url",
                    "core": "url"
                },
                "binary": {
                    "version": {
                        "release": "",
                        "preview": ""
                    }
                }
            }
        }

    torchcs_data["latest"]["binary"]["version"].update(latest_versions)

    TORCHCS_META.parent.mkdir(parents=True, exist_ok=True)
    with open(TORCHCS_META, "w", encoding="utf-8") as f:
        json.dump(torchcs_data, f, indent=2, ensure_ascii=False)
    log.info(Fore.CYAN + "Updated torchcs/metadata.json")


def check_existing_versions_for_missing_sha256():
    log.info(Fore.CYAN + "Scanning existing versions for missing SHA256 values...")

    for release_type in ["release", "preview"]:
        type_dir = BEDROCK_DIR / release_type
        if not type_dir.exists():
            continue

        for version_folder in type_dir.iterdir():
            metadata_path = version_folder / "metadata.json"
            if not metadata_path.exists():
                continue

            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                windows_data = metadata.get("minecraft", {}).get("binary", {}).get("windows", {})
                linux_data = metadata.get("minecraft", {}).get("binary", {}).get("linux", {})

                missing = False

                for platform, data in [("windows", windows_data), ("linux", linux_data)]:
                    url = data.get("url")
                    sha256 = data.get("sha256", "")

                    if url and not sha256:
                        log.info(Fore.YELLOW + f"Missing SHA256 for {platform} {version_folder.name} ({release_type})")
                        new_hash = download_and_hash(url)
                        if new_hash:
                            metadata["minecraft"]["binary"][platform]["sha256"] = new_hash
                            missing = True

                if missing:
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    log.info(Fore.GREEN + f"Updated missing SHA256 for {version_folder.name} ({release_type})")

            except Exception as e:
                log.error(Fore.RED + f"Error reading/parsing {metadata_path}: {e}")

def validate_versions_json():
    actual_versions = {"release": [], "preview": []}

    for release_type in ["release", "preview"]:
        type_dir = BEDROCK_DIR / release_type
        if not type_dir.exists():
            continue

        for version_folder in type_dir.iterdir():
            if (version_folder / "metadata.json").exists():
                actual_versions[release_type].append(version_folder.name)

    if VERSIONS_JSON.exists():
        with open(VERSIONS_JSON, "r", encoding="utf-8") as f:
            versions_data = json.load(f)
    else:
        versions_data = {"release": [], "preview": []}

    changed = False

    for release_type in ["release", "preview"]:
        for version in actual_versions[release_type]:
            if version not in versions_data[release_type]:
                versions_data[release_type].append(version)
                changed = True

        versions_data[release_type] = [
            v for v in versions_data[release_type] if v in actual_versions[release_type]
        ]

        versions_data[release_type].sort(key=version_key, reverse=True)

    if changed or not VERSIONS_JSON.exists():
        with open(VERSIONS_JSON, "w", encoding="utf-8") as f:
            json.dump(versions_data, f, indent=2, ensure_ascii=False)
        log.info(Fore.CYAN + "Validated and updated versions.json")
    else:
        log.info(Fore.GREEN + "versions.json already up to date")

def fix_missing_latest_versions():
    if not TORCHCS_META.exists() or not VERSIONS_JSON.exists():
        return

    with open(TORCHCS_META, "r", encoding="utf-8") as f:
        torchcs_data = json.load(f)

    with open(VERSIONS_JSON, "r", encoding="utf-8") as f:
        versions_data = json.load(f)

    changed = False
    binary_versions = torchcs_data.get("latest", {}).get("binary", {}).get("version", {})

    for release_type in ["release", "preview"]:
        current = binary_versions.get(release_type, "")
        known_versions = versions_data.get(release_type, [])

        if not current or current not in known_versions:
            if known_versions:
                newest_version = sorted(known_versions, key=version_key, reverse=True)[0]
                binary_versions[release_type] = newest_version
                changed = True
                log.info(
                    Fore.YELLOW
                    + f"Set latest {release_type} version to {newest_version} "
                    + ("(was missing)" if not current else "(was invalid)")
                )

    if changed:
        with open(TORCHCS_META, "w", encoding="utf-8") as f:
            json.dump(torchcs_data, f, indent=2, ensure_ascii=False)
        log.info(Fore.GREEN + "Corrected missing or invalid versions in torchcs/metadata.json")

def update_versions_json(new_versions):
    if VERSIONS_JSON.exists():
        with open(VERSIONS_JSON, "r", encoding="utf-8") as f:
            versions_data = json.load(f)
    else:
        versions_data = {"release": [], "preview": []}

    for release_type in ["release", "preview"]:
        for version in new_versions.get(release_type, []):
            if version not in versions_data[release_type]:
                versions_data[release_type].append(version)

    with open(VERSIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(versions_data, f, indent=2, ensure_ascii=False)
    log.info(Fore.CYAN + "Updated versions.json")

def check_update_and_create_sha256():
    log.info(Fore.CYAN + "Checking for new versions and missing SHA256 values...")

    download_links = fetch_download_urls()
    updated_versions = {"release": [], "preview": []}
    latest_versions = {}

    for release_type, versions in download_links.items():
        for version, platform_data in versions.items():
            metadata_path = BEDROCK_DIR / release_type / version / "metadata.json"
            print(metadata_path)
            if metadata_path.exists():
                continue
            if save_version_metadata(release_type, version, platform_data):
                updated_versions[release_type].append(version)
                latest_versions[release_type] = version

    if latest_versions:
        update_torchcs_metadata(latest_versions)

    if updated_versions["release"] or updated_versions["preview"]:
        update_versions_json(updated_versions)

    check_existing_versions_for_missing_sha256()
    validate_versions_json()
    fix_missing_latest_versions()

def main():
    check_update_and_create_sha256()

if __name__ == "__main__":
    main()