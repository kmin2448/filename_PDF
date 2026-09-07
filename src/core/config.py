import os
import json

APP_NAME = "PDF_Auto-Renamer"
DEFAULT_FOLDER_NAME = "청구서정리"


class Config:
    """루트 폴더 등 사용자 설정을 파일로 보관 (%APPDATA%/PDF_Auto-Renamer/config.json)"""

    _cache = None

    @staticmethod
    def get_config_path() -> str:
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        return os.path.join(base, APP_NAME, "config.json")

    @staticmethod
    def get_default_root() -> str:
        """기본 루트 폴더: 바탕화면/청구서정리"""
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        return os.path.join(desktop, DEFAULT_FOLDER_NAME)

    @staticmethod
    def load() -> dict:
        if Config._cache is not None:
            return Config._cache

        data = {}
        path = Config.get_config_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data = loaded
        except Exception:
            # 설정 파일이 깨진 경우 기본값으로 동작
            data = {}

        Config._cache = data
        return data

    @staticmethod
    def save():
        path = Config.get_config_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(Config.load(), f, ensure_ascii=False, indent=2)
        except Exception:
            # 설정 저장 실패가 본 작업을 막지 않도록 무시
            pass

    @staticmethod
    def get_root_dir() -> str:
        """비목별 폴더가 생성될 루트 폴더 경로 반환"""
        root = Config.load().get("root_dir", "")
        if root and str(root).strip():
            return str(root).strip()
        return Config.get_default_root()

    @staticmethod
    def set_root_dir(path: str):
        data = Config.load()
        data["root_dir"] = path
        Config._cache = data
        Config.save()

    @staticmethod
    def reset_root_dir():
        data = Config.load()
        data.pop("root_dir", None)
        Config._cache = data
        Config.save()
