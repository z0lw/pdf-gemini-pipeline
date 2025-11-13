# 出力フォルダの例

このフォルダは、パイプライン実行後の出力構造の参考例です。

## フォルダ構造

```
outputs/                      # ← 実際の出力先フォルダ
└── 2024/                     # 元PDFのファイル名（拡張子なし）
    ├── pdf_pages/            # 分割されたPDF/PNG画像
    │   ├── 2024_p01_L.pdf    # 1ページ目の左半分（PDF）
    │   ├── 2024_p01_L.png    # 1ページ目の左半分（PNG画像）
    │   ├── 2024_p01_R.pdf    # 1ページ目の右半分（PDF）
    │   └── 2024_p01_R.png    # 1ページ目の右半分（PNG画像）
    ├── p01_l/                # 1ページ目左半分のYomitoku出力
    │   └── output.html       # YomitokuによるHTML（OCR結果）
    ├── p01_r/                # 1ページ目右半分のYomitoku出力
    │   └── output.html       # YomitokuによるHTML（OCR結果）
    ├── 2024_p01_l.json       # 1ページ目左半分のGemini解析結果（JSON）
    └── 2024_p01_r.json       # 1ページ目右半分のGemini解析結果（JSON）
```

## ファイルの説明

### PDFとPNG (`pdf_pages/`)
- 元のPDFを左右に分割した結果
- PDFとPNG（画像）の両方が生成されます
- PNGはYomitokuへの入力として使用されます

### HTML (`pXX_l/`, `pXX_r/`)
- YomitokuによるOCR結果
- HTML形式で文字認識結果が保存されます
- 表構造なども可能な限り再現されます

### JSON (`*_pXX_l.json`, `*_pXX_r.json`)
- Gemini APIによる最終的な解析結果
- 構造化されたJSONデータ
- 自動的に`year`フィールドが追加されます（元PDFのファイル名）

## 実際の出力について

実際に`python pipeline.py`を実行すると、`outputs/`フォルダに同じ構造で結果が保存されます。
このフォルダはあくまで「こういう構造になる」という参考例です。
