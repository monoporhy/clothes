# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Personal clothes catalog published at https://monoporhy.github.io/clothes/. Used to check "do I already own something similar / what size fits me" while shopping.

## Adding Items

2-step flow:

1. **URL を受け取ったら** — URL をフェッチして brand, name, **og:image**, category を抽出し、ユーザーに確認する
   - og:image が取得できた場合: 画像を `images/{id}.jpg` としてダウンロードし、`image` フィールドに `images/{id}.jpg` を記録する
   - og:image が取得できない場合: `image: ""` のまま（後で手動追加）
2. **サイズ（とカラー）を受け取ったら** — サイズページまたは商品ページから 着丈/肩幅/身幅/袖丈 を抽出して表示する
   - 取得できない場合: スクリーンショットを共有してもらい、数値を手動で転記する
3. `clothes.json` と `images/{id}.jpg` を両方コミットして push: `git add clothes.json images/ && git commit -m "feat: add [item description]" && git push`

## Data Schema (`clothes.json`)

```json
{
  "id": "brand-color-size-yyyy-mm",       // kebab-case, lowercase
  "category": "トップス",                  // see valid values below
  "brand": "ブランド名",
  "name": "商品名",
  "color": "カラー",
  "color_hex": "#9BA4A4",              // 近似HEX（設定しない場合は ""）
  "size": "サイズ",
  "dimensions": { "着丈": 69, "肩幅": 44, "身幅": 52, "袖丈": 20 },
  "url": "https://...",
  "image": "images/{id}.jpg",              // ローカル保存パス（取得できない場合は ""）
  "purchased_at": "yyyy-mm"
}
```

Valid categories: `トップス` / `ボトムス` / `アウター` / `シューズ` / `バッグ` / `アクセサリー` / `その他`

Dimension keys by category:
- トップス / アウター: `着丈`, `肩幅`, `身幅`, `袖丈`
- ボトムス: `ウエスト`, `股上`, `渡り`
- シューズ / バッグ / アクセサリー: leave `dimensions` as `{}`

## Architecture

Two files only:
- `clothes.json` — array of all items; source of truth
- `index.html` — self-contained static page; fetches `clothes.json` at runtime and renders a filterable table + image gallery with no build step or dependencies

The page is deployed via GitHub Pages (no CI needed — push to `main` publishes automatically).
