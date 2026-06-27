# プロジェクト構成メモ
アセット生成ツールです。
build_assets.exeを実行して、
生成されたoutput/assetsフォルダとdependenciesフォルダをoverlay側の同名フォルダと差し替えて使います。
dependenciesにはジャケット生成のexeが入ってますが、依存ファイルごと差し替える必要があるのでdependencies丸々変えてください。

## 全体の処理の流れ

1. 起動時にバージョン、Windows ロケール、日本語言語パック、作業ディレクトリ、`default.ini` の値を確認する。
2. AviUtl または AviUtl ExEdit2 を検出し、必要に応じてスクリプト・オブジェクト・設定をインストールする。
3. ユーザーが入力した譜面 ID から Sonolus サーバーを判定する。
4. 譜面メタ情報、ジャケット画像、背景画像、譜面データを取得する。
5. 譜面データからスコア推移、コンボ、ライフ、スキル発動タイミングを計算する。
6. `cover.png`、`background.png`、`background-v1.png`、`data.ped`、`.exo` または `.object` を `dist/<chartId>` 相当の出力先に生成する。
7. 生成されたファイルを AviUtl / ExEdit2 に読み込むことで動画編集用のプロジェクトとして使える。

## ルート直下

| パス | 役割 |
| --- | --- |
| `main.go` | CLI のエントリーポイントです。フラグ定義、更新確認、前提条件チェック、AviUtl 検出、譜面 ID 入力、譜面取得、背景生成、スコア計算、`data.ped` と `.exo` / `.object` 生成までの全体フローを制御します。 |
| `console.go` | 起動時タイトル、ANSI/RGB カラー出力用の補助関数を定義します。 |
| `tips.go` | 起動中にランダム表示される Tips 文言を保持します。日本語・英語ペアの Tips をランダムに選んで表示します。 |
| `default.ini` | ユーザーが編集できる既定設定です。オフセット、キャッシュ、テキスト言語、ウォーターマーク、ライフ、スコア、コンボ、スキル、判定表示などの初期値を持ちます。 |
| `README.md` | ツール概要、利用条件、必要環境、使い方への導線、謝辞をまとめたメイン README です。日本語部分は現状 mojibake しています。 |
| `LICENSE` | GPL 系ライセンス本文です。 |
| `go.mod` | Go モジュール定義です。モジュール名、Go/toolchain バージョン、依存パッケージを定義します。 |
| `go.sum` | Go 依存パッケージのチェックサムです。 |
| `.gitignore` | ビルド成果物、配布用出力、`dist/`、`default-override.ini`、AviUtl プロジェクト出力などを Git 管理から除外します。 |
| `.gitattributes` | Go ファイルの改行を LF に固定する設定です。 |
| `PROJECT_STRUCTURE_JA.md` | このドキュメントです。 |

## Go パッケージ

### `pkg/sonolus`

Sonolus API の JSON を Go の構造体として扱うための薄いモデル層です。

| パス | 役割 |
| --- | --- |
| `pkg/sonolus/http.go` | `LevelInfo`、`SRL`、`EngineInfo`、`TagInfo` など Sonolus のレベル情報レスポンスを表す構造体を定義します。相対 URL と絶対 URL を扱う `JoinUrl` もここにあります。 |
| `pkg/sonolus/levelData.go` | 譜面本体データの構造体を定義します。`LevelData` は `bgmOffset` と `entities` を持ち、各 entity の archetype とデータ値を保持します。 |

### `pkg/pjsekaioverlay`

このツールの実処理を持つ中核パッケージです。

| パス | 役割 |
| --- | --- |
| `pkg/pjsekaioverlay/chart.go` | 譜面取得まわりを担当します。対応サーバー判定、ScoreSync ローカルサーバー検出、Sonolus からの譜面情報・譜面データ取得、ジャケット取得、背景取得またはローカル背景生成、背景生成 exe のダウンロードを行います。 |
| `pkg/pjsekaioverlay/ped.go` | 譜面データからスコア・コンボ・ライフ・スキルイベントを計算し、AviUtl 側のスクリプトが読む `data.ped` を生成します。ノーツ種別ごとの重み、全ノーツ flick 扱い、BPM 変化からの時刻計算、スキル補正、ランクバー位置計算もここにあります。 |
| `pkg/pjsekaioverlay/installCheck.go` | Windows / AviUtl 環境へのインストール補助を担当します。実行中の AviUtl 検出、`.obj` / `.obj2` のインストール、AviUtl 設定の最大解像度変更、依存スクリプトコピー、フォント検出、ExEdit2 英語言語ファイル取得、禁止リスト照合を行います。 |
| `pkg/pjsekaioverlay/exo-alias.go` | 埋め込みテンプレートから AviUtl 用 `.exo` と ExEdit2 用 `.object` を生成します。譜面タイトル、説明文、難易度、画像パス、各種 UI 設定値をプレースホルダーに流し込みます。`.exo` は Shift_JIS にエンコードして出力します。 |
| `pkg/pjsekaioverlay/version.go` | アプリケーションのバージョン定数を定義します。現在は `0.0.0` です。 |
| `pkg/pjsekaioverlay/default.ini` | `go:embed` される既定設定です。実行ファイル付近に設定ファイルがない場合、これを元に `default.ini` が生成されます。 |

### 埋め込みテンプレート・スクリプト

| パス | 役割 |
| --- | --- |
| `pkg/pjsekaioverlay/main_jp_16-9_1920x1080.exo` | AviUtl 旧環境向け、v3 UI、日本語、16:9 用のベース `.exo` テンプレートです。 |
| `pkg/pjsekaioverlay/main_jp_4-3_1440x1080.exo` | AviUtl 旧環境向け、v3 UI、日本語、4:3 用のベース `.exo` テンプレートです。 |
| `pkg/pjsekaioverlay/main_en_16-9_1920x1080.exo` | AviUtl 旧環境向け、v3 UI、英語、16:9 用のベース `.exo` テンプレートです。 |
| `pkg/pjsekaioverlay/main_en_4-3_1440x1080.exo` | AviUtl 旧環境向け、v3 UI、英語、4:3 用のベース `.exo` テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin_jp_16-9_1920x1080.exo` | AviUtl 旧環境向け、v1 スキン、日本語、16:9 用テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin_jp_4-3_1440x1080.exo` | AviUtl 旧環境向け、v1 スキン、日本語、4:3 用テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin_en_16-9_1920x1080.exo` | AviUtl 旧環境向け、v1 スキン、英語、16:9 用テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin_en_4-3_1440x1080.exo` | AviUtl 旧環境向け、v1 スキン、英語、4:3 用テンプレートです。 |
| `pkg/pjsekaioverlay/main2_16-9_1920x1080.object` | AviUtl ExEdit2 向け、v3 UI、16:9 用 alias object テンプレートです。 |
| `pkg/pjsekaioverlay/main2_4-3_1440x1080.object` | AviUtl ExEdit2 向け、v3 UI、4:3 用 alias object テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin2_16-9_1920x1080.object` | AviUtl ExEdit2 向け、v1 スキン、16:9 用 alias object テンプレートです。 |
| `pkg/pjsekaioverlay/v1-skin2_4-3_1440x1080.object` | AviUtl ExEdit2 向け、v1 スキン、4:3 用 alias object テンプレートです。 |
| `pkg/pjsekaioverlay/sekai.obj` | AviUtl 旧環境にインストールされる日本語 v3 UI スクリプトです。 |
| `pkg/pjsekaioverlay/sekai-en.obj` | AviUtl 旧環境にインストールされる英語 v3 UI スクリプトです。 |
| `pkg/pjsekaioverlay/sekai-v1.obj` | AviUtl 旧環境にインストールされる日本語 v1 UI スクリプトです。 |
| `pkg/pjsekaioverlay/sekai-v1-en.obj` | AviUtl 旧環境にインストールされる英語 v1 UI スクリプトです。 |
| `pkg/pjsekaioverlay/sekai.obj2` | AviUtl ExEdit2 にインストールされる v3 UI スクリプトです。 |
| `pkg/pjsekaioverlay/sekai-v1.obj2` | AviUtl ExEdit2 にインストールされる v1 UI スクリプトです。 |

## アセット

### `assets`

生成された `.exo` / `.object` と `data.ped` から参照される標準アセット群です。出力プロジェクトの見た目を作る画像・音声が入っています。

| パス | 役割 |
| --- | --- |
| `assets/*.png` | 難易度背景、レーン、ライフ、コンボ、スコア、AutoLive 表示、トーナメント表示など、基本 UI に使う画像です。 |
| `assets/*.mp4` | AP / v1 AP などの短い演出動画です。 |
| `assets/combo/` | コンボ数字・記号・ラベル画像です。通常表示、AP 表示、色違い、接頭辞付き画像などを含みます。 |
| `assets/judge/v1/` | v1 スキン用の判定画像です。 |
| `assets/judge/v3/` | v3 UI 用の判定画像です。 |
| `assets/life/v1/` | v1 ライフ UI の背景、枠、危険表示、オーバーフロー表示、数字画像です。 |
| `assets/life/v3/` | v3 ライフ UI の背景、マスク、危険表示、オーバーフロー表示、数字画像です。 |
| `assets/score/` | スコア UI のバー、背景、数字、ランク表示素材です。 |
| `assets/score/digit/` | スコア表示用の数字・符号・小数点・パーセント画像です。 |
| `assets/score/rank/chr/` | ランク文字そのものの画像です。 |
| `assets/score/rank/txt/en/` | 英語 UI 用のランクテキスト画像です。 |
| `assets/score/rank/txt/jp/` | 日本語 UI 用のランクテキスト画像です。 |
| `assets/skill/` | スキル演出用の音声、カットイン、バー、アイコン、数字、プロフィール画像などです。 |
| `assets/skill/profile/README.md` | スキルプロフィール画像に関する補足 README です。 |

### `extra-assets`

本体生成に必須ではない追加素材・参考素材です。README でも追加素材として案内されています。

| パス | 役割 |
| --- | --- |
| `extra-assets/ap-fc-clear-fail/` | AP、FC、LC、FAIL、FINISH などのリザルト・クリア演出動画です。16:9 / 4:3、v1、英語版のバリエーションがあります。 |
| `extra-assets/auto_anim/` | Auto 表示の追加アニメーション素材です。 |
| `extra-assets/button/` | skip / stop ボタン画像です。 |
| `extra-assets/clear_status/` | Normal / Append の clear、fail、FC、AP 状態アイコンです。 |
| `extra-assets/difficulty/` | 難易度色、難易度一覧 GIF、背景画像などです。 |
| `extra-assets/fever/` | Fever / Super Fever の演出動画、フレーム、ゲージ素材です。 |
| `extra-assets/judgement/` | 判定テキスト画像と v1 差分です。 |
| `extra-assets/judgement/custom/` | Colorfully Sekai / Neo Sekai 系のカスタム判定フォント画像セットです。 |
| `extra-assets/lane/` | レーン、判定ライン、レーン発光動画、Blender プロジェクトとテクスチャです。 |
| `extra-assets/lane/lane_blender/` | レーン素材作成用の `.blend` プロジェクト、参照画像、テクスチャです。 |
| `extra-assets/note_se/01/` | ノーツ SE セット 01 です。tap、flick、long、trace、critical、perfect/great/good などの音声が入っています。 |
| `extra-assets/note_se/02/` | ノーツ SE セット 02 です。構成は 01 と近い別バリエーションです。 |
| `extra-assets/skill/` | スキル UI、スキル SE、スキル文言画像などの追加素材です。 |
| `extra-assets/tournament/` | トーナメントモード用のトロフィーやラベル背景です。 |
| `extra-assets/tutorial/` | ライブチュートリアル動画素材です。 |
| `extra-assets/tex_jacket_empty_740.png` | 空ジャケット用の追加画像素材です。 |

## 依存ファイル

### `dependencies`

AviUtl / ExEdit2 へコピーされるスクリプト、外部ツール、フォント関連の補助情報です。

| パス | 役割 |
| --- | --- |
| `dependencies/pjsekai-background-gen.exe` | ジャケット画像から背景画像を生成する外部実行ファイルです。存在しない場合は `chart.go` が GitHub Releases から取得しようとします。 |
| `dependencies/font/clue.md` | 必要フォントに関するヒント・案内用ファイルです。 |
| `dependencies/aviutl script/` | AviUtl 旧環境向けにコピーされる依存スクリプト群です。 |
| `dependencies/aviutl script/unmult.anm` | 旧 AviUtl 用の透過系アニメーションスクリプトです。 |
| `dependencies/aviutl script/@テキスト自動リサイズ.anm` | 旧 AviUtl 用のテキスト自動リサイズスクリプトです。 |
| `dependencies/aviutl script/ANM_ssd/` | 旧 AviUtl 用の追加 `.anm`、`.obj`、`.tra` スクリプト素材です。 |
| `dependencies/aviutl2/` | AviUtl ExEdit2 向けにコピーされる依存ファイル群です。 |
| `dependencies/aviutl2/style.conf` | ExEdit2 用のスタイル設定ファイルです。 |
| `dependencies/aviutl2/Language/` | ExEdit2 用の言語ファイルです。英語翻訳補助ファイルも含みます。 |
| `dependencies/aviutl2/Script/` | ExEdit2 用のスクリプト群です。 |
| `dependencies/aviutl2/Script/bignumber.lua` | ExEdit2 で非常に大きな数を扱うための Lua ライブラリです。 |
| `dependencies/aviutl2/Script/unmult.anm2` | ExEdit2 用の透過系アニメーションスクリプトです。 |
| `dependencies/aviutl2/Script/ext/` | Lua 拡張ライブラリ一式です。`require`、`table`、`string`、`math`、`io`、`os`、`class` などの補助モジュールを含みます。 |
| `dependencies/aviutl2/Script/ANM_ssd/` | ExEdit2 用の追加 `.anm`、`.obj`、`.tra` スクリプト素材です。 |

## Wiki と GitHub 設定

| パス | 役割 |
| --- | --- |
| `wiki/Home.md` | GitHub Wiki のトップページです。英語の案内と文字化けした日本語セクションがあります。 |
| `wiki/Start-Here!.md` | 英語版の詳細利用ガイドです。必要環境、録画、AviUtl 設定、UI カスタマイズ仕様、よくある問題を扱います。 |
| `wiki/ここから始めよう！.md` | 日本語版 Wiki ページに相当するファイルですが、現状は文字化けを含みます。 |
| `.github/FUNDING.yml` | GitHub Sponsors、Patreon、Ko-fi などの支援先設定です。 |
| `.github/workflows/auto-approve.yml` | Dependabot / GitHub Actions bot の PR を自動承認する GitHub Actions ワークフローです。 |
| `.github/workflows/publish-wiki.yml` | `wiki/**` 変更時に GitHub Wiki へ公開するワークフローです。 |
| `.github/workflows/update-license.yml` | 毎年 1 月 1 日または手動実行で LICENSE / Markdown 内の年表記を更新し、PR を作るワークフローです。 |

## 生成される主な出力

通常実行時は `dist/<chartId>/` 相当のディレクトリに以下のようなファイルが生成されます。

| ファイル | 役割 |
| --- | --- |
| `cover.png` | Sonolus サーバーから取得したジャケット画像を 512x512 にリサイズしたものです。 |
| `background.png` | v3 UI などで使う背景画像です。サーバーから取得する場合と、ジャケットからローカル生成する場合があります。 |
| `background-v1.png` | v1 UI 用の背景画像です。 |
| `data.ped` | AviUtl スクリプトが読む独自データファイルです。アセットパス、言語、バージョン、初期ライフ、時刻ごとのスコア・ランク・コンボ、スキル、ライフ回復イベントが入ります。 |
| `main_*.exo` | AviUtl 旧環境向けの編集プロジェクトです。日本語 / 英語、16:9 / 4:3 のバリエーションがあります。 |
| `v1-skin_*.exo` | AviUtl 旧環境向けの v1 スキン編集プロジェクトです。 |
| `main2_*.object` | AviUtl ExEdit2 向けの alias object です。 |
| `v1-skin2_*.object` | AviUtl ExEdit2 向けの v1 スキン alias object です。 |

## 設定値の読み込み

`SetOverlayDefault()` は実行ファイルのあるディレクトリで以下の順に設定ファイルを探します。

1. `default-override.ini`
2. `default.ini`
3. どちらもなければ、埋め込みの `pkg/pjsekaioverlay/default.ini` から `default.ini` を生成

`main.go` では 25 個の設定値があることを期待しており、範囲外の値がある場合は処理を止めます。

## 注意点

- このプロジェクトは Windows と AviUtl / AviUtl ExEdit2 前提です。
- `main.go` は PowerShell コマンドでシステムロケールと言語パックを確認します。
- 日本語の非 Unicode プログラム設定が必要なため、README でも `Japanese (Japan)` ロケールが要求されています。
- `.exo` や `.obj` は AviUtl 互換性のため Shift_JIS を扱います。
- README、Wiki、コード中の一部日本語文字列は現在のファイル上で文字化けしています。英語併記がある箇所はそこから意味を補えます。
- ネットワークアクセスは譜面取得、背景・ジャケット取得、更新確認、背景生成 exe 取得、ExEdit2 英語言語ファイル取得、禁止リスト照合で使われます。
