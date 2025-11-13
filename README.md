# PDF → Yomitoku → Gemini パイプライン

見開きPDFを左右に分割し、Yomitokuで文字認識してHTML化、そのHTMLとPDFをGemini AIに送ってJSON形式のデータを自動抽出するツールです。

## 📋 何ができるの?

1. PDFを左ページ・右ページに自動分割
2. 各ページをYomitoku（OCRツール）でHTML化
3. GeminiにPDFとHTMLを送って、構造化されたJSONデータを取得
4. すべて自動で一括処理

## 🔧 必要なもの

- **Python 3.11以上**
- **Gemini API キー** ([Google AI Studio](https://aistudio.google.com/app/apikey)で無料取得可能)
- **Yomitoku CLI** (日本語OCRツール)
- **GPU推奨** (なくてもCPUで動作可能、ただし遅い)

## 📦 セットアップ手順

### ステップ1: このリポジトリをクローン

```bash
git clone https://github.com/yourusername/pdf-gemini-pipeline.git
cd pdf-gemini-pipeline
```

### ステップ2: Python環境を作成

```bash
python -m venv .venv
```

**Windowsの場合:**
```powershell
.\.venv\Scripts\activate
```

**Mac/Linuxの場合:**
```bash
source .venv/bin/activate
```

### ステップ3: 必要なライブラリをインストール

```bash
pip install -r requirements.txt
```

### ステップ4: Yomitokuをインストール

別のフォルダでYomitokuをセットアップします:

```bash
# 好きな場所に移動してクローン
git clone https://github.com/kotaro-kinoshita/yomitoku.git
cd yomitoku
python -m venv .venv
```

**Windowsの場合:**
```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**Mac/Linuxの場合:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

インストールが完了したら、`yomitoku`コマンドのパスをメモしておいてください:
- **Windows**: `C:\path\to\yomitoku\.venv\Scripts\yomitoku.exe`
- **Mac/Linux**: `/path/to/yomitoku/.venv/bin/yomitoku`

### ステップ5: 設定ファイルを作成

このリポジトリに戻って、`.env`ファイルを作成します:

```bash
# .env.exampleをコピー
cp .env.example .env
```

**Windowsの場合:**
```powershell
Copy-Item .env.example .env
```

### ステップ6: `.env`ファイルを編集

`.env`ファイルをテキストエディタで開いて、以下を設定してください:

```env
# 必須: Gemini APIキー (https://aistudio.google.com/app/apikey で取得)
GEMINI_API_KEY=YOUR_ACTUAL_API_KEY_HERE

# 必須: Yomitokuのパス (ステップ4でメモしたパス)
YOMITOKU_CMD=C:\path\to\yomitoku\.venv\Scripts\yomitoku.exe

# 以下は基本的にそのままでOK
PDF_INPUT_DIR=.\input_pdfs
PROMPT_PATH=.\prompt.md
OUTPUT_DIR=.\outputs
DEVICE=cuda  # GPUがない場合は cpu に変更
GEMINI_MODEL=models/gemini-2.5-flash
```

**重要:** `GEMINI_API_KEY`と`YOMITOKU_CMD`は必ず実際の値に書き換えてください!

## 🚀 使い方

### 1. PDFを配置

処理したいPDFファイルを `input_pdfs/` フォルダに入れてください。

```
input_pdfs/
  ├── 2024.pdf
  └── 2025.pdf
```

**推奨:** ファイル名にはシンプルな年度情報を使ってください（例: `2024.pdf`, `2025.pdf`）。ファイル名（拡張子を除く）が自動的にJSONの`year`フィールドに設定されるため、後で複数年度のデータを比較しやすくなります。

### 2. 実行

```bash
python pipeline.py
```

### 3. 結果を確認

`outputs/` フォルダに結果が保存されます:

```
outputs/
  └── 2024/
      ├── pdf_pages/           # 分割されたPDF/PNG
      │   ├── 2024_p01_L.pdf
      │   ├── 2024_p01_L.png
      │   ├── 2024_p01_R.pdf
      │   └── 2024_p01_R.png
      ├── p01_l/               # 左ページのYomitoku HTML
      │   └── output.html
      ├── p01_r/               # 右ページのYomitoku HTML
      │   └── output.html
      ├── 2024_p01_l.json      # 左ページのJSON結果
      └── 2024_p01_r.json      # 右ページのJSON結果
```

詳しい出力例は `outputs_example/` フォルダを参照してください。

## 📖 JSONデータについて

各JSONファイルには自動的に`year`フィールドが追加されます:

```json
{
  "year": "2024",
  "data": [
    ...
  ]
}
```

このフィールドには元のPDFファイル名(拡張子を除く)が入るので、複数年度のデータを比較する際に便利です。

## ⚙️ オプション設定

### 単一ファイルだけ処理したい

```bash
python pipeline.py --pdf ".\input_pdfs\sample.pdf"
```

### CPUモードで実行

```bash
python pipeline.py --device cpu
```

### カスタムプロンプトを使う

`prompt.md`ファイルを編集すれば、Geminiへの指示を変更できます。

## 🔍 トラブルシューティング

### `GEMINI_API_KEY must be stored in .env`

→ `.env`ファイルに正しいAPIキーを設定してください

### `No Yomitoku HTML in ...`

→ YomitokuのパスとPython環境が正しいか確認してください

### GPUメモリ不足エラー

→ `.env`の`DEVICE`を`cpu`に変更してください

## 📚 詳細情報

- **プロンプトのカスタマイズ**: [prompt.md](prompt.md)を編集
- **Yomitoku**: https://github.com/kotaro-kinoshita/yomitoku
- **Gemini API**: https://ai.google.dev/

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。
