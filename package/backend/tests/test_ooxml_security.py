import io
import unittest
import zipfile

from app.word_formatter.utils.ooxml import DocxPackage


class OoxmlSecurityTests(unittest.TestCase):
    def test_suspicious_compression_ratio_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b"A" * (4 * 1024 * 1024))

        with self.assertRaises(ValueError):
            DocxPackage.from_bytes(buffer.getvalue())

    def test_external_entities_are_not_resolved(self):
        package = DocxPackage(
            files={
                "word/document.xml": (
                    b'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                    b"<root>&xxe;</root>"
                )
            }
        )

        root = package.read_xml("word/document.xml")

        self.assertIsNone(root.text)
        self.assertEqual(len(root), 1)


if __name__ == "__main__":
    unittest.main()
