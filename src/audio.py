"""Audio helpers. Uses the ffmpeg binary bundled by imageio-ffmpeg, so the bot needs
no system ffmpeg install — important on Windows where ffmpeg is rarely on PATH."""
from __future__ import annotations

import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """Absolute path to a portable ffmpeg binary (downloaded once by imageio-ffmpeg)."""
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def to_opus_ogg(in_path: str, out_path: str) -> str:
    """Transcode any audio file to OGG/Opus, the format Telegram needs to render a
    proper voice note (with waveform) via reply_voice."""
    subprocess.run(
        [ffmpeg_exe(), "-y", "-i", in_path, "-c:a", "libopus", "-b:a", "48k", out_path],
        check=True,
        capture_output=True,
    )
    return out_path
