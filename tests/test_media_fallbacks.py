"""Every media element must name a type the browser can act on, and keep a source file.

The two WAV masters are 13 MB each and byte-identical (md5 6727fd5b…), so a page that only
offers the WAV gives a phone nothing it can stream. The AAC copy is the streaming source;
the WAV stays downloadable.
"""
import re
import unittest
from pathlib import Path

MEDIA = Path("site/media")
PAGES = ["site/media/song.html", "site/media/song_mv_4k.html"]


class MediaMarkupTests(unittest.TestCase):
    def test_every_source_declares_a_type(self):
        for page in MEDIA.glob("*.html"):
            for tag in re.findall(r"<source[^>]*>", page.read_text(encoding="utf-8")):
                self.assertIn("type=", tag, f"{page}: {tag}")

    def test_every_video_source_is_mp4(self):
        for page in MEDIA.glob("*.html"):
            for tag in re.findall(r"<source[^>]*\.mp4[^>]*>", page.read_text(encoding="utf-8")):
                self.assertIn('type="video/mp4"', tag, f"{page}: {tag}")

    def test_no_empty_poster_attribute(self):
        for page in Path("site").rglob("*.html"):
            self.assertNotIn('poster=""', page.read_text(encoding="utf-8"), str(page))

    def test_the_song_pages_offer_a_streamable_copy(self):
        for page in PAGES:
            html = Path(page).read_text(encoding="utf-8")
            self.assertIn('type="audio/mp4"', html, page)
            self.assertIn("song_klon8_pop.m4a", html, page)

    def test_the_wav_master_is_still_downloadable(self):
        for page in PAGES:
            html = Path(page).read_text(encoding="utf-8")
            self.assertIn(".wav", html, page)

    def test_the_referenced_media_files_exist(self):
        for page in PAGES:
            for ref in re.findall(r'(?:src|href)="([^"]+\.(?:m4a|wav|mp4|png))"',
                                  Path(page).read_text(encoding="utf-8")):
                self.assertTrue((MEDIA / ref).exists(), f"{page} -> {ref}")

    def test_the_aac_copy_is_smaller_than_the_master(self):
        m4a = MEDIA / "song_klon8_pop.m4a"
        wav = MEDIA / "song_klon8_pop.wav"
        if m4a.exists() and wav.exists():
            self.assertLess(m4a.stat().st_size, wav.stat().st_size // 3)


if __name__ == "__main__":
    unittest.main()
