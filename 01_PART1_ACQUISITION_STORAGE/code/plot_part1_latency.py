#!/usr/bin/env python3
"""Draw Part1 latency from an explicitly supplied archived summary CSV.

Whiskers are observed min/max, not confidence intervals. No benchmark is run.
Matplotlib is loaded only after CLI and output-isolation checks.
Sources: original recorded plotting script; AI assistance: ChatGPT8November2026,
CLI/output isolation repair with OpenAI Codex18November2026.
"""
from pathlib import Path
import argparse
import csv
import os

REPO_ROOT = Path(__file__).resolve().parents[2]


def plot_recorded_summary(summary: Path, out: Path):
    summary = summary.expanduser().resolve()
    out = out.expanduser().resolve()
    if not summary.is_file():
        raise FileNotFoundError('Explicit recorded benchmark summary CSV is missing: ' + str(summary))
    if out.exists():
        raise ValueError('Output directory already exists; choose a NEW external --out directory.')
    if out.is_relative_to(REPO_ROOT) or REPO_ROOT.is_relative_to(out):
        raise ValueError('Output must be outside the submission source repository.')
    if out.is_relative_to(summary.parent) or summary.is_relative_to(out):
        raise ValueError('Output and the source CSV directory must be separate.')
    with summary.open(encoding='utf-8-sig', newline='') as stream:
        data = {(row['variant'], row['query']): row for row in csv.DictReader(stream)}
    # Matplotlib font/config writes, as well as the figure, stay in the NEW output.
    out.mkdir(parents=True, exist_ok=False)
    os.environ['MPLCONFIGDIR'] = str(out / 'matplotlib_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    variants = ['csv_uncompressed', 'parquet_snappy', 'parquet_zstd', 'parquet_zstd_by_year', 'parquet_zstd_by_quarter']
    labels = ['CSV', 'Snappy', 'ZSTD single', 'ZSTD year', 'ZSTD quarter']
    colors = ['#6B7280', '#297A8A', '#23529C', '#A86D14', '#805AA0']
    hatches = ['', '//', '', '..', 'xx']
    queries = ['all_rows_all_columns', 'all_rows_six_columns', 'one_year_six_columns', 'one_quarter_six_columns']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.labelsize': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(7.0, 2.65), layout='constrained')
    width = 0.15
    for j, (v, label, color, hatch) in enumerate(zip(variants, labels, colors, hatches)):
        values = [float(data[(v, q)]['median_seconds']) for q in queries]
        low = [v0-float(data[(v, q)]['min_seconds']) for v0, q in zip(values, queries)]
        high = [float(data[(v, q)]['max_seconds'])-v0 for v0, q in zip(values, queries)]
        x = [i+(j-2)*width for i in range(4)]
        ax.bar(x, values, width=width, label=label, color=color, edgecolor='white', linewidth=0.4,
               hatch=hatch, yerr=[low, high], error_kw={'elinewidth': 0.7, 'capsize': 1.8, 'ecolor': '#202020'}, zorder=3)
    ax.set_xticks(range(4), ['All rows\n33 columns', 'All rows\n6 columns', '2023\n6 columns', '2023Q1\n6 columns'])
    ax.set_ylabel('Latency (seconds)')
    ax.set_ylim(0, 1.48)
    ax.set_yticks([0, .3, .6, .9, 1.2])
    ax.grid(axis='y', alpha=.20, zorder=0)
    ax.legend(ncol=5, loc='upper center', bbox_to_anchor=(.5, 1.15), frameon=False, fontsize=8.1, handlelength=1.5, columnspacing=1.2)
    fig.savefig(out/'part1_latency.png', dpi=300, facecolor='white')
    plt.close(fig)
    print(out/'part1_latency.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True,
                        help='Explicit archived benchmark_summary.csv; no new measurements are generated.')
    parser.add_argument('--out', type=Path, required=True,
                        help='NEW output directory outside the repository and source CSV directory.')
    args = parser.parse_args()
    plot_recorded_summary(args.summary, args.out)


if __name__ == '__main__':
    main()
