# Assets and licences

Neon Royale ships almost no asset files. Cards, chips, felts, the roulette wheel, wood,
signs, marquee lights, particles and **every sound effect** are generated in code at
runtime (pygame drawing and numpy synthesis). The only third-party files are the fonts
below.

No casino brands, logos or trademarks are used. "Neon Royale" is a made-up name.

## Fonts

All fonts are unmodified files from the [Google Fonts repository](https://github.com/google/fonts)
and are licensed under the **SIL Open Font License 1.1**. Each font's full licence text is
bundled next to it in `src/neon_royale/assets/fonts/`.

| File | Family | Used for | Copyright | Licence | Source |
|---|---|---|---|---|---|
| `CinzelDecorative-Black.ttf`, `CinzelDecorative-Bold.ttf` | Cinzel Decorative | The casino's name, table titles | © 2012 Natanael Gama. Reserved Font Name "Cinzel" | OFL 1.1 (`OFL-cinzeldecorative.txt`) | [google/fonts/ofl/cinzeldecorative](https://github.com/google/fonts/tree/main/ofl/cinzeldecorative) |
| `PlayfairDisplaySC-Bold.ttf`, `PlayfairDisplaySC-Black.ttf` | Playfair Display SC | Headings, buttons, banners | © 2017 The Playfair Display Project Authors. Reserved Font Name "Playfair Display" | OFL 1.1 (`OFL-playfairdisplaysc.txt`) | [google/fonts/ofl/playfairdisplaysc](https://github.com/google/fonts/tree/main/ofl/playfairdisplaysc) |
| `Lato-Regular.ttf`, `Lato-Bold.ttf`, `Lato-Black.ttf` | Lato | Body text and all numbers (lining figures) | © 2010-2014 Łukasz Dziedzic. Reserved Font Name "Lato" | OFL 1.1 (`OFL-lato.txt`) | [google/fonts/ofl/lato](https://github.com/google/fonts/tree/main/ofl/lato) |

The OFL allows bundling and redistributing the fonts with software. All three families have
Reserved Font Names, so modified versions would have to be renamed; the game uses them
unmodified.

## Generated in code

| What | Where |
|---|---|
| Playing cards (faces, pips, original geometric court-card art, backs) | `src/neon_royale/ui/render/` |
| Casino chips, felts, table layouts, roulette wheel | `src/neon_royale/ui/render/` |
| Wood, leather, velvet, carpet, brass plaques, gold lettering, light pools | `src/neon_royale/ui/render/decor.py` |
| Marquee bulbs, glow helpers, particles | `src/neon_royale/ui/fx/` |
| Sound effects and ambience | `src/neon_royale/audio/` |

Code-generated assets are part of this project's source and carry no third-party licence.

## Screenshots

`docs/screenshots/*.jpg` are captures of the game itself, produced by
`tools/screenshots.py`. They contain only the fonts and generated art listed above.
