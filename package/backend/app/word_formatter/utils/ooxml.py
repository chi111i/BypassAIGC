"""
docx (OOXML zip) 读写辅助。
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Dict

from lxml import etree


@dataclass
class DocxPackage:
    files: Dict[str, bytes]

    @classmethod
    def from_path(cls, path: str) -> "DocxPackage":
        with zipfile.ZipFile(path, "r") as z:
            files = {name: z.read(name) for name in z.namelist()}
        return cls(files=files)

    @classmethod
    def from_bytes(cls, data: bytes) -> "DocxPackage":
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            files = {name: z.read(name) for name in z.namelist()}
        return cls(files=files)

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in self.files.items():
                z.writestr(name, content)
        return buf.getvalue()

    def write_to(self, path: str) -> None:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in self.files.items():
                z.writestr(name, content)

    def read_xml(self, name: str) -> etree._Element:
        if name not in self.files:
            raise KeyError(f"missing file in docx: {name}")
        return etree.fromstring(self.files[name])

    def write_xml(self, name: str, root: etree._Element) -> None:
        self.files[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")

    def ensure_file(self, name: str, content: bytes) -> None:
        if name not in self.files:
            self.files[name] = content
