"""YouTube Shorts Safe-Zone Subtitle Renderer & Phrase Splitter for Kontentor."""

import struct
import zlib
from pathlib import Path
from typing import Dict, List, Tuple

GLYPHS = {
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "C": [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    "D": [0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "G": [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "I": [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "J": [0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C],
    "K": [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "M": [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    "N": [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "P": [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    "Q": [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "S": [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "W": [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    "X": [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    "Y": [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    "Z": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    "3": [0x1F, 0x02, 0x04, 0x06, 0x01, 0x11, 0x0E],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    "?": [0x0E, 0x11, 0x01, 0x06, 0x04, 0x00, 0x04],
    "!": [0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04],
    ".": [0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C],
    ",": [0x00, 0x00, 0x00, 0x00, 0x04, 0x04, 0x08],
    ":": [0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00],
    "-": [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
    "'": [0x04, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00],
    " ": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
}


def _normalize_text(text: str) -> str:
    return (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("—", " - ")
        .replace("–", "-")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .upper()
        .strip()
    )


def split_narration_into_phrases(
    narration: str, total_duration: float
) -> List[Tuple[str, float, float]]:
    """Split spoken sentence into 2 or 3 natural subtitle phrases timed to voiceover."""
    words = narration.strip().split()
    if not words:
        return [("", 0.0, total_duration)]

    # Group into chunks of ~5-7 words so subtitles change dynamically as the narrator speaks
    chunk_size = 6 if len(words) <= 13 else 5
    chunks: List[List[str]] = [
        words[i : i + chunk_size] for i in range(0, len(words), chunk_size)
    ]
    total_words = len(words)
    phrases: List[Tuple[str, float, float]] = []
    t_cursor = 0.0

    for idx, chunk in enumerate(chunks):
        phrase_text = " ".join(chunk)
        if idx == len(chunks) - 1:
            t_end = total_duration
        else:
            ratio = len(chunk) / total_words
            t_end = round(min(total_duration, t_cursor + total_duration * ratio), 3)
        phrases.append((phrase_text, round(t_cursor, 3), round(t_end, 3)))
        t_cursor = t_end

    return phrases


def render_subtitle_banner_png(
    text: str, output_png: Path, width: int = 740, height: int = 148
) -> Path:
    """Render a high-contrast YouTube Shorts safe-zone subtitle pill with drop shadow."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    clean_text = _normalize_text(text)

    scale = 4  # 20x28 px per character
    char_w = 6 * scale
    char_h = 7 * scale
    max_chars_per_line = max(16, (width - 48) // char_w)

    words = clean_text.split()
    lines: List[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars_per_line:
            current = f"{current} {w}".strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    lines = lines[:2]

    # Mask values: 0 = background, 1 = drop shadow, 2 = bright white text, 3 = gold first/last line highlight
    text_mask = [[0] * width for _ in range(height)]
    total_text_h = len(lines) * char_h + (len(lines) - 1) * 14
    start_y = max(16, (height - total_text_h) // 2)

    for line_idx, line in enumerate(lines):
        line_w = len(line) * char_w
        start_x = max(20, (width - line_w) // 2)
        y0 = start_y + line_idx * (char_h + 14)
        color_code = 3 if line_idx == 0 else 2

        for c_idx, ch in enumerate(line):
            glyph = GLYPHS.get(ch, GLYPHS[" "])
            x0 = start_x + c_idx * char_w
            for gy in range(7):
                row_bits = glyph[gy]
                for gx in range(5):
                    if (row_bits >> (4 - gx)) & 1:
                        for sy in range(scale):
                            for sx in range(scale):
                                py = y0 + gy * scale + sy
                                px = x0 + gx * scale + sx
                                if 0 <= py < height and 0 <= px < width:
                                    text_mask[py][px] = color_code
                                # 3px drop shadow
                                spy = py + 3
                                spx = px + 3
                                if (
                                    0 <= spy < height
                                    and 0 <= spx < width
                                    and text_mask[spy][spx] == 0
                                ):
                                    text_mask[spy][spx] = 1

    rows = []
    for y in range(height):
        row = bytearray([0])
        is_gold_border = y < 4 or y >= height - 4
        for x in range(width):
            cell = text_mask[y][x]
            if cell == 3:
                # Golden highlight line (#FFD740)
                row.extend((255, 215, 64, 255))
            elif cell == 2:
                # Crisp pure white line (#FFFFFF)
                row.extend((255, 255, 255, 255))
            elif cell == 1:
                # Deep black drop-shadow
                row.extend((0, 0, 0, 255))
            elif is_gold_border or x < 4 or x >= width - 4:
                # Warm gold pill border (#EAB308)
                row.extend((234, 179, 8, 240))
            else:
                # High-contrast dark backdrop (#0D0A07, alpha 220)
                row.extend((13, 10, 7, 220))
        rows.append(bytes(row))

    raw_data = b"".join(rows)

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw_data, 6))
        + _chunk(b"IEND", b"")
    )
    output_png.write_bytes(png_bytes)
    return output_png


def _fmt_srt_time(seconds: float) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    total_sec = int(seconds)
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def export_srt(scenes: List[Dict], srt_path: Path) -> Path:
    """Export phrase-level synchronized .srt subtitle file."""
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    idx = 1
    for sc in scenes:
        scene_start = float(sc.get("start_time", 0.0))
        dur = float(sc.get("duration", 4.0))
        phrases = split_narration_into_phrases(sc.get("narration", ""), dur)
        for p_text, p_s, p_e in phrases:
            start_str = _fmt_srt_time(scene_start + p_s)
            end_str = _fmt_srt_time(scene_start + p_e)
            blocks.append(f"{idx}\n{start_str} --> {end_str}\n{p_text}\n")
            idx += 1
    srt_path.write_text("\n".join(blocks), encoding="utf-8")
    return srt_path
