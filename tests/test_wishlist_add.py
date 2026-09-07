import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))
import wishlist_add


class TestExtractShortcode(unittest.TestCase):
    def test_post_url(self):
        url = 'https://www.instagram.com/p/DAbc123/?igsh=xyz'
        self.assertEqual(wishlist_add.extract_shortcode(url), 'DAbc123')

    def test_reel_url(self):
        url = 'https://www.instagram.com/reel/Xy_z-9/'
        self.assertEqual(wishlist_add.extract_shortcode(url), 'Xy_z-9')

    def test_username_prefixed_url(self):
        url = 'https://www.instagram.com/lidnm_official/p/Cshort99/'
        self.assertEqual(wishlist_add.extract_shortcode(url), 'Cshort99')

    def test_non_instagram_url(self):
        self.assertIsNone(wishlist_add.extract_shortcode('https://example.com/p/abc/'))

    def test_profile_url(self):
        self.assertIsNone(wishlist_add.extract_shortcode('https://www.instagram.com/lidnm_official/'))

    def test_none_input(self):
        self.assertIsNone(wishlist_add.extract_shortcode(None))


class TestHasId(unittest.TestCase):
    def test_found(self):
        items = [{'id': 'ig-a'}, {'id': 'ig-b'}]
        self.assertTrue(wishlist_add.has_id(items, 'ig-b'))

    def test_not_found(self):
        self.assertFalse(wishlist_add.has_id([{'id': 'ig-a'}], 'ig-x'))

    def test_empty(self):
        self.assertFalse(wishlist_add.has_id([], 'ig-a'))


class TestBuildItem(unittest.TestCase):
    def test_fields(self):
        item = wishlist_add.build_item('DAbc123', 'images/wishlist/ig-DAbc123.jpg', 'キャプション', '2026-09-07')
        self.assertEqual(item, {
            'id': 'ig-DAbc123',
            'ig_url': 'https://www.instagram.com/p/DAbc123/',
            'image': 'images/wishlist/ig-DAbc123.jpg',
            'caption': 'キャプション',
            'brand': '',
            'category': '',
            'score': None,
            'ai_comment': '',
            'similar_owned': [],
            'status': 'inbox',
            'added_at': '2026-09-07',
        })

    def test_no_image(self):
        item = wishlist_add.build_item('X', '', '', '2026-09-07')
        self.assertEqual(item['image'], '')
        self.assertEqual(item['status'], 'inbox')


class TestMainCorruptWishlist(unittest.TestCase):
    def test_corrupt_json_aborts_without_overwriting(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = pathlib.Path(d) / 'wishlist.json'
            tmp_path.write_text('{broken')
            with patch.object(wishlist_add, 'WISHLIST_PATH', tmp_path):
                result = wishlist_add.main(['wishlist_add.py', 'https://www.instagram.com/p/Xabc/'])
            self.assertEqual(result, 1)
            self.assertEqual(tmp_path.read_text(), '{broken')


if __name__ == '__main__':
    unittest.main()
