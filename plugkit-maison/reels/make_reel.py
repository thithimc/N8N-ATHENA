#!/usr/bin/env python3
"""Rushs -> reel vertical 9:16 sous-titré, en local et gratuitement.

Étapes : (1) assemble les rushs, (2) coupe les silences, (3) transcrit avec
Whisper (faster-whisper, local), (4) incruste des sous-titres « style reels »
mot par mot + un titre d'accroche, (5) cadre en 1080x1920 et normalise le son.

Exemples :
  python make_reel.py rush1.mp4 rush2.mov -o reel.mp4
  python make_reel.py interview.mp4 --fond flou --accroche "3 erreurs en prépa"
  python make_reel.py talk.mp4 --pas-de-coupe --modele medium --langue fr

Dépendances : ffmpeg (avec libass) + `pip install faster-whisper`.
"""
import argparse, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

W, H = 1080, 1920


def run(cmd, capture=False):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Erreur ffmpeg :\n{' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stderr if capture else None


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def assemble(inputs, out):
    """Concatène les rushs en les ramenant au même format (1080 de large, 30 fps)."""
    if len(inputs) == 1:
        shutil.copy(inputs[0], out)
        return
    args, parts = [], []
    for i, f in enumerate(inputs):
        args += ["-i", str(f)]
        parts.append(f"[{i}:v]scale=1080:-2,setsar=1,fps=30,format=yuv420p[v{i}];"
                     f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}];")
    chain = "".join(f"[v{i}][a{i}]" for i in range(len(inputs)))
    fc = "".join(parts) + f"{chain}concat=n={len(inputs)}:v=1:a=1[v][a]"
    run(["ffmpeg", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", str(out)])


def cut_silences(src, out, noise_db, min_silence, pad):
    """Supprime les blancs (silencedetect) en gardant un peu de marge autour de la parole."""
    log = run(["ffmpeg", "-i", str(src), "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
               "-f", "null", "-"], capture=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    total = duration(src)
    keep, cursor = [], 0.0
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else total
        a, b = max(0, cursor - pad), min(total, s + pad)
        if b - a > 0.15:
            keep.append((a, b))
        cursor = e
    if total - cursor > 0.15:
        keep.append((max(0, cursor - pad), total))
    if not keep or (len(keep) == 1 and keep[0][1] - keep[0][0] > total - 0.3):
        shutil.copy(src, out)
        return 0.0
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
    run(["ffmpeg", "-y", "-i", str(src),
         "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
         "-af", f"aselect='{expr}',asetpts=N/SR/TB",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", str(out)])
    return total - sum(b - a for a, b in keep)


def transcribe(src, model_name, lang):
    import numpy as np
    from faster_whisper import WhisperModel
    # Audio décodé par ffmpeg (16 kHz mono) : évite les soucis de version de PyAV.
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "s16le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, _ = model.transcribe(audio, language=lang, word_timestamps=True, vad_filter=True)
    words = []
    for s in segments:
        for w in s.words or []:
            if not w.word.strip():
                continue
            # Whisper découpe parfois « aujourd'hui » en « aujourd » + « 'hui » : on recolle.
            if words and not w.word.startswith(" "):
                st, _, txt = words[-1]
                words[-1] = (st, w.end, txt + w.word.strip())
            else:
                words.append((w.start, w.end, w.word.strip()))
    return words


def ts(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def build_ass(words, out, hook, max_words, color):
    """Sous-titres par petits blocs, mot prononcé surligné (look « reels »)."""
    bgr = color.lstrip("#")
    hl = f"&H00{bgr[4:6]}{bgr[2:4]}{bgr[0:2]}"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,560,1
Style: Hook,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,1,0,0,0,100,100,0,0,3,18,0,8,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook:
        lines.append(f"Dialogue: 1,{ts(0)},{ts(3.5)},Hook,,0,0,0,,{hook.upper()}")
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w[0] - cur[-1][1] > 0.6 or cur[-1][2][-1:] in ".?!,"):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    for ci, chunk in enumerate(chunks):
        chunk_end = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else chunk[-1][1] + 0.3
        chunk_end = min(chunk_end, chunk[-1][1] + 0.5)
        for wi, (start, end, _) in enumerate(chunk):
            nxt = chunk[wi + 1][0] if wi + 1 < len(chunk) else chunk_end
            txt = " ".join(("{\\c" + hl + "&}" + t.upper() + "{\\c&H00FFFFFF&}") if j == wi else t.upper()
                           for j, (_, _, t) in enumerate(chunk))
            lines.append(f"Dialogue: 0,{ts(start)},{ts(max(nxt, start + 0.05))},Sub,,0,0,0,,{txt}")
    Path(out).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def render(src, ass, out, mode):
    if mode == "flou":
        v = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
             f"boxblur=30:5[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    else:
        v = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    if ass:
        esc = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        v += f",subtitles='{esc}'"
    run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", v + ",format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-r", "30", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])


def main():
    p = argparse.ArgumentParser(description="Rushs -> reel 9:16 sous-titré")
    p.add_argument("rushs", nargs="+", type=Path)
    p.add_argument("-o", "--sortie", type=Path, default=Path("reel.mp4"))
    p.add_argument("--fond", choices=["crop", "flou"], default="crop",
                   help="crop = recadre au centre ; flou = garde toute l'image sur fond flouté")
    p.add_argument("--accroche", default="", help="titre affiché en haut pendant 3,5 s")
    p.add_argument("--pas-de-coupe", action="store_true", help="ne pas supprimer les silences")
    p.add_argument("--sans-sous-titres", action="store_true")
    p.add_argument("--seuil-silence", type=float, default=-35, help="dB (défaut -35)")
    p.add_argument("--duree-silence", type=float, default=0.5, help="secondes min. d'un blanc à couper")
    p.add_argument("--modele", default="small", help="tiny/base/small/medium/large-v3")
    p.add_argument("--langue", default="fr")
    p.add_argument("--mots", type=int, default=3, help="mots max par sous-titre")
    p.add_argument("--couleur", default="#FFD400", help="couleur du mot surligné")
    p.add_argument("--srt", action="store_true", help="exporte aussi les sous-titres en .ass à côté")
    a = p.parse_args()

    for f in a.rushs:
        if not f.exists():
            sys.exit(f"Fichier introuvable : {f}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        print("1/4 Assemblage des rushs…")
        assemble(a.rushs, tmp / "joined.mp4")
        src = tmp / "joined.mp4"
        if not a.pas_de_coupe:
            print("2/4 Suppression des silences…")
            gained = cut_silences(src, tmp / "cut.mp4", a.seuil_silence, a.duree_silence, 0.12)
            src = tmp / "cut.mp4"
            print(f"    {gained:.1f} s de blancs coupés")
        ass = None
        if not a.sans_sous_titres:
            print(f"3/4 Transcription Whisper ({a.modele})…")
            words = transcribe(src, a.modele, a.langue)
            print(f"    {len(words)} mots")
            ass = tmp / "subs.ass"
            build_ass(words, ass, a.accroche, a.mots, a.couleur)
            if a.srt:
                shutil.copy(ass, a.sortie.with_suffix(".ass"))
        elif a.accroche:
            ass = tmp / "subs.ass"
            build_ass([], ass, a.accroche, a.mots, a.couleur)
        print("4/4 Rendu 1080x1920…")
        render(src, ass, a.sortie, a.fond)
    print(f"✅ {a.sortie} ({duration(a.sortie):.1f} s)")


if __name__ == "__main__":
    main()
