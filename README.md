# 照射計算アプリ GUI

> **CSV（Shift-JIS）／Excel** からビームカレントを読み込み、  
> しきい値・指数減衰を考慮して **照射時間・生成放射能 (mCi)** を一発計算。  
> Windows 用スタンドアロン **`IrradiationApp.exe`** と、  
> Python ソース実行のどちらでも利用できます。

---

## 主な特長

| 機能 | 説明 |
|------|------|
| **列を自動検出** | 見出しセルに `AI01C01` を含む列を検索し、その直下から読取開始 |
| **同位体切替** | 11C / 18F の減衰定数をワンクリックで切替 |
| **2段階しきい値** | <code>&lt; 0.5</code> をウォームアップ無視、<code>≤ 0.3</code> で照射終了 |
| **CSV & Excel 対応** | Windows 生成の Shift-JIS CSV／`xlsx`／`xls` を自動判定 |
| **インストール不要 EXE** | PyInstaller 1ファイル方式 – 解凍して即実行 |

---

## ダウンロード（Windows）

1. GitHub Releases から最新 **`IrradiationApp.zip`** を取得  
   <https://github.com/**yourname**/irradiation-app/releases>
2. ZIP を展開し **`IrradiationApp.exe`** をダブルクリック  
   *初回 SmartScreen が出たら「詳細情報 › 実行」*
3. **参照…** で CSV/Excel を選択 → 同位体を選択 → **計算実行**  
   結果がウィンドウ中央に表示されます。

---

## Mac / Linux などソースから実行

```bash
git clone https://github.com/**yourname**/irradiation-app.git
cd irradiation-app
python -m venv .venv && source .venv/bin/activate   # 任意
pip install -r requirements.txt
python src/irradiation_app.py

