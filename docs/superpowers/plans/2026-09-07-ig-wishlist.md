# IGウィッシュリスト Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** iPhoneの共有シートからワンタップでIG投稿を記録し、Claude Codeセッションでスコアリングして、GitHub Pages上のウィッシュリストページで閲覧できるようにする。

**Architecture:** iPhoneショートカット → GitHub `repository_dispatch` → GitHub Action が `scripts/wishlist_add.py` を実行して `wishlist.json` に inbox 項目を追記(画像はベストエフォート取得)→ PCの Claude Code セッションがスコアリング → 静的ページ `wishlist.html` が表示。

**Tech Stack:** Python 3 標準ライブラリのみ / GitHub Actions / 素のHTML+CSS+JS(ビルドなし・依存なし)

**Spec:** `docs/superpowers/specs/2026-09-07-ig-wishlist-design.md`

## Global Constraints

- 外部パッケージ禁止(Python は標準ライブラリのみ、HTML はCDN・ライブラリ読み込みなし)
- 従量課金API(Claude API等)は使わない
- JSON書き出しは `json.dumps(..., ensure_ascii=False, indent=2)` + 末尾改行
- ページは index.html のダークUI CSS変数(`--bg: #0b0c0e` 等)を踏襲
- コミットメッセージは既存流儀(`feat: ...` + 日本語)に合わせる
- `category` の値域: トップス / ボトムス / アウター / シューズ / バッグ / アクセサリー / その他
- テストは `unittest`(pytest 不使用)。実行は `python3 tests/test_wishlist_add.py`

---

### Task 1: 登録スクリプト `scripts/wishlist_add.py` + テスト

**Files:**
- Create: `scripts/wishlist_add.py`
- Create: `tests/test_wishlist_add.py`
- Create: `wishlist.json`(初期値 `[]`)

**Interfaces:**
- Produces: `extract_shortcode(url: str) -> str | None`、`has_id(items: list, item_id: str) -> bool`、`build_item(shortcode: str, image_path: str, caption: str, today: str) -> dict`、CLI `python3 scripts/wishlist_add.py <instagram-url>`(exit 0、不正URLはスキップ)
- Produces: `wishlist.json` のスキーマ(Task 3 のページ、Task 4 のドキュメントが依存):

```json
{
  "id": "ig-DAbc123",
  "ig_url": "https://www.instagram.com/p/DAbc123/",
  "image": "images/wishlist/ig-DAbc123.jpg",
  "caption": "",
  "brand": "",
  "category": "",
  "score": null,
  "ai_comment": "",
  "similar_owned": [],
  "status": "inbox",
  "added_at": "2026-09-07"
}
```

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_wishlist_add.py`:

```python
import pathlib
import sys
import unittest

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


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python3 tests/test_wishlist_add.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'wishlist_add'`

- [ ] **Step 3: 実装を書く**

`scripts/wishlist_add.py`:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python3 tests/test_wishlist_add.py`
Expected: `OK`(11 tests)

- [ ] **Step 5: wishlist.json を初期化**

`wishlist.json` を内容 `[]`(+改行)で作成する。ページの fetch が 404 にならないために必要。

- [ ] **Step 6: コミット**

```bash
git add scripts/wishlist_add.py tests/test_wishlist_add.py wishlist.json
git commit -m "feat: ウィッシュリスト登録スクリプトを追加"
```

---

### Task 2: GitHub Action `wishlist-add.yml`

**Files:**
- Create: `.github/workflows/wishlist-add.yml`

**Interfaces:**
- Consumes: Task 1 の CLI `python3 scripts/wishlist_add.py <url>`
- Produces: `repository_dispatch` イベント `wishlist-add`(payload: `{"client_payload": {"url": "..."}}`)で起動するワークフロー。Task 4 のセットアップ手順書がこのイベント名に依存

- [ ] **Step 1: ワークフローを書く**

`.github/workflows/wishlist-add.yml`:

```yaml
name: wishlist-add

on:
  repository_dispatch:
    types: [wishlist-add]

concurrency:
  group: wishlist
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  add:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Add post to wishlist
        env:
          IG_URL: ${{ github.event.client_payload.url }}
        run: python3 scripts/wishlist_add.py "$IG_URL"

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          mkdir -p images/wishlist
          git add wishlist.json images/wishlist
          if git diff --cached --quiet; then
            echo "no changes"
            exit 0
          fi
          git commit -m "feat: ウィッシュリストに投稿を追加"
          git pull --rebase origin main
          git push
```

注意: `IG_URL` は必ず `env:` 経由で渡す(`run:` に `${{ }}` を直接埋め込むとシェルインジェクションになる)。

- [ ] **Step 2: YAML構文チェック**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/wishlist-add.yml')); print('ok')"`
Expected: `ok`(PyYAML が無い環境なら `ruby -ryaml -e "YAML.load_file('.github/workflows/wishlist-add.yml'); puts 'ok'"` で代替。どちらも無ければ目視確認と Step 4 の実機確認に委ねる)

- [ ] **Step 3: コミットして push**

```bash
git add .github/workflows/wishlist-add.yml
git commit -m "feat: wishlist-add ワークフローを追加"
git push
```

- [ ] **Step 4: end-to-end 確認(gh CLI が使える場合)**

```bash
gh api repos/monoporhy/clothes/dispatches \
  -f event_type=wishlist-add \
  -f 'client_payload[url]=https://www.instagram.com/p/DAbc123TEST/'
sleep 30
gh run list --workflow=wishlist-add.yml --limit 1
```

Expected: run が `completed` になり、`git pull` 後の `wishlist.json` に `ig-DAbc123TEST` が追加されている(存在しない投稿なので image/caption は空のまま — それが正常)。
確認後、テスト項目を削除して戻す:

```bash
git pull
python3 -c "
import json, pathlib
p = pathlib.Path('wishlist.json')
items = [i for i in json.loads(p.read_text()) if i['id'] != 'ig-DAbc123TEST']
p.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n')
"
git add wishlist.json
git commit -m "chore: e2eテスト項目を削除"
git push
```

`gh` が未認証の場合はこのステップをスキップし、Task 4 のセットアップ(ショートカット実機テスト)で確認する旨を報告する。

---

### Task 3: 閲覧ページ `wishlist.html` + index.html リンク

**Files:**
- Create: `wishlist.html`
- Modify: `index.html`(`.header-nav` にリンク追加、244行目付近)

**Interfaces:**
- Consumes: Task 1 の `wishlist.json` スキーマ、既存 `clothes.json`(`similar_owned` の id 解決に使用)

- [ ] **Step 1: wishlist.html を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ウィッシュリスト</title>
  <style>
    :root {
      --bg:       #0b0c0e;
      --surface:  #111318;
      --border:   #252830;
      --border2:  #1e2028;
      --text:     #c4c8d4;
      --muted:    #5a6070;
      --accent:   #4d7fa8;
      --dim:      #8a90a0;
      --hover-bg: #161820;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Helvetica Neue', Helvetica, 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    header {
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      display: flex;
      align-items: stretch;
    }
    .header-brand {
      padding: 14px 20px 14px 0;
      border-right: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .header-brand .sigil {
      width: 22px; height: 22px;
      display: grid;
      grid-template: 1fr 1fr / 1fr 1fr;
      gap: 3px;
    }
    .header-brand .sigil span { background: var(--accent); display: block; }
    .header-brand .sigil span:nth-child(3) { background: var(--muted); }
    h1 {
      font-size: 0.85rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .header-nav {
      padding: 14px 0 14px 20px;
      display: flex;
      align-items: center;
      gap: 4px;
      margin-left: auto;
    }
    .header-nav a {
      font-size: 0.75rem;
      color: var(--muted);
      text-decoration: none;
      letter-spacing: 0.08em;
      padding: 5px 12px;
      border: 1px solid transparent;
      transition: color 0.15s, border-color 0.15s;
    }
    .header-nav a:hover { color: var(--accent); border-color: var(--border); }

    .control-bar {
      display: flex;
      align-items: center;
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }
    .tab-bar { display: flex; }
    .tab-bar button {
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      color: var(--muted);
      font-size: 0.75rem;
      font-family: inherit;
      letter-spacing: 0.1em;
      padding: 10px 16px;
      cursor: pointer;
      white-space: nowrap;
      transition: color 0.15s, border-color 0.15s;
      margin-bottom: -1px;
    }
    .tab-bar button:hover { color: var(--text); }
    .tab-bar button.active { color: var(--accent); border-bottom-color: var(--accent); }
    .score-filter {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.7rem;
      color: var(--muted);
      white-space: nowrap;
      padding-left: 16px;
    }
    .score-filter select {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      font-family: inherit;
      font-size: 0.75rem;
      padding: 4px 8px;
    }

    .section-label {
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      padding: 20px 24px 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
      gap: 16px;
      padding: 16px 24px 32px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      display: flex;
      flex-direction: column;
    }
    .card .thumb {
      width: 100%;
      aspect-ratio: 4 / 5;
      object-fit: cover;
      display: block;
      background: var(--border2);
    }
    .card .no-image {
      width: 100%;
      aspect-ratio: 4 / 5;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      background: var(--border2);
    }
    .card-body { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
    .card-top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
    .card-brand { font-size: 0.75rem; letter-spacing: 0.06em; }
    .card-cat { font-size: 0.65rem; color: var(--muted); letter-spacing: 0.08em; }
    .score-badge {
      font-size: 0.8rem;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--accent);
      white-space: nowrap;
    }
    .card-comment { font-size: 0.72rem; color: var(--dim); line-height: 1.5; flex: 1; }
    .card-caption {
      font-size: 0.68rem;
      color: var(--muted);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .similar {
      border-top: 1px solid var(--border2);
      padding-top: 8px;
      font-size: 0.65rem;
      color: var(--muted);
      line-height: 1.6;
    }
    .similar .similar-label {
      font-size: 0.6rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .card-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid var(--border2);
      padding-top: 10px;
    }
    .card-actions a {
      font-size: 0.7rem;
      color: var(--accent);
      text-decoration: none;
      letter-spacing: 0.06em;
    }
    .card-actions button {
      background: none;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.65rem;
      font-family: inherit;
      padding: 4px 10px;
      cursor: pointer;
      letter-spacing: 0.06em;
    }
    .card-actions button:hover { color: var(--text); border-color: var(--muted); }

    .empty-note { padding: 16px 24px 32px; color: var(--muted); font-size: 0.75rem; }
    .footer-note { padding: 0 24px 32px; font-size: 0.68rem; color: var(--muted); }
    .footer-note a { color: var(--muted); cursor: pointer; text-decoration: underline; }

    @media (max-width: 600px) {
      header, .control-bar { padding-left: 12px; padding-right: 12px; }
      .section-label { padding: 16px 12px 0; }
      .grid { padding: 12px 12px 24px; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
      .footer-note { padding: 0 12px 24px; }
    }
  </style>
</head>
<body>

  <header>
    <div class="header-brand">
      <div class="sigil">
        <span></span><span></span><span></span><span></span>
      </div>
      <h1>Wishlist</h1>
    </div>
    <nav class="header-nav">
      <a href="index.html">← カタログ</a>
      <a href="coordinate.html">コーデ →</a>
    </nav>
  </header>

  <div class="control-bar">
    <div class="tab-bar" id="tab-bar"></div>
    <label class="score-filter">
      スコア
      <select id="min-score">
        <option value="0">すべて</option>
        <option value="60">60+</option>
        <option value="70">70+</option>
        <option value="80">80+</option>
      </select>
    </label>
  </div>

  <div id="content"></div>

  <div class="footer-note">
    非表示: <span id="hidden-count">0</span>件
    <a id="reset-hidden">リセット</a>
  </div>

  <script>
    const CATS = ['ALL', 'トップス', 'ボトムス', 'アウター', 'シューズ', 'バッグ', 'アクセサリー', 'その他'];
    const HIDDEN_KEY = 'wishlist-hidden';

    let wishlist = [];
    let clothesById = {};
    let filterCat = 'ALL';
    let minScore = 0;

    function esc(str) {
      return String(str || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function getHidden() {
      try { return JSON.parse(localStorage.getItem(HIDDEN_KEY)) || []; }
      catch { return []; }
    }
    function hideItem(id) {
      const h = getHidden();
      if (!h.includes(id)) h.push(id);
      localStorage.setItem(HIDDEN_KEY, JSON.stringify(h));
      render();
    }
    function resetHidden() {
      localStorage.removeItem(HIDDEN_KEY);
      render();
    }

    function similarHTML(item) {
      const owned = (item.similar_owned || [])
        .map(id => clothesById[id])
        .filter(Boolean);
      if (!owned.length) return '';
      const rows = owned.map(c => `${esc(c.brand)} / ${esc(c.name)}`).join('<br>');
      return `<div class="similar"><div class="similar-label">似た手持ち</div>${rows}</div>`;
    }

    function cardHTML(item) {
      const img = item.image
        ? `<img class="thumb" src="${esc(item.image)}" alt="" loading="lazy">`
        : `<div class="no-image">NO IMAGE</div>`;
      const score = item.score != null ? `<span class="score-badge">${esc(item.score)}</span>` : '';
      const brand = item.brand || '(未整理)';
      return `
        <div class="card" data-id="${esc(item.id)}">
          ${img}
          <div class="card-body">
            <div class="card-top">
              <div>
                <div class="card-brand">${esc(brand)}</div>
                <div class="card-cat">${esc(item.category || '')}</div>
              </div>
              ${score}
            </div>
            ${item.ai_comment ? `<div class="card-comment">${esc(item.ai_comment)}</div>` : ''}
            ${!item.ai_comment && item.caption ? `<div class="card-caption">${esc(item.caption)}</div>` : ''}
            ${similarHTML(item)}
            <div class="card-actions">
              <a href="${esc(item.ig_url)}" target="_blank" rel="noopener">投稿を見る ↗</a>
              <button class="hide-btn">非表示</button>
            </div>
          </div>
        </div>`;
    }

    function sectionHTML(label, items, emptyNote) {
      if (!items.length) {
        return emptyNote
          ? `<div class="section-label">${label}</div><div class="empty-note">${emptyNote}</div>`
          : '';
      }
      return `<div class="section-label">${label}</div>
        <div class="grid">${items.map(cardHTML).join('')}</div>`;
    }

    function render() {
      const hidden = getHidden();
      const visible = wishlist.filter(i =>
        !hidden.includes(i.id) &&
        (filterCat === 'ALL' || i.category === filterCat));

      const inbox = visible.filter(i => i.status === 'inbox');
      const scored = visible
        .filter(i => i.status === 'scored' && (i.score == null || i.score >= minScore))
        .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

      const content = document.getElementById('content');
      content.innerHTML =
        sectionHTML('整理待ち', inbox, '') +
        sectionHTML('厳選リスト', scored,
          'まだありません。IGの共有シートから「欲しい服に追加」で貯めて、PCで「ウィッシュリスト整理して」と頼むとここに並びます。');

      content.querySelectorAll('.hide-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          hideItem(e.target.closest('.card').dataset.id);
        });
      });
      document.getElementById('hidden-count').textContent = hidden.length;
    }

    function renderTabs() {
      const bar = document.getElementById('tab-bar');
      bar.innerHTML = '';
      CATS.forEach(cat => {
        const btn = document.createElement('button');
        btn.textContent = cat;
        if (cat === filterCat) btn.classList.add('active');
        btn.addEventListener('click', () => {
          filterCat = cat;
          document.querySelectorAll('#tab-bar button').forEach(b =>
            b.classList.toggle('active', b.textContent === filterCat));
          render();
        });
        bar.appendChild(btn);
      });
    }

    document.getElementById('min-score').addEventListener('change', e => {
      minScore = Number(e.target.value);
      render();
    });
    document.getElementById('reset-hidden').addEventListener('click', resetHidden);

    Promise.all([
      fetch('wishlist.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch('clothes.json').then(r => r.ok ? r.json() : []).catch(() => []),
    ])
      .then(([wl, clothes]) => {
        wishlist = wl;
        clothes.forEach(c => { clothesById[c.id] = c; });
        renderTabs();
        render();
      })
      .catch(err => {
        document.body.insertAdjacentHTML('beforeend',
          `<p style="color:#c44;padding:20px">wishlist.json の読み込みに失敗しました (${err.message})</p>`);
      });
  </script>
</body>
</html>
```

- [ ] **Step 2: index.html のヘッダーにリンク追加**

`index.html` の `.header-nav`(現在 `<a href="coordinate.html">コーデ →</a>` のみ)を次に変更:

```html
    <nav class="header-nav">
      <a href="wishlist.html">ウィッシュ →</a>
      <a href="coordinate.html">コーデ →</a>
    </nav>
```

- [ ] **Step 3: サンプルデータで表示確認**

一時的に `wishlist.json` を以下に置き換える(確認後に戻す):

```json
[
  {
    "id": "ig-SAMPLE1",
    "ig_url": "https://www.instagram.com/p/SAMPLE1/",
    "image": "",
    "caption": "新作のウールジャケット入荷しました",
    "brand": "",
    "category": "",
    "score": null,
    "ai_comment": "",
    "similar_owned": [],
    "status": "inbox",
    "added_at": "2026-09-07"
  },
  {
    "id": "ig-SAMPLE2",
    "ig_url": "https://www.instagram.com/p/SAMPLE2/",
    "image": "",
    "caption": "",
    "brand": "LIDNM",
    "category": "トップス",
    "score": 82,
    "ai_comment": "手持ちのウールスラックスと相性が良い。白Tと用途が被る点だけ注意。",
    "similar_owned": ["wym-extra-fine-cotton-basic-tee-2026-03"],
    "status": "scored",
    "added_at": "2026-09-07"
  }
]
```

Run:

```bash
python3 -m http.server 8765 &
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8765/wishlist.html
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8765/wishlist.json
kill %1
```

Expected: `200` が2回。加えてJS構文チェック: `node --check` はHTML不可のため、`python3 -c` でscriptタグ抽出→ `node --check` があれば実施、なければブラウザ確認(メインセッションで実施)に委ねる。
確認できたら `wishlist.json` を `[]`(+改行)に戻す。

- [ ] **Step 4: コミット**

```bash
git add wishlist.html index.html wishlist.json
git commit -m "feat: ウィッシュリストページを追加"
```

---

### Task 4: ドキュメント(セットアップ手順・整理手順・CLAUDE.md)

**Files:**
- Create: `docs/wishlist-setup.md`
- Create: `docs/wishlist-triage.md`
- Modify: `CLAUDE.md`(末尾にセクション追加)

**Interfaces:**
- Consumes: Task 2 のイベント名 `wishlist-add`、Task 1 のスキーマ

- [ ] **Step 1: セットアップ手順書を書く**

`docs/wishlist-setup.md`:

````markdown
# ウィッシュリスト セットアップ手順(iPhone)

## 1. GitHub PAT(fine-grained)を発行する

1. https://github.com/settings/personal-access-tokens/new を開く
2. Token name: `wishlist-shortcut`
3. Expiration: 1年(失効したら再発行してショートカット内のトークンを差し替える)
4. Repository access: **Only select repositories** → `monoporhy/clothes`
5. Permissions → Repository permissions → **Contents: Read and write**(これだけでよい)
6. Generate token → 表示されたトークン(`github_pat_...`)をコピー

## 2. iPhoneショートカットを作る

ショートカットアプリ → 「+」で新規作成:

1. 名前: **欲しい服に追加**
2. 上部の(i)→ **共有シートに表示** をオン。「共有シートタイプ」は **URL** と **テキスト** にする
3. アクションを追加: **URLの内容を取得**
   - URL: `https://api.github.com/repos/monoporhy/clothes/dispatches`
   - 「方法を表示」を開き Method: **POST**
   - ヘッダを追加:
     - `Authorization` = `Bearer github_pat_XXXX`(手順1のトークン)
     - `Accept` = `application/vnd.github+json`
   - 本文を要求: **JSON**
     - `event_type`(テキスト)= `wishlist-add`
     - `client_payload`(辞書)→ 中に `url`(テキスト)= 変数「**ショートカットの入力**」
4. アクションを追加: **通知を表示** → 「ウィッシュリストに追加しました」

## 3. 使い方

Instagramアプリで投稿の「共有」(紙飛行機ではなく「…」→共有 でもよい)→ 共有シートから **欲しい服に追加** をタップ。
1〜2分後に https://monoporhy.github.io/clothes/wishlist.html の「整理待ち」に現れる。

## トラブルシューティング

- 通知が失敗(401): PATの期限切れ → 手順1で再発行し、ショートカットの `Authorization` ヘッダを差し替える
- 「整理待ち」に出ない: GitHub の Actions タブで `wishlist-add` の実行ログを確認
- 画像が NO IMAGE: Instagram側の取得拒否。PCで「ウィッシュリスト整理して」と頼めば補完を試みる
````

- [ ] **Step 2: 整理手順書を書く**

`docs/wishlist-triage.md`:

````markdown
# ウィッシュリスト整理手順(Claude Code向け)

ユーザーが「ウィッシュリスト整理して」と言ったら、この手順で `wishlist.json` の
`status: "inbox"` 項目を処理する。

## 手順

1. `git pull` してから `wishlist.json` の inbox 項目を列挙する
2. `image` が空の項目は補完を試みる:
   - `ig_url` の embed ページ(`{ig_url}embed/captioned/`)を WebFetch またはブラウザで取得
   - 無理ならユーザーにスクリーンショット共有を依頼し、`images/wishlist/{id}.jpg` に保存
3. 各項目について画像・キャプションを見て以下を記入する:
   - `brand`: 投稿者・キャプションから推定(不明なら `""`)
   - `category`: トップス / ボトムス / アウター / シューズ / バッグ / アクセサリー / その他
   - `score`: 0–100(下記基準)
   - `ai_comment`: 買うべきか迷ったときの判断材料を1〜2文
   - `similar_owned`: clothes.json の似た手持ち服の id 配列
   - `status`: `"scored"` に変更
4. `git add wishlist.json images/wishlist && git commit -m "feat: ウィッシュリストを整理" && git push`

## スコア基準(0–100)

- **減点**: 手持ちとの重複(同カテゴリ・同色・同シルエットを既に所有)。重複相手は `similar_owned` に必ず記録
- **加点**: 手持ちとコーデが組みやすい(色相環の同系色/補色関係、不足カテゴリの補完)
- **小幅加点**: 所有ブランド傾向(LIDNM / WYM など)との一致
- 目安: 80+ = 買い候補、60–79 = 検討、60未満 = 見送り推奨
````

- [ ] **Step 3: CLAUDE.md にセクション追加**

`CLAUDE.md` 末尾に追加:

```markdown
## Wishlist (IGウィッシュリスト)

Instagramで見つけた欲しい服を貯める仕組み。手持ちカタログとは別ファイル。

- `wishlist.json` — ウィッシュリスト本体(スキーマは `docs/superpowers/specs/2026-09-07-ig-wishlist-design.md`)
- `wishlist.html` — 閲覧ページ(スコア順カード表示)
- `.github/workflows/wishlist-add.yml` — iPhoneショートカットからの `repository_dispatch` (`wishlist-add`) で `scripts/wishlist_add.py` を実行し inbox 項目を追記
- 「**ウィッシュリスト整理して**」と言われたら `docs/wishlist-triage.md` の手順でスコアリングする
- セットアップ手順(PAT・ショートカット作成): `docs/wishlist-setup.md`
```

- [ ] **Step 4: コミット**

```bash
git add docs/wishlist-setup.md docs/wishlist-triage.md CLAUDE.md
git commit -m "docs: ウィッシュリストのセットアップ・整理手順を追加"
```

---

## 実装後(メインセッションで行う)

1. `git push` して GitHub Pages 反映を確認
2. wishlist.html をブラウザで目視確認(サンプルデータ or 実データ)
3. ユーザーと一緒に `docs/wishlist-setup.md` に沿って PAT 発行・ショートカット作成・実機テスト
