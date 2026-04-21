"""
Stage 4 — TTS Audio Generator
Converts podcast script text into MP3 audio using Kokoro TTS.
Stitches all article audios into one episode MP3.
"""

import os
import sys
import soundfile as sf
import numpy as np
from datetime import datetime
from pathlib import Path


def generate_audio_kokoro(text: str, output_path: str) -> bool:
    """
    Converts text to speech using Kokoro TTS.
    Saves as WAV first then converts to MP3 via pydub.
    """
    try:
        from kokoro import KPipeline

        print(f"  Generating audio: {output_path}")

        # Initialize Kokoro pipeline
        # af_heart is a warm friendly female voice
        pipeline = KPipeline(lang_code="a")

        # Generate audio
        samples = []
        for _, _, audio in pipeline(text, voice="af_bella", speed=0.95):
            samples.append(audio)

        if not samples:
            print("  No audio generated")
            return False

        # Combine all chunks
        full_audio = np.concatenate(samples)

        # Save as WAV first
        wav_path = output_path.replace(".mp3", ".wav")
        sf.write(wav_path, full_audio, 24000)

        # Convert WAV to MP3 using pydub
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_wav(wav_path)
        audio_segment.export(output_path, format="mp3", bitrate="128k")

        # Clean up WAV
        os.remove(wav_path)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"  TTS error: {e}")
        return False


def generate_episode(script: str, date_str: str = None, category: str = "tech") -> str:
    """
    Takes full episode script and generates one MP3 file.
    Returns path to the MP3 file.
    """

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Make sure episodes folder exists
    Path("episodes").mkdir(exist_ok=True)

    output_path = f"episodes/{category}/{date_str}.mp3"

    print("\n" + "="*50)
    print("TTS AUDIO GENERATION")
    print("="*50)
    print(f"  Date    : {date_str}")
    print(f"  Words   : {len(script.split())}")
    print(f"  Output  : {output_path}")
    print(f"  Est time: ~{len(script.split()) // 130} minutes of audio")

    success = generate_audio_kokoro(script, output_path)

    if success:
        print(f"\n{'='*50}")
        print(f"EPISODE GENERATED SUCCESSFULLY")
        print(f"  File: {output_path}")
        print(f"{'='*50}")
        return output_path
    else:
        print("  Audio generation failed")
        return ""


if __name__ == "__main__":
    # Test with a short script first
    test_script = """
    Welcome to your daily tech briefing. I am Herlin.

    Here is the thing about artificial intelligence right now —
    it is moving faster than most people realize.
    Think of it this way. Two years ago, asking an AI to write
    code felt like magic. Today it feels like using a calculator.
    That is how quickly this is becoming normal.

    The big story today is about open source AI models catching
    up to the big closed ones. Meta, Mistral, and a bunch of
    smaller labs are releasing models that are honestly pretty
    close to GPT-4 in quality. And they are free to use and run
    locally on your own machine.

    So what does this mean for you as a developer?
    It means you can build AI powered apps without paying
    OpenAI or Anthropic a single dollar. You run the model
    yourself. You own the data. Nobody is watching.
    That is a really big deal for privacy sensitive applications
    like healthcare or finance.

    And that is your briefing for today.
    Stay curious, keep building, and I will see you tomorrow.
    """

    print("Testing TTS generation...")
    print("="*50)
    print("This may take 1-2 minutes on first run")
    print("Kokoro downloads a small model file the first time")
    print("="*50)

    output = generate_episode(test_script, "test")

    if output:
        print(f"\nSuccess! Open this file to hear your podcast:")
        print(f"  open {output}")
    else:
        print("\nTTS generation failed — check errors above")
