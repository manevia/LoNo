"""Bounded, ephemeral adaptive HLS output. The original stream remains the fallback."""
import os
import re
import shutil
from pathlib import Path

from .. import config

PROFILES = ((360, 450, 600), (480, 850, 1100), (720, 1800, 2300))
TARGET = "adaptive-hls"
_SESSION = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
_ASSET = re.compile(r"abr_(?:360|480|720)(?:\.m3u8|_[0-9]+\.ts)")


def enabled():
    return os.getenv("MEDIA_ABR_ENABLED", "false").lower() in ("1", "true", "yes")


def folder(session_id: str) -> Path:
    if not _SESSION.fullmatch(session_id):
        raise ValueError("Invalid broadcast session ID")
    return Path(config.RECORDINGS_DIR) / ".adaptive-hls" / session_id


def args(source: str, output: Path, has_audio: bool, *, rtsp=True) -> list[str]:
    """One input, three aligned video renditions; never upscale the input."""
    cmd = ["-hide_banner", "-nostats", "-loglevel", "warning", "-progress", "pipe:1", "-y"]
    if rtsp:
        cmd += ["-rtsp_transport", "tcp"]
    elif source.startswith("rtmp"):
        cmd += ["-rw_timeout", "15000000"]
    cmd += ["-i", source, "-filter_complex_threads", "1"]
    graph = "[0:v]split=3[v360][v480][v720];" + ";".join(
        f"[v{height}]scale=-2:trunc(min(ih\\,{height})/2)*2,fps=25[o{height}]" for height, _, _ in PROFILES
    )
    cmd += ["-filter_complex", graph]
    variants = []
    for i, (height, bitrate, peak) in enumerate(PROFILES):
        cmd += ["-map", f"[o{height}]"]
        if has_audio:
            cmd += ["-map", "0:a:0"]
        cmd += [f"-c:v:{i}", "libx264", f"-preset:v:{i}", "veryfast", f"-threads:v:{i}", "2",
                f"-pix_fmt:v:{i}", "yuv420p", f"-b:v:{i}", f"{bitrate}k", f"-maxrate:v:{i}", f"{peak}k",
                f"-bufsize:v:{i}", f"{peak * 2}k", f"-g:v:{i}", "50", f"-keyint_min:v:{i}", "50",
                f"-sc_threshold:v:{i}", "0", f"-force_key_frames:v:{i}", "expr:gte(t,n_forced*2)"]
        if has_audio:
            cmd += [f"-c:a:{i}", "aac", f"-b:a:{i}", "64k", f"-ar:a:{i}", "48000"]
        variants.append(f"v:{i}" + (f",a:{i}" if has_audio else "") + f",name:{height}")
    return cmd + ["-f", "hls", "-hls_time", "2", "-hls_list_size", "12", "-hls_delete_threshold", "4",
                  "-hls_start_number_source", "epoch", "-hls_flags", "delete_segments+independent_segments+temp_file",
                  "-master_pl_name", "abr_master.m3u8", "-master_pl_publish_rate", "1",
                  "-var_stream_map", " ".join(variants), "-hls_segment_filename", str(output / "abr_%v_%09d.ts"),
                  str(output / "abr_%v.m3u8")]


def asset(session_id: str, name: str):
    """Only serve known generated filenames; callers must check session access first."""
    if not _ASSET.fullmatch(name):
        return None
    path = folder(session_id) / name
    return path if path.is_file() else None


def master(session_id: str):
    root = folder(session_id)
    path = root / "abr_master.m3u8"
    if not path.is_file():
        return None
    # Require all three playlists and at least one real segment each before
    # exposing the master. Until then the existing MediaMTX feed works normally.
    for height, _, _ in PROFILES:
        playlist = root / f"abr_{height}.m3u8"
        try:
            segments = [line for line in playlist.read_text().splitlines() if line.endswith(".ts")]
            if not segments or not asset(session_id, segments[-1]):
                return None
        except OSError:
            return None
    return path


def cleanup(session_id: str):
    # Only generated, session-scoped HLS cache files; recordings are elsewhere.
    shutil.rmtree(folder(session_id), ignore_errors=True)
