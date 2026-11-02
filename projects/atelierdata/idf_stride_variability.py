"""Bounded heuristic for variable payload in fixed-stride IDF byte runs.

Only a repeated nontrivial 8-byte token with at least two varying
non-token columns counts. This is NOT evidence of record boundaries,
a file format specification, encryption, or a working decoder.
No source bytes, offsets or filenames are returned.
"""
from __future__ import annotations

from array import array

TOKEN = 8
MIN_RUN = 32


def longest_variable_payload_streak(
    data: bytes, stride: int, *, min_run: int = MIN_RUN
) -> int:
    """Return longest qualifying complete-row token chain, or zero.

    At least four distinct sampled suffixes and two varying non-token
    columns are required. Only up to 128 rows from the start, middle and
    end of each candidate are examined. Counts saturate at 65535.
    This is a heuristic, not evidence of record boundaries or a decoder.
    """
    if stride <= TOKEN or min_run < 2 or len(data) < stride * min_run:
        return 0
    n = len(data)
    runs = array("H", [1]) * n
    for i in range(n - stride - TOKEN, -1, -1):
        if data[i:i + TOKEN] == data[i + stride:i + stride + TOKEN]:
            runs[i] = min(65535, runs[i + stride] + 1)

    best = 0
    for i in range(n - stride - TOKEN + 1):
        count = runs[i]
        if count < max(min_run, best + 1):
            continue
        # Avoid rechecking the same chain at each later occurrence.
        if i >= stride and runs[i - stride] > count:
            continue
        if len(set(data[i:i + TOKEN])) < 3:
            continue
        count = min(count, (n - i) // stride)
        if count < max(min_run, best + 1):
            continue
        size = min(count, 128)
        starts = (0, max(0, (count - size) // 2), count - size)
        for start in set(starts):
            suffixes = [
                data[i + (start + j) * stride + TOKEN:
                     i + (start + j + 1) * stride]
                for j in range(size)
            ]
            if len(set(suffixes)) < 4:
                continue
            if sum(len({row[k] for row in suffixes}) > 1
                   for k in range(stride - TOKEN)) >= 2:
                best = count
                break
    return best


def has_variable_payload_streak(
    data: bytes, stride: int, *, min_run: int = MIN_RUN
) -> bool:
    """Backward-compatible boolean form of the aggregate heuristic."""
    return longest_variable_payload_streak(
        data, stride, min_run=min_run) > 0
