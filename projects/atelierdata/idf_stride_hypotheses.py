"""Synthetic-safe fixed-stride hypothesis comparison for IDF samples.

This is descriptive evidence only. No original bytes or motif tokens are exported.
"""
from collections import defaultdict

TOKEN_BYTES = 8
STRIDES = (19, 21)
MAX_SAMPLE = 256 * 1024


def compare_stride_hypotheses(sample: bytes, strides=STRIDES):
    """Count matching 8-byte windows at each offset + stride.

    Adjacent matches in the same phase form a run. Runs are counted only
    when at least 8 token positions match, to avoid isolated coincidences.
    The output is aggregate-only and cannot reconstruct source data.
    """
    if len(sample) > MAX_SAMPLE:
        raise ValueError("Sample exceeds bounded static-analysis limit")
    if not strides or any(type(s) is not int or s < TOKEN_BYTES + 1 or s > 128 for s in strides):
        raise ValueError("Invalid candidate stride")
    # A constant or low-diversity buffer can match every candidate stride.
    # Report this confounder instead of treating repetition as record evidence.
    distinct_bytes = len(set(sample))
    low_diversity = bool(sample) and distinct_bytes <= 2
    result = {}
    for stride in strides:
        matches = [i for i in range(max(0, len(sample) - stride - TOKEN_BYTES + 1))
                   if sample[i:i + TOKEN_BYTES] == sample[i + stride:i + stride + TOKEN_BYTES]]
        # Each run is a chain of successive positions spaced exactly by stride.
        present = set(matches)
        chains = []
        for start in matches:
            if start - stride in present:
                continue
            length = 1
            while start + length * stride in present:
                length += 1
            if length >= 7:  # 7 equalities imply 8 repeated token positions.
                chains.append((start, length + 1))
        possible_pairs = max(0, len(sample) - stride - TOKEN_BYTES + 1)
        # Near-total equality across all offsets indicates whole-buffer
        # periodicity, not evidence of discrete record boundaries.
        global_periodicity = possible_pairs > 0 and len(matches) / possible_pairs >= 0.95
        result[str(stride)] = {
            "matching_window_pairs": len(matches),
            "possible_window_pairs": possible_pairs,
            "global_periodicity_confounder": global_periodicity,
            "qualified_runs": len(chains),
            "longest_run_tokens": max((length for _, length in chains), default=0),
            "qualified_phase_count": len({start % stride for start, _ in chains}),
            "low_diversity_confounder": low_diversity,
        }
    return {"schema": "atelierdata-idf-stride-hypotheses-v1",
            "sample_bytes": len(sample), "token_bytes": TOKEN_BYTES,
            "distinct_byte_values": distinct_bytes,
            "source_executed": False, "idf_decoder_proven": False,
            "hypotheses": result,
            "interpretation": "Repeated windows alone cannot establish records or decode IDF; low-diversity or globally periodic inputs can generate spurious matches."}
