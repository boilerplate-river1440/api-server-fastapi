from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .config import settings


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile, folder: str) -> str:
        destination_dir = self.root / folder
        destination_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename or "upload.bin").suffix
        filename = f"{uuid4().hex}{suffix}"
        destination = destination_dir / filename
        destination.write_bytes(await upload.read())
        return f"/{self.root.name}/{folder}/{filename}"


storage = LocalStorage(settings.upload_dir)
