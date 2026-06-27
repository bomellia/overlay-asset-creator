# Dot Style Fonts

Fonts in this directory are for generating digit assets with
`tools/replace_digit_assets.py`.

## Installed fonts

- `DotGothic16-Regular.ttf` - pixel/dot Gothic style from Google Fonts.
- `Silkscreen-Regular.ttf` / `Silkscreen-Bold.ttf` - bold pixel style from Google Fonts.
- `PixelifySans-wght.ttf` - variable pixel style from Google Fonts.
- `Handjet-ELGR-ELSH-wght.ttf` - variable display/dot-matrix style from Google Fonts.
- `PressStart2P-Regular.ttf` - wide arcade pixel style; percent is very readable.
- `Jersey10-Regular.ttf`
- `Jersey15-Regular.ttf`
- `Jersey20-Regular.ttf`
- `Jersey25-Regular.ttf`
- `Tiny5-Regular.ttf`
- `Micro5-Regular.ttf`
- `VT323-Regular.ttf` - terminal/CRT style.
- `DSEG7Classic-Bold.ttf`
- `DSEG7Modern-Bold.ttf`
- `DSEG14Classic-Bold.ttf`
- `DSEG14Modern-Bold.ttf`

## Percent-friendly choices

These are the safer choices when `%` must stay readable:

- `PressStart2P-Regular.ttf`
- `Jersey15-Regular.ttf`
- `Jersey20-Regular.ttf`
- `Jersey25-Regular.ttf`
- `Tiny5-Regular.ttf`
- `PixelifySans-wght.ttf`

## Example

Edit `tools\replace_digit_assets.ini`, then run:

```powershell
python main.py
```

DSEG can be useful for score-style segmented digits:

Set these in `tools\replace_digit_assets.ini`:

```ini
score_font = dependencies\font\dot-style\DSEG7Modern-Bold.ttf
combo_font = dependencies\font\dot-style\DSEG14Modern-Bold.ttf
```

## Licenses

The Google Fonts files are distributed under the SIL Open Font License; see
the matching `OFL-*.txt` files.

DSEG is distributed under the SIL Open Font License; see `DSEG-LICENSE.txt`.
