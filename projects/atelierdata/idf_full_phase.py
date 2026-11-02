"""Read-only, complete-row fixed-stride phase evidence; never decodes IDF.

No offsets, byte values, tokens or filenames are returned. A qualifying run
requires a nontrivial 8-byte repeated token and variable adjacent payload.
The result is only a structural heuristic, not a format specification.
"""
from __future__ import annotations

try:
    import numpy as _np  # Optional acceleration; not required by Windows CI.
except ImportError:
    _np = None

TOKEN = 8
MIN_RUN = 32
MAX_ROWS = 128
# Bound temporary NumPy arrays independently of the size of the IDF member.
MATCH_CHUNK = 1 << 20


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
    """Yield maximal complete-row token chains with bounded auxiliary memory.

    Match positions are grouped by modulo-stride phase. A run of M adjacent
    matches denotes M+1 complete rows. The NumPy path scans <=1 MiB of match
    positions per chunk; the pure-Python path keeps only one run per phase.
    No list proportional to the size of the source file is constructed.
    """
    n = len(data)
    limit = n - stride - TOKEN + 1
    if limit <= 0:
        return
    active = {}  # phase -> (first_match, last_match, number_of_matches)

    def completed(first, matches):
        count = min(65535, matches + 1, (n - first) // stride)
        return (first, count) if count >= min_run else None

    if _np is not None:
        arr = _np.frombuffer(data, dtype=_np.uint8)
        for base in range(0, limit, MATCH_CHUNK):
            size = min(MATCH_CHUNK, limit - base)
            mask = _np.ones(size, dtype=bool)
            for j in range(TOKEN):
                mask &= (arr[base + j:base + j + size] ==
                         arr[base + stride + j:base + stride + j + size])
            matches = _np.flatnonzero(mask)
            # Group in vectorized operations, not a Python loop per matching
            # byte: low-entropy IDF members may contain millions of matches.
            for phase in range(stride):
                positions = matches[(matches + base) % stride == phase]
                if positions.size == 0:
                    continue
                breaks = _np.flatnonzero(_np.diff(positions) != stride)
                starts = _np.r_[0, breaks + 1]
                ends = _np.r_[breaks, positions.size - 1]
                for left, right in zip(starts, ends):
                    first = base + int(positions[left])
                    last = base + int(positions[right])
                    count = int(right - left + 1)
                    previous = active.get(phase)
                    if previous is not None and previous[1] + stride == first:
                        active[phase] = (previous[0], last, previous[2] + count)
                    else:
                        if previous is not None:
                            result = completed(previous[0], previous[2])
                            if result is not None:
                                yield result
                        active[phase] = (first, last, count)
    else:
        for i in range(limit):
            phase = i % stride
            previous = active.get(phase)
            if data[i:i + TOKEN] == data[i + stride:i + stride + TOKEN]:
                if previous is not None and previous[1] + stride == i:
                    active[phase] = (previous[0], i, previous[2] + 1)
                else:
                    if previous is not None:
                        result = completed(previous[0], previous[2])
                        if result is not None:
                            yield result
                    active[phase] = (i, i, 1)
            elif previous is not None:
                result = completed(previous[0], previous[2])
                if result is not None:
                    yield result
                del active[phase]
    for first, _, matches in active.values():
        result = completed(first, matches)
        if result is not None:
            yield result


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
