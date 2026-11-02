"""Generate Hog's original short mono WAV effects using standard-library math."""

from array import array
import math
from pathlib import Path
from random import Random
import wave

RATE = 22050
OUTPUT = Path(__file__).resolve().parents[1] / "assets/sounds"


def tone(notes, length, *, noise=False):
    values = array("h")
    rng = Random(7)
    total = int(length * RATE)
    for index in range(total):
        time = index / RATE
        segment = min(len(notes) - 1, int(index / total * len(notes)))
        frequency = notes[segment]
        envelope = min(1, time / .015) * min(1, (length - time) / .06)
        wave_value = math.sin(2 * math.pi * frequency * time)
        if noise:
            wave_value = .4 * wave_value + .6 * rng.uniform(-1, 1)
        values.append(int(8500 * envelope * wave_value))
    if __import__("sys").byteorder != "little":
        values.byteswap()
    return values.tobytes()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    effects = {"roll": ((220, 180, 260, 160), .19, True),
               "sow": ((220, 165), .23, False),
               "bonus": ((523, 659, 784), .31, False),
               "win": ((523, 659, 784, 1047), .57, False)}
    for name, (notes, length, noise) in effects.items():
        with wave.open(str(OUTPUT / f"{name}.wav"), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(RATE)
            stream.writeframes(tone(notes, length, noise=noise))
        print(f"Generated {name}.wav")


if __name__ == "__main__":
    main()
