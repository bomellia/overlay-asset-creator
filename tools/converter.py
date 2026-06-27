import os
import io
import sys
from pathlib import Path
from PIL import Image, ImageFile, ImageOps, ImageChops



class AssetsBase:
    def __init__(self):
        pass
    
    def _load(self, base_path, file_name) -> ImageFile.ImageFile:
        path = os.path.join(base_path, file_name)
        img = Image.open(path)
        if img is None:
            raise FileNotFoundError()
        return img


class RPrismBgAssets(AssetsBase):
    REQUIRED_FILES = (
        "base.png",
        "center_cover.png",
        "center_mask.png",
        "side_cover.png",
        "side_mask.png",
    )

    def __init__(self, base_path):
        super().__init__()
        self.base =         self._load(base_path, "base.png")
        self.center_cover = self._load(base_path, "center_cover.png")
        self.center_mask =  self._load(base_path, "center_mask.png")
        self.side_cover =   self._load(base_path, "side_cover.png")
        self.side_mask =    self._load(base_path, "side_mask.png")



def application_dir() -> Path:
    """Return the directory containing the executable (or this source file)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_assets_dir() -> Path:
    candidates: list[Path] = []
    env_assets = os.environ.get("RPRISM_BG_ASSETS_DIR")
    if env_assets:
        candidates.append(Path(env_assets))

    exe_dir = application_dir()
    candidates.extend(
        [
            exe_dir / ".." / "assets" / "original",
            exe_dir / "assets" / "original",
            Path.cwd() / "assets" / "original",
            Path.cwd() / ".." / "assets" / "original",
        ]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if all((resolved / name).is_file() for name in RPrismBgAssets.REQUIRED_FILES):
            return resolved
    return (exe_dir / "assets" / "original").resolve()


RPRISM_ASSETS_DIR = find_assets_dir()
_RPRISM_ASSETS = None


def get_rprism_assets() -> RPrismBgAssets:
    """Load assets on first use so callers receive a useful runtime error."""
    global _RPRISM_ASSETS
    if _RPRISM_ASSETS is None:
        try:
            _RPRISM_ASSETS = RPrismBgAssets(RPRISM_ASSETS_DIR)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"変換素材が見つかりません: {RPRISM_ASSETS_DIR}\n"
                "実行ファイルと同じ場所に assets/original を配置してください。"
            ) from exc
    return _RPRISM_ASSETS

def conv_jacket(jacket: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(jacket))
    
    # アスペクト比を保ったまま、長い方の辺を500pxにする
    img.thumbnail(
        size=(500, 500),
        resample=Image.Resampling.LANCZOS
    )
    
    # 500px × 500pxの黒でパディングする
    img = ImageOps.pad(
        image=img, 
        size=(500, 500),
        method=Image.Resampling.LANCZOS,
        color=(0, 0, 0)
    )
    
    # RGB
    img = img.convert("RGB")
    
    return img

def crop(img: Image.Image, x, y, w, h) -> Image.Image:
    return img.crop((x, y, x+w, y+h))

def gen_orig_background(jacket: Image.Image) -> Image.Image:
    # ジャケットのリサイズ、切り出し
    jacket = jacket.copy().resize((510, 510))
    jacket_l = crop(jacket.copy(), 50, 120, 188, 125)
    jacket_r = crop(jacket.copy(), 300, 220, 188, 125)
    
    # 元のオブジェクトを書き換えないようにコピー
    assets = get_rprism_assets()
    base = assets.base.copy()
    center_c = assets.center_cover.copy()
    center_m = assets.center_mask.copy()
    side_c = assets.side_cover.copy()
    side_m = assets.side_mask.copy()
    
    # カバーの透明度を調整
    center_c.putalpha(center_c.getchannel("A").point(lambda x: int(x * 0.4)))
    side_c.putalpha(side_c.getchannel("A").point(lambda x: int(x * 0.4)))
    
    # 透明なImageの上にジャケットを貼り付ける
    center_jacket_layer = Image.new("RGBA", center_m.size, (0, 0, 0, 0))
    center_jacket_layer.paste(jacket, (769, 225))
    center_jacket_layer.paste(ImageOps.flip(jacket), (770, 929))
    
    side_jacket_layer = Image.new("RGBA", side_m.size, (0, 0, 0, 0))
    side_jacket_layer.paste(jacket_l, (514, 257))
    side_jacket_layer.paste(jacket_r, (1346, 513))
    side_jacket_layer.paste(ImageOps.flip(jacket_r), (1346, 747))

    # 下にあるものからペーストしていく
    base.paste(center_jacket_layer, center_m)
    base.paste(side_jacket_layer, side_m)
    base.paste(center_c, center_c)
    base.paste(side_c, side_c)
    
    jacket.close()
    jacket_l.close()
    jacket_r.close()
    center_jacket_layer.close()
    side_jacket_layer.close()
    center_c.close()
    center_m.close()
    side_c.close()
    side_m.close()
    
    return base
