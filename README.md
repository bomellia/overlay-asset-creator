# プロジェクト構成メモ
アセット生成ツールです。
toolsフォルダ内のiniを好きに書き換えて(必要に応じてフォントファイルを用意して)、
build_assets.exeを実行して、
生成されたoutput/assetsフォルダとdependenciesフォルダをoverlay側の同名フォルダと差し替えて使います。
dependenciesにはジャケット生成のexeが入ってますが、依存ファイルごと差し替える必要があるのでdependencies丸々変えてください。

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
