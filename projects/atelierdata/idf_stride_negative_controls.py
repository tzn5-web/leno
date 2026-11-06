"""Conservative, aggregate-only IDF stride hypothesis ranking.

This is NOT a decoder. Use only authorized, SHA256-verified samples.
No sample bytes, motifs, offsets or private paths are emitted.
"""
from idf_stride_hypotheses import compare_stride_hypotheses, STRIDES, TOKEN_BYTES


def rank_stride_evidence(sample: bytes, strides=STRIDES):
    """Rank candidate strides against neighboring-stride negative controls.

    An apparent record width is only interesting if its equality rate is
    materially above both adjacent widths. Periodic/low-diversity buffers
    are explicitly marked inconclusive. This heuristic cannot prove records.
    """
    if not isinstance(sample, bytes):
        raise TypeError("Expected immutable bytes")
    candidates = tuple(strides)
    if not candidates:
        raise ValueError("At least one candidate stride is required")
    if any(type(s) is not int or s < TOKEN_BYTES + 2 or s >= 128 for s in candidates):
        raise ValueError("Candidate stride must allow valid neighboring controls")
    if len(candidates) != len(set(candidates)):
        raise ValueError("Duplicate candidate strides")
    controls = sorted(set(candidates) | {n for s in candidates for n in (s - 1, s + 1) if n > TOKEN_BYTES})
    raw = compare_stride_hypotheses(sample, controls)
    rows = []
    for stride in candidates:
        current = raw["hypotheses"][str(stride)]
        denom = current["possible_window_pairs"]
        rate = current["matching_window_pairs"] / denom if denom else 0.0
        neighbors = [raw["hypotheses"][str(n)] for n in (stride - 1, stride + 1) if str(n) in raw["hypotheses"]]
        baseline = max((r["matching_window_pairs"] / r["possible_window_pairs"]
                        for r in neighbors if r["possible_window_pairs"]), default=0.0)
        # Small samples can produce a perfect equality rate by chance.
        # Require independent comparison opportunities and a material margin.
        insufficient_pairs = denom < 32
        weak_margin = (rate - baseline) < 0.05
        inconclusive = (insufficient_pairs or weak_margin or current["low_diversity_confounder"]
                        or current["global_periodicity_confounder"]
                        or current["qualified_runs"] == 0 or rate <= baseline)
        rows.append({"stride": stride, "equality_rate": round(rate, 6),
                     "neighbor_control_max_rate": round(baseline, 6),
                     "excess_over_controls": round(rate - baseline, 6),
                     "qualified_runs": current["qualified_runs"],
                     "insufficient_pairs": insufficient_pairs,
                     "weak_control_margin": weak_margin,
                     "inconclusive": bool(inconclusive),
                     "record_format_proven": False})
    return {"schema": "atelierdata-idf-negative-controls-v1",
            "sample_bytes": len(sample), "token_bytes": TOKEN_BYTES,
            "source_executed": False, "idf_decoder_proven": False,
            "results": rows,
            "warning": "Minimum 32 pairs and 0.05 margin are conservative heuristic gates, not statistical significance or proof of record boundaries."}
