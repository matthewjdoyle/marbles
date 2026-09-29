"""Time reference versus accelerated final renders and verify identical pixels."""
import argparse
from contextlib import redirect_stdout
import io
import json
from statistics import median
from time import perf_counter

from marble_circles import MarbleGenerator
from marbledesk.studio.fast_renderer import FastMarbleGenerator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=1024)
    parser.add_argument('--runs', type=int, default=3)
    options = parser.parse_args()
    if options.runs < 1:
        parser.error('runs must be positive')
    records = []
    for style in ('carrara', 'jupiter'):
        durations = {}
        images = []
        for name, renderer in [('reference', MarbleGenerator), ('accelerated', FastMarbleGenerator)]:
            samples = []
            with redirect_stdout(io.StringIO()):
                for _ in range(options.runs):
                    start = perf_counter()
                    image = renderer(size=options.size, seed=42).generate_marble(
                        style_name=style, deterministic_noise=True)
                    samples.append(perf_counter() - start)
            durations[name] = median(samples)
            images.append(image)
        identical = images[0].tobytes() == images[1].tobytes()
        if not identical:
            raise AssertionError(f'{style} final pixels changed')
        records.append(dict(style=style, size=options.size, runs=options.runs,
                            reference_seconds=round(durations['reference'], 3),
                            accelerated_seconds=round(durations['accelerated'], 3),
                            speedup=round(durations['reference'] / durations['accelerated'], 2),
                            identical_pixels=identical))
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()
