"""Read-only, complete-row fixed-stride phase evidence; never decodes IDF.

No offsets, byte values, tokens or filenames are returned. A qualifying run
requires a nontrivial 8-byte repeated token and variable adjacent payload.
The result is only a structural heuristic, not a format specification.
"""
from __future__ import annotations

from array import array

try:
    import numpy as _np  # Optional acceleration; not required by Windows CI.
except ImportError:
    _np = None

TOKEN = 8
MIN_RUN = 32
MAX_ROWS = 128


def _variable_suffix(data: bytes, start: int, stride: int, count: int) -> bool:
    size = min(MAX_ROWS, count)
    for base in {0, max(0, (count - size) // 2), count - size}:
        rows = [data[start + (base + j) * stride + TOKEN:
                     start + (base + j + 1) * stride] for j in range(size)]
        if len(set(rows)) < 4:
            continue
        if sum(len({row[column] for row in rows}) > 1
               for column in range(stride - TOKEN)) >= 2:
            return True
    return False


def _candidate_token_runs(data: bytes, stride: int, min_run: int):
    """Yield maximal complete-row token chains, grouping matches by phase."""
    n = len(data)
    if _np is not None:
        arr = _np.frombuffer(data, dtype=_np.uint8)
        length = n - stride - TOKEN + 1
        mask = _np.ones(length, dtype=bool)
        for j in range(TOKEN):
            mask &= arr[j:j + length] == arr[j + stride:j + stride + length]
        matches = _np.flatnonzero(mask)
        for phase in range(stride):
            positions = matches[matches % stride == phase]
            if len(positions) == 0:
                continue
            breaks = _np.flatnonzero(_np.diff(positions) != stride)
            starts = _np.r_[0, breaks + 1]
            ends = _np.r_[breaks, len(positions) - 1]
            for first, last in zip(starts, ends):
                i = int(positions[first])
                count = min(65535, int(last - first + 2), (n - i) // stride)
                if count >= min_run:
                    yield i, count
    else:
        runs = array('H', [1]) * n
        for i in range(n - stride - TOKEN, -1, -1):
            if data[i:i + TOKEN] == data[i + stride:i + stride + TOKEN]:
                runs[i] = min(65535, 1 + runs[i + stride])
        for i in range(n - stride - TOKEN + 1):
            count = min(runs[i], (n - i) // stride)
            if count < min_run:
                continue
            if i >= stride and data[i - stride:i - stride + TOKEN] == data[i:i + TOKEN]:
                continue
            yield i, count


def phase_summary(data: bytes, stride: int, *, min_run: int = MIN_RUN) -> dict:
    """Analyze every byte position, returning aggregate-only run statistics.

    A run consists of *complete* stride-sized rows, with a repeated 8-byte
    token and sampled variable suffixes. 65,535 is the saturation bound.
    """
    empty = {'qualified_runs': 0, 'longest_qualified_run': 0,
             'distinct_phases': 0, 'qualified_coverage_bytes': 0}
    if stride <= TOKEN or min_run < 2 or len(data) < stride * min_run:
        return empty
    candidates = []
    for i, count in _candidate_token_runs(data, stride, min_run):
        if len(set(data[i:i + TOKEN])) < 3:
            continue
        if not _variable_suffix(data, i, stride, count):
            continue
        candidates.append((i, i + count * stride, count))
    if not candidates:
        return empty
    # Different eight-byte windows within the same repeated row can generate
    # overlapping candidates. Count each overlapping region only once,
    # selecting its longest complete-row candidate as representative.
    candidates.sort()
    canonical = []
    group = [candidates[0]]
    right = candidates[0][1]
    for candidate in candidates[1:]:
        if candidate[0] < right:
            group.append(candidate)
            right = max(right, candidate[1])
        else:
            canonical.append(max(group, key=lambda row: (row[2], -row[0])))
            group = [candidate]
            right = candidate[1]
    canonical.append(max(group, key=lambda row: (row[2], -row[0])))
    return {'qualified_runs': len(canonical),
            'longest_qualified_run': max(row[2] for row in canonical),
            'distinct_phases': len({row[0] % stride for row in canonical}),
            'qualified_coverage_bytes': sum(row[1] - row[0] for row in canonical)}
