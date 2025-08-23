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

### Practical use of `watch`
Goal: harvest existing plain Text (title) clips so you don't retype them.

Flow:
1. Start watcher in terminal:
	```
	python src/textp2srt.py watch manual.txt
	```
2. Switch to Resolve. For each plain Text clip (NOT Text+):
	* Click the clip.
	* In the Inspector select the text field, press Cmd+A (Ctrl+A on Windows) then Cmd+C (Ctrl+C).
	* The clipboard change is auto‑captured as a new `>` block.
3. Skip any Text+ clips (their text is read via API later).
4. When done, Ctrl+C the watcher. Now `manual.txt` has blocks matching your plain Text clips in timeline order.
5. Run `preview` / `diagnose` and then `srt` with `--include-text-plus` for the mixed export.

Tips:
* First clipboard snapshot is ignored on purpose (often stale content).
* If you copied something wrong just edit `manual.txt` directly.

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

Windows / Linux quick paths(maybe):
```
Windows (ProgramData): C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules
Linux (default):       /opt/resolve/Developer/Scripting/Modules
```

Find them if unsure:
```
# PowerShell (run as user)
gci -Recurse -Filter DaVinciResolveScript.py "C:/ProgramData/Blackmagic Design" 2>$null

# Linux
sudo find /opt/resolve -name DaVinciResolveScript.py 2>/dev/null
```

Using fuscript to print sys.path (any OS):
```
"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fuscript" -l python3 -c "import sys;print(*sys.path,sep='\n')"
```
On Windows adjust path, e.g.:
```
"C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe" -l python3 -c "import sys;print(*sys.path,sep='\n')"
```

Trouble hints:
* Blocks > clips -> stray `>` or over filtering.
* Clips > blocks -> merge or add blocks / add ignore patterns.
* Missing Text+ lines -> forgot `--include-text-plus`.

License: see `LICENSE`.
Credit: based on original TextPlus2SRT; simplified for mixed workflow.


