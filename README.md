# textp2srt – Manual + Text/Text+ Mixed Subtitle Workflow (macOS)

This fork evolves the original TextPlus-only exporter into a lightweight CLI that lets you:

* Capture / write manual subtitle blocks for plain "Text" title clips (which the Resolve API cannot read directly).
* Automatically pull StyledText from Text+ (Fusion) clips.
* Combine both into a single SRT with correct timing.
* Diagnose mismatches, count usable clips, and apply manual text back into Text+ clips if desired.

All user‑facing output is English. The ignore list for transitions still contains Japanese names so filtering works on Japanese installs.

---

## Why this approach?
DaVinci Resolve's scripting API exposes the text content of Text+ (Fusion) clips, but NOT the content of simple "Text" title clips. To still build subtitles quickly:

1. You maintain a manual subtitle text file where each block starts with a leading `>` line.
2. Plain Text clips consume blocks sequentially.
3. Text+ clips use their API text (manual blocks are NOT consumed for those unless the API returns empty).
4. A mixed SRT is generated in timeline order.

Result: You can freely mix Text and Text+ on a track and still export a coherent SRT without retyping Text+ content manually.

---

## Installation
Requires: Python 3 (tested 3.13), DaVinci Resolve (running), Typer.

```bash
pip install typer
```

Place `textp2srt.py` in your project (or keep this repo) and run it while Resolve is open.

---

## Manual subtitle file format

```
>First subtitle line
Optional continuation line
>Second block
>Third block line1
Line2
```

Rules:
* A line beginning with `>` starts a new block (the `>` is removed; leading spaces after it are trimmed).
* Lines until the next `>` (or EOF) belong to that block.
* Empty blocks are discarded.

---

## Typical usage scenarios

1. Rapid drafting while editing
    * Keep a text editor beside Resolve.
    * Use the clipboard watcher to append `>` blocks each time you copy a new subtitle line.
    * Later run `preview` to verify alignment, then `srt` to export.

2. Mixing Text and Text+
    * Use Text+ for stylized lines you want to author directly inside Fusion.
    * Use simple Text for the rest; just supply manual blocks for those.
    * `srt --include-text-plus` merges both sources seamlessly.

3. Cleaning transition noise
    * Transitions / dips / dissolves often appear as short “clips”.
    * Built‑in filtering ignores known names and very short generic segments.
    * Add more patterns with `--extra-ignore` or disable filtering with `--no-ignore-effects`.

4. Quality assurance pass
    * Run `diagnose` to see kept vs ignored items and confirm counts.
    * Run `stats` to quantify how many were ignored as effects vs Text+.

5. Applying manual text back to Text+
    * If you drafted all text manually first, later `apply` can push blocks into sequential Text+ clips (StyledText field).

---

## Commands overview

Run `python src/textp2srt.py --help` for the live help.

| Command | Purpose |
|---------|---------|
| `tracks` | List video track names (use to find your subtitle track name). |
| `watch OUTPUT.txt` | Monitor clipboard; each new distinct clipboard snapshot is appended as a `>` block (first snapshot is skipped to avoid junk). |
| `count TRACK` | Count subtitle candidate clips (plain Text by default; add `--include-text-plus` for Text+). |
| `preview manual.txt TRACK` | Show first 30 (or all with `--all`) manual blocks paired with clip timings. |
| `srt manual.txt out.srt TRACK --include-text-plus` | Generate mixed SRT (manual blocks + Text+ API text). Without the flag you only map manual blocks to plain Text clips. |
| `diagnose manual.txt TRACK` | Show counts and (optionally with `--all`) full lists of kept / ignored / Text+. Hints for mismatches. |
| `stats TRACK` | Summarize raw vs kept vs ignored vs Text+ counts + tail samples. |
| `apply manual.txt TRACK` | Push manual blocks sequentially into Text+ clips' StyledText. |

Shared options:
* `--include-text-plus` – Include Text+ clips in clip collection (for `preview`, `srt`, `diagnose`).
* `--no-ignore-effects` – Turn OFF effect/transition filtering.
* `--extra-ignore PATTERN` – Additional substring(s) to treat as effects (repeatable).
* `--all` – For `preview` / `diagnose` to show all entries.

---

## Example workflow

1. Identify track: `python src/textp2srt.py tracks` → suppose it prints `V4` as your subtitle track name.
2. Start recording manual lines while editing:
    ```bash
    python src/textp2srt.py watch manual.txt
    ```
    Copy each subtitle sentence; watcher appends blocks automatically.
3. Inspect pairing:
    ```bash
    python src/textp2srt.py preview manual.txt V4 --include-text-plus
    ```
4. If counts differ, run diagnostics:
    ```bash
    python src/textp2srt.py diagnose manual.txt V4 --include-text-plus --all
    ```
    Adjust your manual file (merge/split blocks) or tweak ignore patterns.
5. Export SRT:
    ```bash
    python src/textp2srt.py srt manual.txt subtitles.srt V4 --include-text-plus
    ```
6. (Optional) Push manual text into Text+ clips (if you created them blank first):
    ```bash
    python src/textp2srt.py apply manual.txt V4
    ```

---

## Notes on filtering
* Default ignore names include common Japanese & English transition terms.
* A heuristic also ignores very short (≤0.6s) generic‑named segments (likely transition remnants).
* Disable all filtering with `--no-ignore-effects` if you suspect over‑filtering.

---

## Limitations
* Cannot read the text of plain Text (non‑Fusion) title clips via API – hence the manual workflow.
* Assumes chronological ordering: blocks map to clips in timeline order. Re‑timing after generating an SRT may desync; regenerate after edits.
* No multi‑line styling export (SRT is plain text). Text+ rich formatting is not preserved.

---

## Troubleshooting
| Issue | Hint |
|-------|------|
| Blocks > clips | Extra stray `>` lines or over‑filtering. Try removing blank blocks or add `--no-ignore-effects`. |
| Clips > blocks | Merge short manual blocks or add more `>` blocks; or add more `--extra-ignore` patterns. |
| Missing Text+ lines | Ensure `--include-text-plus` was used for mixed export. |
| No module `DaVinciResolveScript` | Make sure Resolve is installed and running; macOS path is auto‑handled. |
| Typer not found | `pip install typer`. |

---

## License
See `LICENSE` (inherits the original project’s license terms).

---

## Original project credit
Based on the original TextPlus2SRT concept; refactored for a mixed manual/Text+ workflow and simplified dependencies (Typer only).


