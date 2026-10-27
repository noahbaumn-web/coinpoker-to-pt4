# coinpoker-to-pt4

Free, open-source Python script that converts **CoinPoker** hand histories into **PokerStars format**, so they can be imported into **PokerTracker 4**.

CoinPoker exports are close to the PokerStars format, but not close enough: PT4 rejects or miscounts many hands (currency symbol, all-ins, straddles, side pots...). Existing converters are paid and Windows-only. This one is free, runs anywhere Python runs (macOS included), and has no dependencies.

## Usage

```bash
python3 coinpoker_to_pt4.py CoinPoker_export.txt
```

This creates `CoinPoker_export_PT4.txt` in the current folder. Import that file into PokerTracker 4.

Requires Python 3.8+. No packages to install.

## What it converts

| CoinPoker | PokerStars (PT4) |
|---|---|
| `Hand #X: NLH (₮0.02/₮0.05)` | `PokerStars Hand #X: Hold'em No Limit ($0.02/$0.05)` |
| `₮` symbol | `$` |
| `PLAYER: RETURN ₮X` | `Uncalled bet ($X) returned to PLAYER` |
| `PLAYER: ALLIN ₮X` | `bets / raises / calls ... and is all-in`, with correct totals |
| `PLAYER: STRADDLE ₮X` (after HOLE CARDS) | `PLAYER: posts big blind $X` (moved before HOLE CARDS) |
| `SPLASH dropped ₮X` | Removed, total pot adjusted |
| Run-it-twice (`FIRST` / `SECOND` boards) | Only the first board is kept |
| Several `collected` lines for one player (side pots) | Merged into one line with the total |
| `Game ended:`, `Board []`, `Hand was run once` | Removed |

## Limitations

- **No Limit Hold'em cash games only.** Tournaments and other variants are not supported.
- Expects headers in the form `Hand #...: NLH (₮.../₮...)`. Hands with another header format (e.g. `CoinPoker Hand #`) are skipped, not converted.
- **Bomb pots** are not supported.
- Run-it-twice hands keep only the first board, so results for those hands are approximate.
- Tested on real exports from spring 2026 (2,000+ hands imported into PT4 without errors). CoinPoker may change its export format at any time.

If PT4 rejects a hand, please open an issue with the hand ID and the error message (remove other players' names if you want).

## License

MIT
