# PJSekai Overlay Asset Tools

このリポジトリには、次の2種類の生成ツールが含まれます。

1. ジャケット画像から背景PNGを作る背景生成ツール
2. フォントとINIから差し替え用UIアセット一式を作るアセット生成ツール

## 環境構築

Python 3.10以上を使用します。

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install Pillow numpy pyinstaller
```

コマンドはリポジトリのルートで実行してください。

## 1. 背景生成

### 入出力仕様

| 項目 | 内容 |
| --- | --- |
| 入力 | PNG、JPEGなどPillowで読めるジャケット画像1枚 |
| 出力 | 入力画像と同じフォルダの`cover.output.png` |
| 上書き | 同名の`cover.output.png`がある場合は上書き |

通常版とRhythm Prism版は同じコマンド形式です。

```powershell
python tools\pjsekai_background_gen.py cover.png -v 3
python tools\rp_background_gen.py cover.png -v 3
```

### 通常版

`tools/pjsekai_background_gen.py`は、ジャケットのぼかし、色抽出、半透明パターンを既存背景へ合成します。

| バージョン | テンプレート | 出力サイズ |
| --- | --- | --- |
| `-v 3` | `assets/background_full.png` | 2048x1168 |
| `-v 1` | `assets/background-v1_full.png` | 2048x1261 |

テンプレートを別の場所に置く場合は`PJSEKAI_BG_ASSETS_DIR`を指定できます。

```powershell
$env:PJSEKAI_BG_ASSETS_DIR = "C:\path\to\assets"
```

### Rhythm Prism版

`tools/rp_background_gen.py`は、Rhythm Prism形式の中央・左右マスクへジャケットを合成します。出力サイズは2048x1168です。

必要なテンプレート:

```text
dependencies/assets/original/base.png
dependencies/assets/original/center_cover.png
dependencies/assets/original/center_mask.png
dependencies/assets/original/side_cover.png
dependencies/assets/original/side_mask.png
```

ソースから実行する場合:

```powershell
$env:RPRISM_BG_ASSETS_DIR = "dependencies\assets\original"
python tools\rp_background_gen.py cover.png -v 3
```

### EXEのビルド

通常版:

```powershell
python -m PyInstaller --noconfirm --clean --onefile `
  --name pjsekai_background_gen `
  tools\pjsekai_background_gen.py
```

Rhythm Prism版:

```powershell
python -m PyInstaller --noconfirm --clean --onefile `
  --name rp_background_gen `
  --paths tools `
  tools\rp_background_gen.py
```

生成されたEXEは`dist/`に入ります。画像テンプレートはEXEへ埋め込まず、次の形で一緒に配置します。

```text
dist/
  pjsekai_background_gen.exe
  rp_background_gen.exe
  assets/
    background_full.png
    background-v1_full.png
    original/
      base.png
      center_cover.png
      center_mask.png
      side_cover.png
      side_mask.png
```

EXEの実行例:

```powershell
dist\pjsekai_background_gen.exe cover.png -v 3
dist\rp_background_gen.exe cover.png -v 3
```

## 2. アセット差し替え

### 入出力仕様

| 項目 | 内容 |
| --- | --- |
| 入力 | `assets/`、フォント、スキンINI |
| 出力 | 既定では`output/assets/` |
| 生成対象 | score、combo、judge/v3、life/v3、rank、AUTO表示 |

元PNGの画像サイズと配置をテンプレートとして使います。入力元の`assets/`は変更しません。

```powershell
python build_assets.py
```

`copy_assets = true`の場合、未編集ファイルも出力先へコピーされるため、生成された`output/assets/`を元の`assets/`と直接置き換えられます。

### INIの指定

1つのINIを1つのスキンとして扱います。新しいスキンは既存INIを複製して作成してください。

```powershell
Copy-Item tools\replace_digit_assets.ini tools\my_skin.ini
python build_assets.py --config tools\my_skin.ini
```

INI同士は継承されません。省略した項目は別のINIではなく、プログラム内の既定値になります。

設定の優先順位:

1. プログラム内の既定値
2. `--config`で指定したINI
3. コマンドライン引数

書き込みなしで確認:

```powershell
python build_assets.py --config tools\my_skin.ini --dry-run
```

### 主なINIセクション

| セクション | 内容 |
| --- | --- |
| `[fonts]` | score、combo、judge、life、UI用フォント |
| `[ui_theme]` | 一括テーマ、分類別テーマ、透明度 |
| `[output]` | 出力先、コピー、元サイズ維持 |
| `[layout]` | 余白、`combo_scale` |
| `[score]` / `[score_shadow]` | スコア数字と背面 |
| `[combo_front]` / `[combo_back]` | APコンボの前面、輪郭、背面 |
| `[combo_non_ap]` | 非APコンボ |
| `[judge]` | 各判定の文字色、輪郭、ブラー |
| `[rank]` | S/A/B/C/Dの色 |
| `[score_ui]` / `[life_ui]` / `[auto_ui]` | UIパネルとゲージ |
| `[life_digit]` | ライフ数字 |

色の書式:

```ini
solid = #RRGGBB
with_alpha = #RRGGBBAA
gradient = #RRGGBB,#RRGGBB,#RRGGBB
```

グラデーションは先頭が上、最後が下です。コメントには`;`を使用します。

### テーマ指定

簡易テーマは全UIへ同じ色を適用します。

```ini
[ui_theme]
ui_theme_mode = simple
ui_theme_color = blue
ui_panel_opacity = 0.62
ui_accent_opacity = 0.92
```

詳細テーマは4分類を個別に変更します。

```ini
[ui_theme]
ui_theme_mode = detailed
score_auto_theme_color = #00e9a3
life_theme_color = #00f050
combo_theme_color = rainbow
judge_theme_color = purple
ui_panel_opacity = 0.62
ui_accent_opacity = 0.92
```

指定可能な名前は`green`、`blue`、`purple`、`cyan`、`pink`、`rainbow`です。`#RRGGBB`も使用できます。

- `score_auto_theme_color`: スコアUIとAUTO表示
- `life_theme_color`: ライフUI
- `combo_theme_color`: コンボ数字、COMBO表示、背面
- `judge_theme_color`: 判定文字の外周ブラー

判定文字本体と輪郭は`[judge]`の固有色を維持し、テーマ色はブラーへ適用されます。

テーマ変換を使わず各セクションの色をそのまま使う場合:

```ini
[ui_theme]
ui_theme_mode = simple
ui_theme_color =
ui_panel_opacity = 1.0
ui_accent_opacity = 1.0
```

### 出力設定

```ini
[output]
output_dir = output\assets
copy_assets = true
stretch_to_original_size = true
dry_run = false

[layout]
x_padding = 3
y_padding = 1
combo_scale = 0.92
```

`combo_scale`はキャンバス寸法を変えず、コンボの前面・背面・COMBO文字を中央基準で縮小します。

### アセット生成EXE

ビルドにはPython、Pillow、PyInstallerが必要ですが、生成されたEXEの実行環境にはPythonやPillowは不要です。

```powershell
.\build_asset_generator.ps1
```

または直接ビルド:

```powershell
python -m PyInstaller --noconfirm --clean --onefile `
  --name build_assets `
  --distpath dist `
  build_assets.py
```

出力:

```text
dist/build_assets.exe
```

リポジトリに同梱されたEXEはそのまま利用できます。再ビルドが必要な場合のみPython環境を用意してください。

EXEにはPythonと画像処理コードだけが含まれます。編集可能なINI、入力アセット、フォントは外部ファイルとして必要です。

```text
project/
  build_assets.exe         # dist内のままでも実行可能
  assets/
  tools/
    replace_digit_assets.ini
  dependencies/
    font/
  output/
```

リポジトリ内の`dist/build_assets.exe`は、1階層上のプロジェクトルートを自動検出します。

```powershell
dist\build_assets.exe
dist\build_assets.exe --config tools\my_skin.ini
dist\build_assets.exe --dry-run
```

## 配布時の注意

コード、フォント、元ゲーム由来画像、背景テンプレートは、それぞれライセンスや再配布条件が異なる場合があります。Gitへ含める前に各素材の利用条件を確認してください。
