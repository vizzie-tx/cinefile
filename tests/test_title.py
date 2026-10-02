"""Run with: python3 -m unittest discover -s tests"""

import json
from pathlib import Path
import subprocess
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "title.sh"


class TitleTests(unittest.TestCase):
    def scan(self, target, inline=False):
        titles = []
        for index, playlist in enumerate(
            [None, 800, {}, [], "00800.MPLS", "00900.mpls"], start=1
        ):
            titles.append({
                "Index": index,
                "Playlist": playlist,
                "Duration": {"Hours": 1, "Minutes": 2, "Seconds": 3},
                "Geometry": {
                    "Width": 1920, "Height": 1080,
                    "PAR": {"Num": 1, "Den": 1},
                },
                "ChapterList": [{}, {}],
            })
        # Include a title with no Playlist field at all.
        titles.append({**titles[0], "Index": 7})
        del titles[-1]["Playlist"]
        scan = "Scan progress\nJSON Title Set:" + (" " if inline else "\n")
        scan += json.dumps({"TitleList": titles}) + "\n"
        result = subprocess.run(
            ["bash", str(SCRIPT), target], input=scan,
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_playlist_case_insensitive(self):
        for target in ["00800.mpls", "00800.MPLS"]:
            with self.subTest(target=target):
                rows = self.scan(target)
                self.assertEqual([row["title"] for row in rows], [5])
                self.assertEqual(rows[0]["mpls"], "00800.MPLS")
                self.assertEqual(rows[0]["duration"], "01:02:03")
                self.assertEqual(rows[0]["format"], "widescreen")

    def test_numeric_title_with_every_playlist_type(self):
        for index in range(1, 8):
            with self.subTest(index=index):
                self.assertEqual(
                    [row["title"] for row in self.scan(str(index))], [index]
                )

    def test_inline_json(self):
        self.assertEqual(
            [row["title"] for row in self.scan("00900.mpls", inline=True)], [6]
        )

    def test_no_match(self):
        for target in ["missing.mpls", "99", "800"]:
            with self.subTest(target=target):
                self.assertEqual(self.scan(target), [])


if __name__ == "__main__":
    unittest.main()
