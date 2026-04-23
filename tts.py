"""
Stage 4 — TTS Audio Generator
Converts podcast script text into MP3 audio using Kokoro TTS.
"""

import os
# Make sure Homebrew ffmpeg is found when running via launchd
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

import soundfile as sf
import numpy as np
from datetime import datetime
from pathlib import Path


def generate_audio_kokoro(text: str, output_path: str) -> bool:
    try:
        from kokoro import KPipeline
        from pydub import AudioSegment

        print(f"  Generating audio: {output_path}")
        pipeline = KPipeline(lang_code="a")

        samples = []
        for _, _, audio in pipeline(
            text, voice="af_heart", speed=0.95
        ):
            samples.append(audio)

        if not samples:
            print("  No audio generated")
            return False

        full_audio = np.concatenate(samples)
        wav_path = output_path.replace(".mp3", ".wav")
        sf.write(wav_path, full_audio, 24000)

        audio_segment = AudioSegment.from_wav(wav_path)
        audio_segment.export(
            output_path, format="mp3", bitrate="128k"
        )
        os.remove(wav_path)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"  TTS error: {e}")
        return False


def generate_audio_gtts(text: str, output_path: str) -> bool:
    """Fallback TTS using gTTS — works on GitHub Actions."""
    try:
        from gtts import gTTS
        from pydub import AudioSegment
        import tempfile

        print(f"  Generating audio with gTTS fallback...")

        words = text.split()
        chunk_size = 500
        chunks = [
            " ".join(words[i:i+chunk_size])
            for i in range(0, len(words), chunk_size)
        ]

        audio_segments = []
        for chunk in chunks:
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False
            ) as tmp:
                tmp_path = tmp.name
            tts = gTTS(text=chunk, lang="en", slow=False)
            tts.save(tmp_path)
            audio_segments.append(
                AudioSegment.from_mp3(tmp_path)
            )
            os.remove(tmp_path)

        full_audio = audio_segments[0]
        for seg in audio_segments[1:]:
            full_audio += seg

        full_audio.export(output_path, format="mp3")
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"  gTTS error: {e}")
        return False


def generate_episode(script: str, date_str: str = None,
                     category: str = "tech") -> str:
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    Path(f"episodes/{date_str}").mkdir(
        parents=True, exist_ok=True
    )
    output_path = f"episodes/{date_str}/{category}.mp3"

    print("\n" + "="*50)
    print("TTS AUDIO GENERATION")
    print("="*50)
    print(f"  Date     : {date_str}")
    print(f"  Category : {category}")
    print(f"  Words    : {len(script.split())}")
    print(f"  Output   : {output_path}")

    is_github = os.getenv("GITHUB_ACTIONS") == "true"

    if is_github:
        success = generate_audio_gtts(script, output_path)
    else:
        success = generate_audio_kokoro(script, output_path)
        if not success:
            print("  Kokoro failed, trying gTTS fallback...")
            success = generate_audio_gtts(script, output_path)

    if success:
        print(f"\n{'='*50}")
        print(f"EPISODE GENERATED SUCCESSFULLY")
        print(f"  File: {output_path}")
        print(f"{'='*50}")
        return output_path

    print("  Audio generation failed")
    return ""
