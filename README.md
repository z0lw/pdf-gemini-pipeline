## PDF → Yomitoku → Gemini パイプライン

左右に分割した PDF を Yomitoku で HTML 化し、その HTML と PDF を Gemini（`models/gemini-2.5-flash`）へ送って JSON を取得する自動処理です。`.env` を整えたら `python pipeline.py` だけで完結します。

### 必要環境
- Python 3.11+
- Yomitoku CLI（GPU 対応推奨）
- CUDA 対応 GPU（例: RTX 5080）※CPU でも可
- Google Gemini API キー

#### Yomitoku の導入手順（例）
```powershell
git clone https://github.com/kotaro-kinoshita/yomitoku.git
cd yomitoku
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
```
上記で生成される `yomitoku\.venv\Scripts\yomitoku.exe` へのパスを `.env` の `YOMITOKU_CMD` に設定してください。

### セットアップ
```powershell
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` で指定する主な値

| 変数名 | 説明 |
|--------|------|
| `GEMINI_API_KEY` | Gemini API キー |
| `PDF_INPUT_DIR` | PDF を置くフォルダ（既定 `.\input_pdfs`） |
| `PDF_INPUT` | 単一 PDF を処理したい時だけ指定（任意） |
| `PROMPT_PATH` | Gemini に渡すプロンプト。`prompt.md` を同梱済み |
| `OUTPUT_DIR` | HTML / JSON を保存するフォルダ（既定 `.\outputs`） |
| `YOMITOKU_CMD` | `yomitoku` 実行ファイルへのパス |
| `DEVICE` | `cuda` / `cpu`（既定 `cuda`） |
| `GEMINI_MODEL` | 既定 `models/gemini-2.5-flash` |

API キーなどの秘密情報は必ず `.env` に書き、OS の環境変数へは設定しません。

### PDF の置き場所
`input_pdfs/` フォルダを用意済みです。この中に処理したい PDF を入れてください。`PDF_INPUT_DIR` を変更すれば別フォルダも利用できます。左右分割後の PDF/PNG と Gemini の JSON は `outputs/<元PDF名>/` 以下にまとまります。

### 実行
通常は `.env` の設定だけで OK:
```powershell
python pipeline.py
```

個別に上書きしたい場合のみ引数を付与します。
```powershell
python pipeline.py --pdf ".\input_pdfs\sample.pdf" --device cpu
```

### 出力構成
`outputs/<元PDF名>/` に以下を生成します。

- `pdf_pages/` … 左右それぞれの PDF/PNG
- `pXX_l`, `pXX_r` … 各半ページの Yomitoku HTML
- `<元PDF名>_pXX_{l|r}.json` … Gemini 応答（JSON 整形済み）

### 備考
- `prompt.md` に既定のプロンプトを同梱しました。内容を編集すればそのまま反映されます。
- GPU が使えない環境では `.env` の `DEVICE` を `cpu` に変更してください。
- 実行ログには `[DONE] <PDF名> -> pXX_{l|r}` が出力され、失敗時は例外メッセージをそのまま表示します。
