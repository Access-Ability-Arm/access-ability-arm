#!/usr/bin/env python3
"""
Offline validation harness for depth-fusion (variance-gated averaging).

The discontinuity "skirt" — phantom points hanging off object edges — is
caused by a plain per-pixel mean blending a pixel that flickers between
foreground and background depth into a mid-air mid-depth value. Variance
gating rejects those temporally-unstable pixels instead of guessing a depth.

This harness lets that fix be validated WITHOUT the camera, because the raw
per-frame depth stack (the input to averaging) is otherwise discarded after a
freeze. Three modes:

  synth   Generate a synthetic raw stack with a known flickering edge, so the
          fix can be verified immediately (no camera, no field capture).

  replay  Load a saved raw stack (logs/raw_depth/*.npz, written when the app
          runs with AAA_SAVE_RAW_DEPTH=1) and A/B plain mean vs variance-gated
          averaging. Reports how many edge pixels gating removes and — for
          synthetic stacks with ground truth — precision/recall of removal.

  analyze Inspect an already-exported point cloud (logs/pointclouds/*.ply or
          *.npz) for the skirt symptom via its Z-depth distribution. Works on
          existing data, but only confirms the symptom — it cannot validate
          the fix, since the cloud is already post-averaging.

Usage:
  python scripts/validate_depth_fusion.py synth   logs/raw_depth/synth.npz
  python scripts/validate_depth_fusion.py replay  logs/raw_depth/synth.npz
  python scripts/validate_depth_fusion.py analyze logs/pointclouds/<file>.ply
"""

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
for pkg in ("core", "vision", "lite6_driver"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / pkg / "src"))

from aaa_vision.depth_fusion import variance_gated_average  # noqa: E402


# ---------------------------------------------------------------------------
# synth: generate a synthetic raw stack with a known flickering edge
# ---------------------------------------------------------------------------
def make_synthetic_stack(
    h: int = 360,
    w: int = 480,
    n_frames: int = 20,
    fg_mm: float = 500.0,
    bg_mm: float = 1500.0,
    surface_noise_mm: float = 3.0,
    edge_width_px: int = 2,
    seed: int = 0,
):
    """Build (depth_stack, fg_mask, edge_mask).

    A foreground disc sits at fg_mm against a background at bg_mm. Stable
    surfaces carry Gaussian sensor noise. Pixels in a thin annulus straddling
    the disc boundary flicker: each frame each edge pixel is independently
    foreground or background (50/50) — exactly the real failure mode.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.0, w / 2.0
    radius = min(h, w) * 0.28
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)

    fg_mask = dist < (radius - edge_width_px)
    edge_mask = np.abs(dist - radius) <= edge_width_px

    stack = np.zeros((n_frames, h, w), dtype=np.uint16)
    for i in range(n_frames):
        frame = np.where(
            dist < radius, fg_mm, bg_mm
        ).astype(np.float32)
        frame += rng.normal(0.0, surface_noise_mm, (h, w))
        # Edge pixels flicker between the two depths
        flicker = rng.random((h, w)) < 0.5
        frame[edge_mask & flicker] = fg_mm + rng.normal(0, surface_noise_mm)
        frame[edge_mask & ~flicker] = bg_mm + rng.normal(0, surface_noise_mm)
        stack[i] = frame.clip(1, 65535).astype(np.uint16)

    return stack, fg_mask, edge_mask


def cmd_synth(out_path: str):
    stack, fg_mask, edge_mask = make_synthetic_stack()
    rgb = np.zeros((*stack.shape[1:], 3), dtype=np.uint8)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        depth_stack=stack,
        rgb=rgb,
        fg_mask=fg_mask,
        edge_mask=edge_mask,
        synthetic=np.bool_(True),
    )
    print(f"Wrote synthetic raw stack → {out_path}")
    print(
        f"  {stack.shape[0]} frames, {stack.shape[2]}x{stack.shape[1]}, "
        f"{int(edge_mask.sum())} flickering edge px"
    )


# ---------------------------------------------------------------------------
# replay: A/B plain mean vs variance-gated averaging on a raw stack
# ---------------------------------------------------------------------------
def plain_mean(frames):
    """Per-pixel mean of valid (>0) samples — the un-gated baseline."""
    h, w = frames[0].shape[:2]
    sums = np.zeros((h, w), np.float32)
    counts = np.zeros((h, w), np.float32)
    for f in frames:
        valid = f > 0
        sums += np.where(valid, f.astype(np.float32), 0.0)
        counts += valid.astype(np.float32)
    return (sums / np.maximum(counts, 1.0)).astype(np.uint16)


def cmd_replay(npz_path: str, std_threshold_mm: float = 40.0):
    data = np.load(npz_path, allow_pickle=True)
    if "depth_stack" not in data.files:
        print(f"ERROR: {npz_path} has no 'depth_stack' — not a raw stack.")
        print(f"  (found: {data.files})")
        return 1
    stack = data["depth_stack"]
    frames = [stack[i] for i in range(stack.shape[0])]
    print(f"Loaded raw stack: {stack.shape[0]} frames, {stack.shape[2]}x{stack.shape[1]}")

    baseline = plain_mean(frames)
    gated, std, counts = variance_gated_average(
        frames, std_threshold_mm=std_threshold_mm
    )

    removed = (baseline > 0) & (gated == 0)
    n_removed = int(removed.sum())
    print(f"\nstd gate threshold: {std_threshold_mm:.0f} mm")
    print(f"  plain-mean valid px : {int((baseline > 0).sum())}")
    print(f"  gated valid px      : {int((gated > 0).sum())}")
    print(f"  px removed by gating: {n_removed}")
    if n_removed:
        removed_depths = baseline[removed].astype(float)
        print(
            f"  removed-px depth    : {removed_depths.min():.0f}–"
            f"{removed_depths.max():.0f} mm "
            f"(mean {removed_depths.mean():.0f} — phantom mid-depths)"
        )

    # Ground-truth scoring when the stack is synthetic
    if "edge_mask" in data.files:
        edge = data["edge_mask"]
        true_pos = int((removed & edge).sum())
        false_pos = int((removed & ~edge).sum())
        total_edge = int(edge.sum())
        recall = true_pos / total_edge if total_edge else 0.0
        precision = true_pos / n_removed if n_removed else 0.0
        print("\nground truth (synthetic):")
        print(f"  flickering edge px      : {total_edge}")
        print(f"  recall  (edge removed)  : {recall:.1%}  ({true_pos}/{total_edge})")
        print(f"  precision (removed=edge): {precision:.1%}  ({true_pos}/{n_removed})")

        # The key result: phantom points in the baseline vs the gated output.
        # A "phantom" is a pixel whose averaged depth sits in the empty gap
        # between the foreground and background bands.
        fg_mask = data["fg_mask"]
        if fg_mask.any():
            fg_band = baseline[fg_mask]
            fg_band = fg_band[fg_band > 0]
            fg_hi = np.percentile(fg_band, 99) + 50.0  # top of foreground band
        else:
            fg_hi = 600.0
        gap_lo, gap_hi = fg_hi, 1400.0

        def phantoms(depth_map):
            d = depth_map[edge]
            return int(np.count_nonzero((d > gap_lo) & (d < gap_hi)))

        print(f"\nphantom edge points (depth in {gap_lo:.0f}–{gap_hi:.0f} mm gap):")
        print(f"  plain mean : {phantoms(baseline)}")
        print(f"  variance-gated : {phantoms(gated)}")
        if phantoms(baseline) and phantoms(gated) == 0:
            print("  → PASS: gating eliminated all phantom edge points")
        elif phantoms(gated) < phantoms(baseline):
            print("  → PARTIAL: gating reduced but did not eliminate phantoms")
        else:
            print("  → FAIL: gating did not reduce phantoms")
    return 0


# ---------------------------------------------------------------------------
# analyze: skirt-symptom check on an already-exported point cloud
# ---------------------------------------------------------------------------
def load_cloud_z(path: str):
    """Return the Z (depth) values of a point cloud from .ply or .npz."""
    p = Path(path)
    if p.suffix == ".npz":
        data = np.load(path, allow_pickle=True)
        pts = data["points"]
        return np.asarray(pts, dtype=float)[:, 2]
    # ASCII PLY: skip header, read x y z ...
    zs = []
    with open(path) as f:
        in_body = False
        for line in f:
            if not in_body:
                if line.strip() == "end_header":
                    in_body = True
                continue
            parts = line.split()
            if len(parts) >= 3:
                zs.append(float(parts[2]))
    return np.array(zs)


def cmd_analyze(cloud_path: str):
    z_raw = load_cloud_z(cloud_path)
    if len(z_raw) == 0:
        print(f"ERROR: no points in {cloud_path}")
        return 1
    print(f"Loaded {len(z_raw)} points from {cloud_path}")

    findings = []

    # Saturated / invalid depths. Nothing on a tabletop is past a few metres;
    # values near the uint16 ceiling are unfilled-depth garbage in the export.
    SANE_MAX = 4000.0  # mm (cloud Z may be mm or m — see scale check below)
    unit = "mm"
    if np.median(np.abs(z_raw)) < 10.0:
        unit = "m"
        SANE_MAX = 4.0
    saturated = np.count_nonzero(np.abs(z_raw) > SANE_MAX)
    if saturated:
        findings.append(
            f"{saturated} points beyond {SANE_MAX:.0f}{unit} — saturated/invalid "
            f"depth leaking into the export (filter these at export time)"
        )
    z = z_raw[np.abs(z_raw) <= SANE_MAX]
    if len(z) == 0:
        print("  All points are saturated/invalid — nothing to analyze.")
        for f in findings:
            print(f"  ! {f}")
        return 0

    med = np.median(z)
    q1, q3 = np.percentile(z, [25, 75])
    iqr = q3 - q1
    print(f"  Z median      : {med:.3f} {unit}")
    print(f"  Z IQR         : {iqr:.3f}  ({q1:.3f}–{q3:.3f})")
    print(f"  Z range (sane): {z.min():.3f}–{z.max():.3f}")

    # Text histogram over the sane range
    print("\n  Z histogram (sane-range points):")
    hist, edges = np.histogram(z, bins=24)
    peak = hist.max()
    for i, c in enumerate(hist):
        bar = "#" * int(40 * c / peak) if peak else ""
        print(f"   {edges[i]:8.2f} | {bar} {c}")

    # Gap / secondary-cluster detection: a compact object fills one contiguous
    # band; a skirt or background bleed shows as a populated region separated
    # from the main mode by empty bins.
    populated = hist > (0.005 * len(z))  # ignore trace noise bins
    main_bin = int(np.argmax(hist))
    # Walk outward from the main peak; the first empty bin ends the core band.
    lo = main_bin
    while lo > 0 and populated[lo - 1]:
        lo -= 1
    hi = main_bin
    while hi < len(hist) - 1 and populated[hi + 1]:
        hi += 1
    secondary = int(hist[:lo].sum() + hist[hi + 1:].sum())
    if secondary > 0.01 * len(z):
        core_lo, core_hi = edges[lo], edges[hi + 1]
        findings.append(
            f"{secondary} points ({100.0 * secondary / len(z):.1f}%) sit outside "
            f"the main band [{core_lo:.0f}, {core_hi:.0f}] {unit}, separated by a "
            f"gap — a discontinuity skirt or background bleed"
        )

    print()
    if findings:
        print("  → Discontinuity symptom(s) found:")
        for f in findings:
            print(f"    ! {f}")
    else:
        print("  → Cloud looks compact in Z; no skirt by these metrics.")
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "synth":
        cmd_synth(path)
        return 0
    if mode == "replay":
        thr = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
        return cmd_replay(path, std_threshold_mm=thr)
    if mode == "analyze":
        return cmd_analyze(path)
    print(f"Unknown mode '{mode}'. Use: synth | replay | analyze")
    return 1


if __name__ == "__main__":
    sys.exit(main())
