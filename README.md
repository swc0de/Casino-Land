# Neon Royale Casino

A single-player desktop casino in the style of a classic high-roller room: **Roulette,
Blackjack and Texas Hold'em** on green baize, under warm light, with mahogany rails, padded
leather, brass and gold leaf. Built with Python and pygame-ce. Every card, chip, light and sound is
generated in code.

> **Play money only.** Neon Royale uses virtual chips with no cash value. There are no
> purchases, no real-money features and nothing to win.

![Lobby](docs/screenshots/lobby.jpg)

| Roulette | Blackjack | Hold'em |
|---|---|---|
| ![Roulette](docs/screenshots/roulette.jpg) | ![Blackjack](docs/screenshots/blackjack.jpg) | ![Hold'em](docs/screenshots/poker.jpg) |

## Features

- **Entrance:** a lacquered sign edged in gold and ringed with chasing Vegas marquee bulbs,
  hung on red velvet, with the name in gold-leaf Roman capitals.
- **Casino floor:** the lobby is the room seen from above: roulette, blackjack and poker
  tables with their chairs, under pendant lights on ornate casino carpet, each with a
  brass name plate. Broke? Claim free chips from the house.
- **Three complete games** with casino-standard rules (below), animated dealing, chip
  movement, payouts, and big-win celebrations (fanfare, confetti, bulb frenzy).
- **Procedural art:** all 52 cards (original art-deco court cards, classic red backs),
  casino chips from 50¢ to $25K stacked in 2.5D, a numbered roulette wheel, wood grain,
  padded leather, velvet, carpet, brass plaques and engraved gold lettering. No image
  files.
- **Procedural sound:** chip clacks, card snaps, a riffle shuffle, wheel rumble, ball
  ticks, win jingles, a big-win fanfare and a casino-floor ambience loop, all synthesised
  with numpy at start-up in a background thread.
- **Settings** (volumes, fullscreen, fast animations, FPS overlay, bankroll reset),
  **lifetime stats** per game, and an in-game **rules panel** for each table (`F1` or `?`).
- **Smooth:** every screen costs 1-5 ms per frame on a 2.1 GHz server core (budget at
  60 FPS is 16.7 ms); bots think in 3 ms slices so the table never stutters.

## Roulette

European single-zero wheel (house edge 2.70% on every bet).

| Bet | Covers | Pays |
|---|---|---|
| Straight | 1 number (including 0) | 35:1 |
| Split | 2 adjacent numbers (including 0-1, 0-2, 0-3) | 17:1 |
| Street | a row of 3 | 11:1 |
| Trio | 0-1-2 or 0-2-3 | 11:1 |
| Corner | 4 numbers meeting at a corner | 8:1 |
| First four | 0-1-2-3 | 8:1 |
| Six line | two adjacent streets | 5:1 |
| Dozen, Column | 12 numbers | 2:1 |
| Red/Black, Odd/Even, 1-18/19-36 | 18 numbers | 1:1 |

Table limits: $1 minimum per bet, $5,000 total on the layout per spin. Zero loses all
outside bets (no *la partage*). After each spin the layout is cleared and winnings are
paid to your bankroll; **REBET** repeats your last bets.

Click a number, line or corner to bet the selected chip there; right-click a bet to take
it back. Keys: `1`-`6` pick a chip, `Space` spin, `Backspace` undo, `C` clear,
`D` double, `R` rebet.

The winning number is drawn by the rules engine before the wheel moves; the ball's path
is then built backwards so it always drops into that pocket.

## Blackjack

Six-deck shoe, Las Vegas Strip rules:

- Blackjack pays **3:2**. Bets $5 to $5,000 in whole dollars.
- Dealer **stands on all 17s** and **peeks** for blackjack with an ace or ten showing, so
  you never lose a double or split to a dealer natural.
- **Insurance** (up to half your bet) pays 2:1 when the dealer shows an ace; with a
  blackjack it's offered as **even money**.
- **Double** on any first two cards, including after a split.
- **Split** any two cards of equal value (so K-Q counts as a pair), up to four hands. Split
  aces get one card each and can't be re-split; 21 after a split is not a blackjack.
- **Late surrender** on your first two cards (half your bet back).
- The shoe is reshuffled when the cut card (about 75% in) comes out.

Click the betting circle to add the selected chip (right-click removes one). Your last
bet stays in the circle for the next hand. Keys: `Space`/`Enter` deal, `H` hit,
`S` stand, `D` double, `P` split, `R` surrender, `I`/`N` insurance yes/no. **HINT**
shows the basic-strategy play for these exact rules.

## Texas Hold'em

No-Limit Hold'em, six seats: you and five computer players. Blinds $5/$10, no rake.

- **Buy in** for $400 to $2,000 (40 to 200 big blinds) from your bankroll; **ADD CHIPS**
  between hands; **LOBBY** cashes your stack back into your bankroll (if a hand is
  running you fold and leave when it ends).
- Standard cash-game rules: the button moves every hand; heads-up the button posts the
  small blind and acts first before the flop. The minimum bet is the big blind and a raise
  must be at least the previous raise. An all-in for less than a full raise doesn't
  reopen the betting for players who already acted. Uncalled bets are returned, side
  pots are built for every all-in, and split pots give the odd $1 chip to the first
  winner clockwise from the button.
- The bots have personalities you can read on their nameplates (Rock, Shark, Maniac,
  Calling station, Solid). Before the flop they rate hands with the Chen formula; after
  it they estimate their winning chances by Monte Carlo simulation and weigh them
  against the pot odds, with a dash of bluffing. Busted bots are replaced by new ones.

Keys: `F` fold, `C` check/call, `R` bet/raise, mouse wheel adjusts the raise, `Space`
skips the pause between hands.

## Install and run

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
neon-royale                        # or: python -m neon_royale
```

Useful options:

| Option | Effect |
|---|---|
| `--fullscreen` / `--windowed` | Override the saved display setting |
| `--mute` | Start with audio off |
| `--scene lobby` | Jump straight to a screen |
| `--seed 42` | Repeatable shuffles and spins |
| `--save PATH` | Use a different profile file |
| `--smoke 5 --screenshot shot.png` | Run for 5 seconds, save the last frame, exit (launch check) |

## Controls

| Key | Action |
|---|---|
| Mouse | Everything: place chips, press buttons, pick tables |
| `Esc` | Back (table → lobby → title) |
| `F1` | Rules and keys for the current table |
| `M` | Mute / unmute |
| `F11` | Toggle fullscreen |
| `F3` | Frame-rate overlay |
| `1` `2` `3` | Pick a table from the lobby (`S` stats, `O` settings) |

Each game's own keys are listed in its section above and in its `F1` panel.

## Your bankroll

You start with **$10,000** in play chips. Your balance, lifetime stats and settings are
saved automatically to:

- Linux: `~/.local/share/neon-royale/save.json`
- macOS: `~/Library/Application Support/neon-royale/save.json`
- Windows: `%APPDATA%\neon-royale\save.json`

Set `NEON_ROYALE_SAVE` to use another path. If you go broke, the house gives you a free
$1,000 to keep playing. **STATS** in the lobby shows rounds, money wagered and won back,
and your biggest win for each game; **SETTINGS** can reset your bankroll to $10,000.

Closing the window never loses chips on a table: unspun roulette bets are refunded (a
ball already spinning pays out its result), an unfinished blackjack hand is voided and
its stakes returned, and a poker hand in progress is voided and your stack cashed out.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests tools && ruff format --check src tests tools
pytest                    # everything, including slow exhaustive checks
pytest -m "not slow"      # quick run
python -m neon_royale --smoke 3 --mute
python tools/screenshots.py   # regenerate docs/screenshots
```

Tests run headless (SDL dummy video and audio drivers), so no display is needed. Some
checks worth knowing about:

- **Roulette:** every bet on the layout has an exact expected value of −1/37, and every
  chip spot on the board hit-tests back to its own bet.
- **Blackjack:** stacked-shoe scenarios cover every rule; a 20,000-round basic-strategy
  simulation checks that money is conserved and the edge is realistic.
- **Poker:** the evaluator matches the textbook category counts over all 2,598,960
  five-card hands and brute force on random seven-card hands; engine tests cover blinds,
  minimum raises, short all-ins, side pots, odd chips and chip conservation.
- **Screens:** each scene is played headless through full rounds.

### Layout

```
src/neon_royale/
  core/      Rules and state. Pure Python, never imports pygame (a test enforces this).
  ui/        pygame presentation: app loop, scenes, widgets, effects, procedural art.
  audio/     numpy sound synthesis.
  assets/    Bundled OFL fonts.
tests/
tools/       Developer scripts (screenshot generator).
docs/        README screenshots (generated by tools/screenshots.py).
```

Each game engine is a state machine that the screen drives with player actions and that
reports what happened as events. The screen animates those events; it never decides
outcomes. That keeps every rule testable without a window.

Money is stored as integer cents, so fractional payouts (3:2 on a $15 blackjack is
$22.50) are exact.

## Assets

See [ASSETS.md](ASSETS.md). The only third-party files are SIL OFL fonts from Google Fonts.

## Licence

No licence has been chosen for the game's code yet. The bundled fonts keep their own
OFL licences.
