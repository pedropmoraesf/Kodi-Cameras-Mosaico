"""Verifica renovação de quadros sem envolver o Kodi nem câmeras reais."""
import os
import tempfile
import unittest
from resources.lib.preview import Preview

class LiveFramesTest(unittest.TestCase):
    def test_frame_name_changes_and_old_content_remains_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            preview = Preview(folder)
            source = preview.image_path("camteste")
            try:
                self.assertIsNone(preview.frame_for_display("camteste"))
                source.write_bytes(b"primeira imagem")
                first = preview.frame_for_display("camteste")
                self.assertEqual(first.read_bytes(), b"primeira imagem")
                self.assertEqual(preview.frame_for_display("camteste"), first)
                for i in range(2, 9):
                    next_frame = source.with_name("atualizacao.jpg")
                    next_frame.write_bytes(("imagem-%d" % i).encode())
                    os.replace(next_frame, source)  # Escrita atômica do FFmpeg
                    versioned = preview.frame_for_display("camteste")
                    self.assertNotEqual(versioned, first)
                    self.assertEqual(versioned.read_bytes(), ("imagem-%d" % i).encode())
                    self.assertLessEqual(len(list(preview.folder.glob("frame_*.jpg"))), 4)
                self.assertFalse(first.exists())
            finally:
                preview.close()
            self.assertFalse(list(preview.folder.glob("frame_*.jpg")))

    def test_old_snapshot_is_cleaned_on_next_open(self):
        with tempfile.TemporaryDirectory() as folder:
            preview = Preview(folder)
            p = preview.folder / "frame_previous.jpg"
            p.write_bytes(b"old")
            restored = Preview(folder)
            self.assertFalse(p.exists())
            preview.close()
            restored.close()

if __name__ == "__main__":
    unittest.main()
