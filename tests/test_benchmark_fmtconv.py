# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boundaries that keep benchmark timings and conversion comparisons meaningful."""

from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace
from time import perf_counter
import unittest

from benchmark_fmtconv import Case, request_frames, verify_outputs


class Plane:
    shape = (64, 64)

    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        y, x = index
        return self.values[y * 64 + x]


class Frame:
    width = height = 64

    def __init__(self, values, bits=8):
        self.format = SimpleNamespace(bits_per_sample=bits, num_planes=1)
        self.plane = Plane(values)
        self.closed = False

    def __getitem__(self, plane):
        return self.plane

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class Clip:
    def __init__(self, frame):
        self.frame = frame

    def get_frame(self, index):
        return self.frame


class BenchmarkTests(unittest.TestCase):
    def test_wrong_scaling_is_rejected_even_with_valid_output_codes(self):
        case = Case("full", "GRAY", 16, 8, scale=1)
        frame = Frame([128] * 4096)
        with self.assertRaisesRegex(RuntimeError, "tile mean"):
            verify_outputs({"wrong_full_range": Clip(frame)}, case, 64, 64)
        self.assertTrue(frame.closed)

    def test_spatial_dither_must_preserve_the_expected_mean(self):
        case = Case("shift", "GRAY", 16, 8)
        frame = Frame([127] * 4096)
        with self.assertRaisesRegex(RuntimeError, "tile mean"):
            verify_outputs({"biased": Clip(frame)}, case, 64, 64)

    def test_low_bits_validate_levels_in_an_eight_bit_container(self):
        case = Case("two_bits", "GRAY", 8, 2, scale=1)
        # Input 127 maps to index 127/85; 2024 of 4096 thresholds round up.
        frame = Frame([170] * 2024 + [85] * (4096 - 2024))
        samples, validation = verify_outputs({"two_bits": Clip(frame)}, case, 64, 64)
        self.assertEqual(samples, 4096)
        self.assertAlmostEqual(validation["two_bits"][0]["expected"], 127)
        self.assertLess(abs(validation["two_bits"][0]["mean_error"]), 0.02)
        self.assertTrue(frame.closed)

    def test_low_bits_reject_unexpanded_quantization_indices(self):
        case = Case("two_bits", "GRAY", 8, 2, scale=1)
        frame = Frame([1] * 4096)
        with self.assertRaisesRegex(RuntimeError, "quantization neighbours"):
            verify_outputs({"unexpanded": Clip(frame)}, case, 64, 64)

    def test_requests_use_unique_indices_and_release_every_frame(self):
        requested, frames = [], []

        class Source:
            def get_frame_async(self, index):
                requested.append(index)
                frame = Frame([])
                frames.append(frame)
                future = Future()
                future.set_result(frame)
                return future

        request_frames(Source(), 37, 11, 4, perf_counter() + 10)
        self.assertEqual(requested, list(range(37, 48)))
        self.assertTrue(all(frame.closed for frame in frames))


if __name__ == "__main__":
    unittest.main()
