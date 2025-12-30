"""
老 .doc 转 .docx（可选）：依赖系统安装 LibreOffice。

- 若不存在 libreoffice/soffice，则抛出 RuntimeError
- 转换输出为 .docx 临时文件路径
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _find_soffice() -> str:
    for exe in ["libreoffice", "soffice"]:
        p = shutil.which(exe)
        if p:
            return p
    raise RuntimeError("LibreOffice (libreoffice/soffice) not found in PATH; cannot convert .doc")


def convert_doc_to_docx(doc_path: str) -> str:
    doc_path = os.path.abspath(doc_path)
    if not doc_path.lower().endswith(".doc"):
        raise ValueError("convert_doc_to_docx expects a .doc file")

    soffice = _find_soffice()
    out_dir = tempfile.mkdtemp(prefix="doc2docx_")
    try:
        cmd = [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            "--convert-to",
            "docx",
            "--outdir",
            out_dir,
            doc_path,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {proc.stderr.strip() or proc.stdout.strip()}")

        # LibreOffice 会输出同名 .docx
        base = Path(doc_path).stem
        converted = os.path.join(out_dir, f"{base}.docx")
        if not os.path.exists(converted):
            # 容错：目录里找第一个 docx
            docx_files = list(Path(out_dir).glob("*.docx"))
            if not docx_files:
                raise RuntimeError("conversion succeeded but no .docx produced")
            converted = str(docx_files[0])

        # 复制到一个稳定路径（避免 out_dir 之后被清理）
        final_path = tempfile.mktemp(prefix="converted_", suffix=".docx")
        shutil.copy2(converted, final_path)
        return final_path
    finally:
        # 清理临时目录
        shutil.rmtree(out_dir, ignore_errors=True)
