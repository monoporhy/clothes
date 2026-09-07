"""IG投稿URLを wishlist.json に inbox 項目として登録する。

GitHub Action (.github/workflows/wishlist-add.yml) から呼ばれる。
画像・キャプションは embed ページ経由のベストエフォート取得。
取れなくても登録は成功させる(PC整理時に補完する)。

使い方: python3 scripts/wishlist_add.py <instagram-url>
"""
import datetime
import html
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
WISHLIST_PATH = ROOT / 'wishlist.json'
IMAGES_DIR = ROOT / 'images' / 'wishlist'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

SHORTCODE_RE = re.compile(r'instagram\.com/(?:[^/?#]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')


def extract_shortcode(url):
    m = SHORTCODE_RE.search(url or '')
    return m.group(1) if m else None


def has_id(items, item_id):
    return any(i.get('id') == item_id for i in items)


def build_item(shortcode, image_path, caption, today):
    return {
        'id': f'ig-{shortcode}',
        'ig_url': f'https://www.instagram.com/p/{shortcode}/',
        'image': image_path,
        'caption': caption,
        'brand': '',
        'category': '',
        'score': None,
        'ai_comment': '',
        'similar_owned': [],
        'status': 'inbox',
        'added_at': today,
    }


def fetch_embed(shortcode):
    """embedページから (画像bytes | None, キャプション str) を取得。失敗は握りつぶす。"""
    url = f'https://www.instagram.com/p/{shortcode}/embed/captioned/'
    try:
        req = urllib.request.Request(url, headers=UA)
        page = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'embed fetch failed: {e}')
        return None, ''

    caption = ''
    m = re.search(r'class="Caption"[^>]*>(.*?)<div class="CaptionComments"', page, re.S)
    if m:
        caption = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1)))
        caption = re.sub(r'\s+', ' ', caption).strip()

    img_bytes = None
    m = re.search(r'<img[^>]*class="[^"]*EmbeddedMediaImage[^"]*"[^>]*src="([^"]+)"', page)
    if m:
        img_url = html.unescape(m.group(1))
        try:
            img_req = urllib.request.Request(img_url, headers=UA)
            img_bytes = urllib.request.urlopen(img_req, timeout=15).read()
        except Exception as e:
            print(f'image fetch failed: {e}')
    return img_bytes, caption


def main(argv):
    if len(argv) < 2:
        print('usage: wishlist_add.py <instagram-url>')
        return 1
    shortcode = extract_shortcode(argv[1])
    if not shortcode:
        print(f'not an instagram post url, skipping: {argv[1]}')
        return 0
    items = json.loads(WISHLIST_PATH.read_text()) if WISHLIST_PATH.exists() else []
    item_id = f'ig-{shortcode}'
    if has_id(items, item_id):
        print(f'already exists: {item_id}')
        return 0
    img_bytes, caption = fetch_embed(shortcode)
    image_path = ''
    if img_bytes:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        (IMAGES_DIR / f'{item_id}.jpg').write_bytes(img_bytes)
        image_path = f'images/wishlist/{item_id}.jpg'
        print(f'saved: {image_path}')
    today = datetime.date.today().isoformat()
    items.append(build_item(shortcode, image_path, caption, today))
    WISHLIST_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n')
    print(f'added: {item_id}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
