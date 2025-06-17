from enum import Enum
from typing import List, TypedDict, Literal
import requests
import json

class Platform(Enum):
    WINDOWS = "win"
    LINUX = "linux"

class DownloadType(Enum):
    SERVER_BEDROCK_WINDOWS = "serverBedrockWindows"
    SERVER_BEDROCK_LINUX = "serverBedrockLinux"
    SERVER_BEDROCK_PREVIEW_WINDOWS = "serverBedrockPreviewWindows"
    SERVER_BEDROCK_PREVIEW_LINUX = "serverBedrockPreviewLinux"
    SERVER_JAR = "serverJar"

class DownloadLink(TypedDict):
    downloadType: DownloadType
    downloadUrl: str

class MinecraftDownloadResult(TypedDict):
    links: List[DownloadLink]

class MinecraftAPIResponse(TypedDict):
    result: MinecraftDownloadResult

class MinecraftDownloadType:
    _URL_MAP = {
        "bin-win/bedrock-server-": DownloadType.SERVER_BEDROCK_WINDOWS,
        "bin-linux/bedrock-server-": DownloadType.SERVER_BEDROCK_LINUX,
        "bin-win-preview/bedrock-server-": DownloadType.SERVER_BEDROCK_PREVIEW_WINDOWS,
        "bin-linux-preview/bedrock-server-": DownloadType.SERVER_BEDROCK_PREVIEW_LINUX,
        "server.jar": DownloadType.SERVER_JAR,
    }

    @staticmethod
    def resolve(url: str) -> DownloadType | None:
        for pattern, dl_type in MinecraftDownloadType._URL_MAP.items():
            if pattern in url:
                return dl_type
        return None

    @staticmethod
    def get_version(url: str) -> str | None:
        try:
            filename = url.split("/")[-1]
            if "bedrock-server-" in filename:
                return filename.removeprefix("bedrock-server-").removesuffix(".zip")
            elif filename == "server.jar":
                return None
        except Exception:
            return None
        return None

    @staticmethod
    def get_platform(url: str) -> str | None:
        if "bin-win" in url:
            return "windows"
        elif "bin-linux" in url:
            return "linux"
        return None

    @staticmethod
    def get_app(url: str) -> str | None:
        if "preview" in url:
            return "preview"
        elif "bedrock-server-" in url:
            return "release"
        return None

class MinecraftRequests:

    @staticmethod
    def fetch() -> List[DownloadLink]:
        url = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
        response = requests.get(url)
        
        if response.status_code != 200:
            return []

        try:
            data: MinecraftAPIResponse = response.json()
            links = data["result"]["links"]
            return links
        except (KeyError, json.JSONDecodeError) as e:
            return []

    @staticmethod
    def get_by_type(links: List[DownloadLink], dl_type: DownloadType) -> str | None:
        for link in links:
            if link["downloadType"] == dl_type.value:
                return link["downloadUrl"]
        return None