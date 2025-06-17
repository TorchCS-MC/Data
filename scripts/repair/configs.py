from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BEDROCK_DIR = ROOT_DIR / "bedrock"
TORCHCS_META_FILE = ROOT_DIR / "torchcs" / "metadata.json"
TORCHCS_VERSIONS_JSON_FILE = ROOT_DIR / "torchcs" / "versions.json"

DEDICATED_METADATA = {
  "version": "",
  "minecraft": {
    "binary": {
      "windows": {
        "url": "",
        "sha256": ""
      },
      "linux": {
        "url": "",
        "sha256": ""
      }
    }
  }
}