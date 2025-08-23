# textp2srt

**Mixed subtitle export helper for DaVinci Resolve**
Plain Text clips + Text+ clips → one SRT file.  
  
Resolve API can read **Text+** but **not plain Text**.
This tool bridges the gap by Clipboard watcher (for plain Text)

This tool is based on the original **TextPlus2SRT** by [david-ca6](https://github.com/david-ca6).  
thanks for the original implementation and inspiration!

---

## Install

While Resolve is open:

```bash
pip install typer
```
  
## Commands

Run `--help` for full options.

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

Extra options:

* `--extra-ignore PATTERN`
* `--no-ignore-effects`

## Manual file format

Plain Text clips must be harvested manually via clipboard.
Each captured block begins with `>`:

```
>Hello world
>Second line
>Multi line block
Line 2
```

## Typical workflow

1. Find track

   ```bash
   python src/textp2srt.py tracks
   ```
2. Harvest plain Text clips

   ```bash
   python src/textp2srt.py watch manual.txt
   ```

   * For each **plain Text** clip:

     * Select it, Cmd+A → Cmd+C (text copied)
     * Watcher adds new `>` block
   * Text+ clips are read automatically later.

3. Preview & diagnose

   ```bash
   python src/textp2srt.py preview manual.txt V4 --include-text-plus
   python src/textp2srt.py diagnose manual.txt V4 --include-text-plus
   ```
4. Export

   ```bash
   python src/textp2srt.py srt manual.txt subs.srt V4 --include-text-plus
   ```

## Tips

* More blocks than clips → stray `>` or over-filtering
* More clips than blocks → merge / add blocks / update ignore patterns
  * These issues can be resolved by simply exporting the current blocks, placing them on the timeline, and checking the differences.

* First clipboard snapshot is ignored (often stale).
* Missing Text+ → forgot `--include-text-plus`
* Filtering: common transitions + very short text ignored by default.
  * Disable with `--no-ignore-effects`.
  * Add patterns with `--extra-ignore`.

---

## Resolve Scripting (macOS)

The script tries normal import, then:

```
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/
```

Quick test:

```bash
python -c "import DaVinciResolveScript as d;print('ok')"
```

If failing:

```bash
export PYTHONPATH="$PYTHONPATH:/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
```

Other OS paths:

* Windows: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules`
* Linux:   `/opt/resolve/Developer/Scripting/Modules`

---

## Debug helpers

Find scripting modules:

```powershell
# Windows PowerShell
gci -Recurse -Filter DaVinciResolveScript.py "C:/ProgramData/Blackmagic Design" 2>$null
```

```bash
# Linux
sudo find /opt/resolve -name DaVinciResolveScript.py 2>/dev/null
```

Show Resolve’s Python sys.path:

```bash
"/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fuscript" -l python3 -c "import sys;print(*sys.path,sep='\n')"
```

## License

See `LICENSE`.
