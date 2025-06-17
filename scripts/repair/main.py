import os
import json
import hashlib
import requests
from pathlib import Path
from configs import BEDROCK_DIR, TORCHCS_VERSIONS_JSON_FILE

def get_sha256_from_url(url: str) -> str | None:
    try:
        sha256_hash = hashlib.sha256()
        with requests.get(url, stream=True, headers={"User-Agent": "TorchCS"}) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception:
        return None

def check_sha256(meta_path: Path) -> bool:
    if not meta_path.exists():
        return False

    try:
        with meta_path.open("r+", encoding="utf-8") as f:
            metadata = json.load(f)

        changed = False
        binary = metadata.get("minecraft", {}).get("binary", {})

        for platform in ("windows", "linux"):
            section = binary.get(platform, {})
            url = section.get("url", "").strip()
            sha = section.get("sha256", "").strip()

            if url and not sha:
                new_sha = get_sha256_from_url(url)
                if new_sha:
                    section["sha256"] = new_sha
                    changed = True

        if changed:
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        return True

    except Exception:
        return False

def check_versions_file():
    with open(TORCHCS_VERSIONS_JSON_FILE, "r", encoding="utf-8") as f:
        versions_data = json.load(f)

    cleaned = {}

    for app, version_list in versions_data.items():
        valid_versions = []
        for version in version_list:
            meta_path = BEDROCK_DIR / app / version / "metadata.json"
            if check_sha256(meta_path):
                valid_versions.append(version)
        cleaned[app] = valid_versions

    with open(TORCHCS_VERSIONS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)

def main():
    check_versions_file()

if __name__ == "__main__":
    main()
