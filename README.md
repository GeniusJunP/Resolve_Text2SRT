## textp2srt (macOS)

Mixed subtitle export helper for DaVinci Resolve. Plain Text clips + Text+ clips -> one SRT.

Core idea:
* Resolve API can read Text+ but not simple Text.
* You keep a manual file. Each block starts with `>`.
* Plain Text clips consume blocks in order.
* Text+ clips use their own StyledText.
* Export a mixed SRT in timeline order.

Install (while Resolve is open):
```
pip install typer
```

Manual file example:
```
>Hello world
>Second line
>Multi line block
Line 2
```

Main commands (run `--help` for options):
```
tracks                              # list video track names
watch manual.txt                    # clipboard -> >blocks (skips first snapshot)
count TRACK [--include-text-plus]
preview manual.txt TRACK [--include-text-plus] [--all]
srt manual.txt out.srt TRACK [--include-text-plus]
diagnose manual.txt TRACK [--include-text-plus] [--all]
stats TRACK
apply manual.txt TRACK              # write blocks into Text+ clips
```
Options you might add: `--extra-ignore PATTERN`, `--no-ignore-effects`.

Typical quick flow:
1. Find track: `python src/textp2srt.py tracks`
2. Capture lines while editing: `python src/textp2srt.py watch manual.txt`
3. Preview: `python src/textp2srt.py preview manual.txt V4 --include-text-plus`
4. Fix mismatches if counts differ (`diagnose`, edit manual file)
5. Export: `python src/textp2srt.py srt manual.txt subs.srt V4 --include-text-plus`

Filtering: common transition names + very short generic clips ignored. Turn off with `--no-ignore-effects`. Add patterns with `--extra-ignore`.

Limitations: cannot read plain Text content (why manual blocks exist). Ordering matters. Formatting beyond plain text not preserved.

DaVinciResolveScript loading (macOS): the script first tries normal import, then looks in:
```
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/
```
If import fails: ensure Resolve is running, check that path exists. Quick test:
```
python -c "import DaVinciResolveScript as d;print('ok')"
```
If still failing, temporarily:
```
export PYTHONPATH="$PYTHONPATH:/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
```

Trouble hints:
* Blocks > clips -> stray `>` or over filtering.
* Clips > blocks -> merge or add blocks / add ignore patterns.
* Missing Text+ lines -> forgot `--include-text-plus`.

License: see `LICENSE`.
Credit: based on original TextPlus2SRT; simplified for mixed workflow.


