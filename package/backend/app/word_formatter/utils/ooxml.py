"""
docx (OOXML zip) 读写辅助。
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Dict

from lxml import etree


MAX_ARCHIVE_ENTRIES = 2048
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRY_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


def _read_archive(archive: zipfile.ZipFile) -> Dict[str, bytes]:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ValueError("DOCX archive contains too many entries")

    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("DOCX archive contains duplicate entries")

    total_size = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise ValueError("Encrypted DOCX archives are not supported")
        if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
            raise ValueError("DOCX archive entry is too large")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("DOCX archive expands beyond the safety limit")
        if (
            info.file_size > 1024 * 1024
            and info.compress_size > 0
            and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
        ):
            raise ValueError("DOCX archive has a suspicious compression ratio")

    return {info.filename: archive.read(info) for info in infos if not info.is_dir()}


@dataclass
class DocxPackage:
    files: Dict[str, bytes]

    @classmethod
    def from_path(cls, path: str) -> "DocxPackage":
        with zipfile.ZipFile(path, "r") as z:
            files = _read_archive(z)
        return cls(files=files)

    @classmethod
    def from_bytes(cls, data: bytes) -> "DocxPackage":
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            files = _read_archive(z)
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
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)
        return etree.fromstring(self.files[name], parser=parser)

    def write_xml(self, name: str, root: etree._Element) -> None:
        self.files[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")

    def ensure_file(self, name: str, content: bytes) -> None:
        if name not in self.files:
            self.files[name] = content
