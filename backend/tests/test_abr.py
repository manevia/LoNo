"""Adaptive HLS output and asset allowlist, with an optional real ffmpeg check."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.broadcast import abr


SID = "12345678-1234-1234-1234-123456789abc"


class AdaptiveHlsTests(unittest.TestCase):
    def test_asset_scope_and_readiness(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "RECORDINGS_DIR", temp):
            root = abr.folder(SID)
            root.mkdir(parents=True)
            (root / "abr_master.m3u8").write_text("#EXTM3U\n")
            self.assertIsNone(abr.master(SID))
            self.assertIsNone(abr.asset(SID, "../private.mp4"))
            self.assertIsNone(abr.asset(SID, "abr_999.m3u8"))
            with self.assertRaises(ValueError):
                abr.folder("../other-session")
            for height, _, _ in abr.PROFILES:
                segment = f"abr_{height}_123.ts"
                (root / segment).write_bytes(b"test")
                (root / f"abr_{height}.m3u8").write_text(f"#EXTM3U\n{segment}\n")
            self.assertIsNotNone(abr.master(SID))
            abr.cleanup(SID)
            self.assertFalse(root.exists())

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_real_three_renditions(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "RECORDINGS_DIR", temp):
            root = abr.folder(SID)
            root.mkdir(parents=True)
            source = Path(temp) / "source.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "6",
                            "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-c:a", "aac", str(source)],
                           check=True, timeout=60)
            subprocess.run(["ffmpeg", *abr.args(str(source), root, True, rtsp=False)], check=True,
                           timeout=60, stdout=subprocess.DEVNULL)
            master = abr.master(SID)
            self.assertIsNotNone(master)
            self.assertEqual(re.findall(r"RESOLUTION=\d+x(\d+)", master.read_text()), ["360", "480", "720"])
            self.assertIn("mp4a.40.2", master.read_text())


if __name__ == "__main__":
    unittest.main()
