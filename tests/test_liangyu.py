import unittest

from liangyu import LiangYuDictionary, format_matches


ENTRIES = [
    {"abbr": "你·我·母", "text": "你是我的母亲"},
    {"abbr": "全·切", "text": "全部切碎"},
    {"abbr": "快·说·否·头·砸", "text": "快点说，否则……就把你的头砸碎"},
]


class LiangYuDictionaryTest(unittest.TestCase):
    def setUp(self):
        self.dictionary = LiangYuDictionary(ENTRIES)

    def test_matches_dotted_abbreviation(self):
        matches = self.dictionary.find_matches("请翻译 快·说·否·头·砸")

        self.assertEqual(matches[0].abbr, "快·说·否·头·砸")

    def test_matches_custom_phrase(self):
        matches = self.dictionary.find_matches("你·我·母")

        self.assertEqual(matches[0].text, "你是我的母亲")

    def test_matches_compact_custom_phrase(self):
        matches = self.dictionary.find_matches("他说你我母")

        self.assertEqual(matches[0].text, "你是我的母亲")

    def test_matches_compact_long_abbreviation(self):
        matches = self.dictionary.find_matches("良秀：快说否头砸")

        self.assertEqual(matches[0].text, "快点说，否则……就把你的头砸碎")

    def test_short_compact_only_matches_exact_message(self):
        self.assertEqual(self.dictionary.find_matches("我要全切了"), [])

        matches = self.dictionary.find_matches("全切")
        self.assertEqual(matches[0].abbr, "全·切")

    def test_lookup_ignores_separators(self):
        entry = self.dictionary.lookup("快说否头砸")

        self.assertIsNotNone(entry)
        self.assertEqual(entry.abbr, "快·说·否·头·砸")

    def test_format_falls_back_on_bad_template(self):
        matches = self.dictionary.find_matches("快说否头砸")

        self.assertIn("快·说·否·头·砸", format_matches(matches, item_format="{missing}"))


if __name__ == "__main__":
    unittest.main()
