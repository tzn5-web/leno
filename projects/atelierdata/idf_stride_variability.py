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


def has_variable_payload_streak(
    data: bytes, stride: int, *, min_run: int = MIN_RUN
) -> bool:
    """True if one >=min_run token chain has varied non-token bytes.

    Up to 128 complete rows are examined at the beginning, middle and end
    of each maximal chain. Incomplete trailing rows never qualify.
    """
    if (stride <= TOKEN or min_run < 2
            or len(data) < stride * min_run):
        return False
    n = len(data)
    runs = array("H", [1]) * n
    for i in range(n - stride - TOKEN, -1, -1):
        if data[i:i + TOKEN] == data[i + stride:i + stride + TOKEN]:
            runs[i] = min(65535, runs[i + stride] + 1)

    for i in range(n - stride - TOKEN + 1):
        count = runs[i]
        if count < min_run:
            continue
        # Avoid checking the same maximal chain for every repeated token.
        if i >= stride and runs[i - stride] > count:
            continue
        if len(set(data[i:i + TOKEN])) < 3:
            continue
        count = min(count, (n - i) // stride)
        if count < min_run:
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
            varying_columns = sum(
                len({row[k] for row in suffixes}) > 1
                for k in range(stride - TOKEN)
            )
            if varying_columns >= 2:
                return True
    return False
