#!/usr/bin/env python3
"""textp2srt (Typer CLI)

Manual subtitles + Text/Text+ mixed SRT helper for DaVinci Resolve.

Commands:
    watch     Monitor clipboard -> append '>' delimited blocks
    count     Count text clips (effects filtered by default)
    tracks    List video track names
    preview   Show pairing (first 30 or all with --all)
    srt       Generate SRT (Text+ uses API text, plain Text uses manual) --include-text-plus
    diagnose  Show mismatch / ignored details (--all for full)
    stats     Show statistics breakdown
    apply     Apply manual blocks to Text+ clips (in order)

Manual input format: Lines starting with '>' begin a new block; lines until next '>' (or EOF) belong to that block.
"""
import sys, time, subprocess
import typer
from datetime import timedelta
from typing import List, Dict, Optional, Iterable

# ---------- Resolve bootstrap (same pattern as original) ----------

def load_source(module_name, file_path):
    if sys.version_info[:2] >= (3,5):
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    else:
        import imp
        return imp.load_source(module_name, file_path)

try:
    import DaVinciResolveScript as dvr_script
except ImportError:
    try:
        expectedPath = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
        load_source('DaVinciResolveScript', expectedPath + 'DaVinciResolveScript.py')
        import DaVinciResolveScript as dvr_script
    except Exception as ex:
        print("[error] Cannot import DaVinciResolveScript")
        print(ex)
        sys.exit(1)

resolve = dvr_script.scriptapp("Resolve")
pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
timeline = project.GetCurrentTimeline() if project else None

# ---------- Helpers ----------

def parse_manual(path: str) -> List[str]:
    blocks: List[str] = []
    if not path:
        return blocks
    cur: List[str] = []
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if line.startswith('>'):
                # flush existing
                if cur:
                    blocks.append('\n'.join(cur).strip())
                    cur = []
                cur.append(line[1:].lstrip())
            else:
                # continuation line
                if cur:
                    cur.append(line)
                else:
                    # ignore loose line without '>' start
                    pass
    if cur:
        blocks.append('\n'.join(cur).strip())
    # drop empties
    return [b for b in blocks if b]

def write_srt(blocks: List[str], clips: List[Dict], out_path: str):
    count = min(len(blocks), len(clips))
    if len(blocks) != len(clips):
        print(f"[warn] blocks={len(blocks)} clips={len(clips)} -> truncating to {count}")
    with open(out_path, 'w', encoding='utf-8') as w:
        for i in range(count):
            b = blocks[i]
            c = clips[i]
            start = _fmt_time(c['start'])
            end = _fmt_time(c['end'])
            w.write(f"{i+1}\n{start} --> {end}\n{b}\n\n")
    print(f"[ok] wrote {count} entries -> {out_path}")

def write_srt_mixed(manual_blocks: List[str], track_name: str, out_path: str,
                    include_text_plus: bool, ignore_effects: bool, extra_ignore: Optional[List[str]]):
    """Generate SRT where:
    - Plain Text clips (no Fusion comp) consume manual blocks sequentially.
    - Text+ clips (Fusion) pull their StyledText directly from the API (ignoring manual blocks).
    This lets manual input act only as a fallback for plain Text clips whose text cannot be retrieved via the API.
    """
    if not timeline:
        print('[error] no timeline')
        return
    extra_ignore = extra_ignore or []
    fps = float(timeline.GetSetting('timelineFrameRate'))
    # Gather items in order
    tcount = timeline.GetTrackCount('video')
    items = []
    for i in range(1, tcount+1):
        name = timeline.GetTrackName('video', i)
        if name != track_name:
            continue
        for it in (timeline.GetItemListInTrack('video', i) or []):
            start = it.GetStart()/fps
            end = it.GetEnd()/fps
            dur = end-start
            fusion_comp = None
            try:
                fusion_comp = it.GetFusionCompByIndex(1)
            except Exception:
                fusion_comp = None
            # Decide ignore (effects) by name for both types
            try:
                nm = it.GetName() or ''
            except Exception:
                nm = ''
            if _should_ignore(nm, dur, ignore_effects, extra_ignore):
                continue
            kind = 'text_plus' if fusion_comp else 'text'
            if kind == 'text_plus' and not include_text_plus:
                # skip if user doesn't want to include Text+ in SRT timeline mapping
                continue
            text_plus_value = None
            if kind == 'text_plus':
                # attempt to pull StyledText
                for tid in ('TextPlus','Text'):
                    try:
                        tool = fusion_comp.FindToolByID(tid) if fusion_comp else None
                    except Exception:
                        tool = None
                    if tool:
                        try:
                            text_plus_value = tool.GetInput('StyledText')
                        except Exception:
                            try:
                                # sometimes GetInput might not work, fallback to a control dictionary
                                text_plus_value = tool.GetData()['StyledText']
                            except Exception:
                                text_plus_value = None
                        if text_plus_value:
                            break
            items.append({'start': start, 'end': end, 'kind': kind, 'api_text': text_plus_value, 'name': nm})
    items.sort(key=lambda d: d['start'])
    manual_idx = 0
    used_manual = 0
    entries = []
    for it in items:
        if it['kind'] == 'text_plus' and it['api_text']:
            txt = it['api_text'].strip()
        elif it['kind'] == 'text_plus' and not it['api_text']:
            # fallback to manual if available
            if manual_idx < len(manual_blocks):
                txt = manual_blocks[manual_idx].strip()
                manual_idx += 1
                used_manual += 1
            else:
                txt = ''
        else:  # plain text clip
            if manual_idx < len(manual_blocks):
                txt = manual_blocks[manual_idx].strip()
                manual_idx += 1
                used_manual += 1
            else:
                txt = ''
        entries.append((it['start'], it['end'], txt))
    # Warn if manual blocks leftover or insufficient
    if manual_idx < len(manual_blocks):
        print(f"[warn] unused manual blocks: {len(manual_blocks)-manual_idx}")
    missing_plain = sum(1 for e in entries if not e[2])
    if missing_plain:
        print(f"[warn] empty subtitle entries: {missing_plain}")
    with open(out_path, 'w', encoding='utf-8') as w:
        for idx,(s,e,text) in enumerate(entries,1):
            w.write(f"{idx}\n{_fmt_time(s)} --> {_fmt_time(e)}\n{text}\n\n")
    print(f"[ok] wrote {len(entries)} entries -> {out_path} (manual_used={used_manual}/{len(manual_blocks)} text_plus={sum(1 for i in items if i['kind']=='text_plus')})")

def _fmt_time(sec: float) -> str:
    td = timedelta(seconds=sec)
    total_ms = int(td.total_seconds() * 1000)
    h = total_ms // 3600000
    m = (total_ms // 60000) % 60
    s = (total_ms // 1000) % 60
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

DEFAULT_IGNORE_NAMES = [
    'カラーディップ', 'クロスディゾルブ', 'ディゾルブ', 'ディップ',
    'Transition', 'Dip', 'Dissolve', 'Cross Dissolve'
]

def _should_ignore(name: str, duration: float, ignore_effects: bool, extra: Iterable[str]) -> bool:
    if not ignore_effects:
        return False
    lname = name.lower()
    patterns = [p.lower() for p in DEFAULT_IGNORE_NAMES] + [e.lower() for e in extra]
    for p in patterns:
        if p and p in lname:
            return True
    # Heuristic: extremely short (<=0.6s) often transition tail clips; keep heuristic conservative
    if duration <= 0.6:
        # only ignore if generic-like name (no letter/digit diversity)
        if len(set(lname)) < 6:
            return True
    return False

def collect_clips(track_name: str, exclude_text_plus: bool = True, ignore_effects: bool = True, extra_ignore: Optional[List[str]] = None) -> List[Dict]:
    res: List[Dict] = []
    if not timeline:
        return res
    extra_ignore = extra_ignore or []
    tcount = timeline.GetTrackCount('video')
    ignored = 0
    for i in range(1, tcount+1):
        name = timeline.GetTrackName('video', i)
        if name != track_name:
            continue
        items = timeline.GetItemListInTrack('video', i) or []
        fps = float(timeline.GetSetting('timelineFrameRate'))
        for it in items:
            fusion_comp = None
            try:
                fusion_comp = it.GetFusionCompByIndex(1)
            except Exception:
                fusion_comp = None
            if exclude_text_plus and fusion_comp:
                continue
            clip_name = ''
            try:
                clip_name = it.GetName() or ''
            except Exception:
                clip_name = ''
            start = it.GetStart() / fps
            end = it.GetEnd() / fps
            dur = end - start
            if _should_ignore(clip_name, dur, ignore_effects, extra_ignore):
                ignored += 1
                continue
            res.append({'item': it, 'start': start, 'end': end, 'name': clip_name})
    return res

def collect_clips_with_ignored(track_name: str, exclude_text_plus: bool = True, ignore_effects: bool = True, extra_ignore: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
    """Return both kept and ignored (for diagnostic)."""
    kept: List[Dict] = []
    ignored_list: List[Dict] = []
    if not timeline:
        return {'kept': kept, 'ignored': ignored_list}
    extra_ignore = extra_ignore or []
    tcount = timeline.GetTrackCount('video')
    for i in range(1, tcount+1):
        name = timeline.GetTrackName('video', i)
        if name != track_name:
            continue
        items = timeline.GetItemListInTrack('video', i) or []
        fps = float(timeline.GetSetting('timelineFrameRate'))
        for it in items:
            fusion_comp = None
            try:
                fusion_comp = it.GetFusionCompByIndex(1)
            except Exception:
                fusion_comp = None
            if exclude_text_plus and fusion_comp:
                # capture name & timing for full dump
                try:
                    nm = it.GetName() or ''
                except Exception:
                    nm = ''
                start = it.GetStart() / fps
                end = it.GetEnd() / fps
                dur = end - start
                ignored_list.append({'item': it, 'reason': 'text_plus', 'name': nm, 'start': start, 'end': end, 'dur': dur})
                continue
            try:
                clip_name = it.GetName() or ''
            except Exception:
                clip_name = ''
            start = it.GetStart() / fps
            end = it.GetEnd() / fps
            dur = end - start
            if _should_ignore(clip_name, dur, ignore_effects, extra_ignore):
                ignored_list.append({'item': it, 'reason': 'effect', 'name': clip_name, 'start': start, 'end': end, 'dur': dur})
            else:
                kept.append({'item': it, 'name': clip_name, 'start': start, 'end': end, 'dur': dur})
    return {'kept': kept, 'ignored': ignored_list}

def collect_textplus_clips(track_name: str) -> List[Dict]:
    out: List[Dict] = []
    if not timeline:
        return out
    tcount = timeline.GetTrackCount('video')
    for i in range(1, tcount+1):
        name = timeline.GetTrackName('video', i)
        if name != track_name:
            continue
        items = timeline.GetItemListInTrack('video', i) or []
        fps = float(timeline.GetSetting('timelineFrameRate'))
        for it in items:
            try:
                comp = it.GetFusionCompByIndex(1)
            except Exception:
                comp = None
            if comp:
                out.append({'item': it, 'comp': comp, 'start': it.GetStart()/fps, 'end': it.GetEnd()/fps})
    return out

def apply_to_textplus(blocks: List[str], track_name: str):
    clips = collect_textplus_clips(track_name)
    if not clips:
        print('[warn] no Text+ clips found')
        return
    count = min(len(blocks), len(clips))
    updated = 0
    for i in range(count):
        comp = clips[i]['comp']
        tool = None
        for tid in ('TextPlus','Text'):
            try:
                tool = comp.FindToolByID(tid)
                if tool: break
            except Exception:
                pass
        if not tool:
            continue
        try:
            tool.SetInput('StyledText', blocks[i])
            updated += 1
        except Exception:
            pass
    print(f"[ok] applied {updated}/{count} blocks to Text+ clips")

# ---------- Typer App ----------
app = typer.Typer(help='Resolve manual subtitle & Text/Text+ SRT tool')

def _ensure_timeline():
    if not timeline:
        typer.echo('[error] No active timeline')
        raise typer.Exit(code=1)

@app.command()
def watch(
    output: str = typer.Argument(..., help='Output file (UTF-8, appended)'),
    interval: float = typer.Option(1.0, '--interval', '-i', help='Polling interval seconds'),
    encoding: str = typer.Option('utf-8', '--encoding', help='Preferred clipboard decoding encoding')
):
    """Monitor clipboard and append new text as '>' blocks (skips the first snapshot)."""
    _ensure_timeline()
    path = output
    enc = encoding or 'utf-8'
    last = ''  # last accepted (or primed) clipboard text
    primed = False  # whether we've seen the first non-empty clipboard snapshot
    print(f"[watch] clipboard -> {path} (Ctrl+C to stop, encoding={enc}, skip first snapshot)")
    try:
        while True:
            # Capture raw bytes to avoid locale ASCII issues
            proc = subprocess.run(['pbpaste'], capture_output=True, text=False)
            raw = proc.stdout or b''
            try:
                cur = raw.decode(enc)
            except UnicodeDecodeError:
                # Fallback attempts
                for fallback in ('utf-8', 'utf-16-le', 'shift_jis', 'mac_roman'):
                    if fallback == enc:
                        continue
                    try:
                        cur = raw.decode(fallback)
                        print(f"[watch] fallback decoding used: {fallback}")
                        break
                    except Exception:
                        continue
                else:
                    cur = raw.decode(enc, errors='replace')
            if cur and cur.strip():
                # First non-empty snapshot: just prime (don't append)
                if not primed:
                    primed = True
                    last = cur
                    head_line = cur.strip().split('\n')[0]
                    print('[prime] initial clipboard (not added):', head_line[:60])
                elif cur != last:
                    block = cur.strip()
                    with open(path, 'a', encoding='utf-8') as w:
                        if block.startswith('>'):
                            w.write(block + '\n')
                        else:
                            w.write('>' + block + '\n')
                    head_line = block.split('\n')[0]
                    print('[add]', head_line[:60])
                    last = cur
            time.sleep(interval)
    except KeyboardInterrupt:
        print('\n[watch] stopped')
@app.command()
def count(
    track: str = typer.Argument(..., help='Target video track name'),
    include_text_plus: bool = typer.Option(False, '--include-text-plus', help='Include Text+ (Fusion) clips'),
    no_ignore_effects: bool = typer.Option(False, '--no-ignore-effects', help='Do not filter transition/effect clips'),
    extra_ignore: List[str] = typer.Option(None, '--extra-ignore', help='Additional ignore substrings (repeatable)')
):
    """Print number of subtitle candidate clips."""
    _ensure_timeline()
    clips = collect_clips(track, exclude_text_plus=not include_text_plus, ignore_effects=not no_ignore_effects, extra_ignore=extra_ignore or [])
    typer.echo(len(clips))

@app.command()
def tracks():
    """List video track names."""
    _ensure_timeline()
    for i in range(1, timeline.GetTrackCount('video')+1):
        typer.echo(timeline.GetTrackName('video', i))

@app.command()
def preview(
    input: str = typer.Argument(..., help='Manual subtitle file'),
    track: str = typer.Argument(..., help='Target track'),
    include_text_plus: bool = typer.Option(False, '--include-text-plus', help='Include Text+ clips'),
    no_ignore_effects: bool = typer.Option(False, '--no-ignore-effects', help='Do not filter effects'),
    extra_ignore: List[str] = typer.Option(None, '--extra-ignore', help='Extra ignore substrings'),
    all: bool = typer.Option(False, '--all', help='Show all (default 30)')
):
    """List pairing of manual blocks and clip timings."""
    _ensure_timeline()
    blocks = parse_manual(input)
    clips = collect_clips(track, exclude_text_plus=not include_text_plus, ignore_effects=not no_ignore_effects, extra_ignore=extra_ignore or [])
    typer.echo(f"blocks={len(blocks)} clips={len(clips)}")
    limit = min(len(blocks), len(clips)) if all else min(len(blocks), len(clips), 30)
    for i in range(limit):
        b = blocks[i].replace('\n',' / ')
        c = clips[i]
        dur = c['end'] - c['start']
        name = c.get('name','')
        typer.echo(f"{i+1:3d} {_fmt_time(c['start'])} -> {_fmt_time(c['end'])} ({dur:.2f}s) | {b[:80]} || {name}")
    if len(blocks) != len(clips):
        typer.echo('[warn] mismatch counts (final SRT will truncate)')

@app.command()
def srt(
    input: str = typer.Argument(..., help='Manual subtitle file'),
    output: str = typer.Argument(..., help='Output SRT path'),
    track: str = typer.Argument(..., help='Target track'),
    include_text_plus: bool = typer.Option(False, '--include-text-plus', help='Include Text+ clips (use API text; manual blocks only mapped to plain Text)'),
    no_ignore_effects: bool = typer.Option(False, '--no-ignore-effects', help='Do not filter effects/transitions'),
    extra_ignore: List[str] = typer.Option(None, '--extra-ignore', help='Additional ignore substrings')
):
    """Generate SRT (mixed: Text+ API text, plain Text manual)."""
    _ensure_timeline()
    blocks = parse_manual(input)
    if include_text_plus:
        write_srt_mixed(blocks, track, output, True, not no_ignore_effects, extra_ignore or [])
    else:
        clips = collect_clips(track, exclude_text_plus=True, ignore_effects=not no_ignore_effects, extra_ignore=extra_ignore or [])
        write_srt(blocks, clips, output)

@app.command()
def diagnose(
    input: str = typer.Argument(..., help='Manual subtitle file'),
    track: str = typer.Argument(..., help='Target track'),
    include_text_plus: bool = typer.Option(False, '--include-text-plus', help='Include Text+ in pairing'),
    no_ignore_effects: bool = typer.Option(False, '--no-ignore-effects', help='Do not filter effects'),
    extra_ignore: List[str] = typer.Option(None, '--extra-ignore', help='Extra ignore substrings'),
    all: bool = typer.Option(False, '--all', help='Show full kept/ignored list')
):
    """Show mismatch status and ignored clips."""
    _ensure_timeline()
    blocks = parse_manual(input)
    data = collect_clips_with_ignored(track, exclude_text_plus=not include_text_plus, ignore_effects=not no_ignore_effects, extra_ignore=extra_ignore or [])
    kept = data['kept']
    ignored = data['ignored']
    typer.echo(f"blocks={len(blocks)} kept_clips={len(kept)} ignored={len(ignored)}")
    if all:
        for i,c in enumerate(kept,1):
            typer.echo(f"K {i:03d} {_fmt_time(c['start'])} -> {_fmt_time(c['end'])} {c['dur']:.2f}s | {c.get('name','')}")
        for ig in ignored:
            nm = ig.get('name','')
            if 'start' in ig:
                typer.echo(f"I {ig['reason']:<8} {_fmt_time(ig['start'])} -> {_fmt_time(ig['end'])} {ig['dur']:.2f}s | {nm}")
            else:
                typer.echo(f"I {ig['reason']:<8} -- -> -- | {nm}")
    else:
        if len(blocks) != len(kept):
            typer.echo('[info] counts differ; first 10 kept:')
        for i,c in enumerate(kept[:10]):
            typer.echo(f"K {i+1:03d} {_fmt_time(c['start'])} -> {_fmt_time(c['end'])} {c['dur']:.2f}s | {c.get('name','')[:60]}")
        if ignored:
            typer.echo('[info] ignored sample (up to 10):')
            for ig in ignored[:10]:
                nm = ig.get('name','')
                if 'start' in ig:
                    typer.echo(f"I {ig['reason']:<8} {nm[:40]} {_fmt_time(ig['start'])} {ig['dur']:.2f}s")
                else:
                    typer.echo(f"I {ig['reason']:<8} {nm[:40]}")
    if len(blocks) > len(kept):
        typer.echo('[hint] More blocks than clips: check stray > lines or try --no-ignore-effects')
    elif len(blocks) < len(kept):
        typer.echo('[hint] More clips than blocks: add --extra-ignore patterns or merge blocks')

@app.command()
def stats(
    track: str = typer.Argument(..., help='Target track'),
    no_ignore_effects: bool = typer.Option(False, '--no-ignore-effects', help='Do not filter effects'),
    extra_ignore: List[str] = typer.Option(None, '--extra-ignore', help='Extra ignore substrings')
):
    """Show statistics (kept/effect/Text+) and tail samples."""
    _ensure_timeline()
    data = collect_clips_with_ignored(track, exclude_text_plus=True, ignore_effects=not no_ignore_effects, extra_ignore=extra_ignore or [])
    kept = data['kept']
    ignored = data['ignored']
    effect_ignored = [i for i in ignored if i.get('reason') == 'effect']
    text_plus_ignored = [i for i in ignored if i.get('reason') == 'text_plus']
    total_raw = 0
    text_plus_total = 0
    effect_name_hits = 0
    if timeline:
        tcount = timeline.GetTrackCount('video')
        for i in range(1, tcount+1):
            name = timeline.GetTrackName('video', i)
            if name != track:
                continue
            items = timeline.GetItemListInTrack('video', i) or []
            fps = float(timeline.GetSetting('timelineFrameRate'))
            for it in items:
                total_raw += 1
                try:
                    comp = it.GetFusionCompByIndex(1)
                except Exception:
                    comp = None
                if comp:
                    text_plus_total += 1
                try:
                    nm = (it.GetName() or '').lower()
                except Exception:
                    nm = ''
                for pat in [p.lower() for p in DEFAULT_IGNORE_NAMES]:
                    if pat and pat in nm:
                        effect_name_hits += 1
                        break
    typer.echo(f"[stats] track='{track}' raw_items={total_raw}")
    typer.echo(f"[stats] kept_text_clips={len(kept)}  ignored_effect={len(effect_ignored)}  ignored_text_plus={len(text_plus_ignored)}")
    typer.echo(f"[stats] total_text_plus_raw={text_plus_total}  effect_name_hits_raw={effect_name_hits}")
    # Tail preview
    def show_tail(label, seq, n=5):
        if not seq:
            return
        print(f"[tail {label}] last {min(n,len(seq))}:")
        tail = seq[-n:]
        for c in tail:
            start = _fmt_time(c.get('start',0)) if 'start' in c else '--'
            end = _fmt_time(c.get('end',0)) if 'end' in c else '--'
            nm = c.get('name','') if 'name' in c else ''
            reason = c.get('reason','')
            if label=='kept':
                print(f"  K {start} -> {end} | {nm[:60]}")
            else:
                dur = c.get('dur',0)
                print(f"  I {reason:<8} {start} -> {end} {dur:.2f}s | {nm[:60]}")
    show_tail('kept', kept)
    show_tail('ignored', effect_ignored)
    show_tail('ignored', text_plus_ignored)

@app.command()
def apply(
    input: str = typer.Argument(..., help='Manual subtitle file'),
    track: str = typer.Argument(..., help='Target track')
):
    """Apply manual blocks into Text+ clips (sequential)."""
    _ensure_timeline()
    blocks = parse_manual(input)
    apply_to_textplus(blocks, track)

# ---------- Main ----------

def main():
    app()

if __name__ == '__main__':
    main()
