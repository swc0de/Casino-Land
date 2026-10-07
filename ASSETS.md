# Assets and licences

Neon Royale ships almost no asset files. Cards, chips, felts, the roulette wheel, neon
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
| `Monoton-Regular.ttf` | Monoton | Marquee titles | © 2011 Vernon Adams. Reserved Font Name "Monoton" | OFL 1.1 (`OFL-monoton.txt`) | [google/fonts/ofl/monoton](https://github.com/google/fonts/tree/main/ofl/monoton) |
| `Bungee-Regular.ttf` | Bungee | Headings, numbers, buttons | © 2023 The Bungee Project Authors | OFL 1.1 (`OFL-bungee.txt`) | [google/fonts/ofl/bungee](https://github.com/google/fonts/tree/main/ofl/bungee) |
| `Rajdhani-Medium.ttf`, `Rajdhani-SemiBold.ttf`, `Rajdhani-Bold.ttf` | Rajdhani | Body text | © 2014 Indian Type Foundry | OFL 1.1 (`OFL-rajdhani.txt`) | [google/fonts/ofl/rajdhani](https://github.com/google/fonts/tree/main/ofl/rajdhani) |

The OFL allows bundling and redistributing the fonts with software. Because Monoton has a
Reserved Font Name, any modified version of that font would have to be renamed; the game
uses it unmodified.

## Generated in code

| What | Where |
|---|---|
| Playing cards (faces, pips, original geometric court-card art, backs) | `src/neon_royale/ui/render/` |
| Casino chips, felts, table layouts, roulette wheel | `src/neon_royale/ui/render/` |
| Neon glow, marquee bulbs, particles | `src/neon_royale/ui/fx/` |
| Sound effects and ambience | `src/neon_royale/audio/` |

Code-generated assets are part of this project's source and carry no third-party licence.
