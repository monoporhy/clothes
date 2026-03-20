# 服カタログ

手持ちの服を管理・公開する個人リファレンスサイト。

**公開URL**: https://monoporhy.github.io/clothes/

**主な用途**: 買い物時に「似たものを持っていないか・サイズは合うか」を確認する。

---

## 構成

```
clothes/
├── index.html     # 公開ページ（テーブル＋画像ギャラリー）
└── clothes.json   # 服データ
```

## アイテム追加方法

Claude Code に以下の3点を渡す:

1. **商品ページのURL**
2. **購入したサイズ**（例: M、L、38）
3. **カラー**（例: ホワイト、ブラック）

Claude Code がページから情報を取得して `clothes.json` に追記し、自動でpushする。

## データ形式

```json
{
  "id": "brand-color-size-yyyy-mm",
  "category": "トップス",
  "brand": "ブランド名",
  "name": "商品名",
  "color": "カラー",
  "size": "サイズ",
  "dimensions": { "着丈": 69, "肩幅": 44, "身幅": 52, "袖丈": 20 },
  "url": "https://...",
  "image": "https://...（og:image URL）",
  "purchased_at": "2026-03"
}
```

カテゴリ: `トップス` / `ボトムス` / `アウター` / `シューズ` / `バッグ` / `アクセサリー` / `その他`
