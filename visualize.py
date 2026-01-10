"""
Visualization module for ARQ simulation results.
"""

import csv
import os
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.colors import LogNorm


def load_results_from_csv(filename):
    """
    Load simulation results from CSV file.

    Args:
        filename: CSV file path

    Returns:
        list: List of result dictionaries
    """
    results = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            for key in row:
                try:
                    if '.' in row[key] or 'e' in row[key].lower():
                        row[key] = float(row[key])
                    else:
                        row[key] = int(row[key])
                except (ValueError, AttributeError):
                    pass
            results.append(row)
    return results


def create_heatmap(results, metric='goodput_kbps', title=None, output_file=None):
    """
    Create a heatmap of results.

    Args:
        results: List of result dictionaries
        metric: Metric to plot (default: 'goodput_kbps')
        title: Plot title
        output_file: Path to save figure (if None, display only)
    """
    # Extract unique window sizes and frame sizes
    window_sizes = sorted(set(r['window_size'] for r in results))
    frame_sizes = sorted(set(r['frame_size'] for r in results))

    # Create matrix
    matrix = np.zeros((len(window_sizes), len(frame_sizes)))

    for r in results:
        w_idx = window_sizes.index(r['window_size'])
        f_idx = frame_sizes.index(r['frame_size'])
        matrix[w_idx, f_idx] = r[metric]

    # Create figure
    plt.figure(figsize=(12, 8))

    # Create heatmap
    sns.heatmap(
        matrix,
        annot=True,
        fmt='.1f',
        cmap='YlOrRd',
        xticklabels=frame_sizes,
        yticklabels=window_sizes,
        cbar_kws={'label': metric}
    )

    plt.xlabel('Frame Size (bytes)', fontsize=12)
    plt.ylabel('Window Size', fontsize=12)

    if title:
        plt.title(title, fontsize=14)
    else:
        plt.title(f'{metric} Heatmap', fontsize=14)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved heatmap to {output_file}")
    else:
        plt.show()

    plt.close()


def plot_efficiency_comparison(results, output_file=None):
    """
    Plot efficiency for different configurations.

    Args:
        results: List of result dictionaries
        output_file: Path to save figure
    """
    # Group by window size
    window_sizes = sorted(set(r['window_size'] for r in results))

    plt.figure(figsize=(12, 6))

    for w in window_sizes:
        w_results = [r for r in results if r['window_size'] == w]
        w_results.sort(key=lambda x: x['frame_size'])

        frame_sizes = [r['frame_size'] for r in w_results]
        efficiency = [r['efficiency'] * 100 for r in w_results]

        plt.plot(frame_sizes, efficiency, marker='o', label=f'W={w}')

    plt.xlabel('Frame Size (bytes)', fontsize=12)
    plt.ylabel('Efficiency (%)', fontsize=12)
    plt.title('Protocol Efficiency vs Frame Size', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xscale('log', base=2)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved efficiency plot to {output_file}")
    else:
        plt.show()

    plt.close()


def plot_goodput_vs_window(results, output_file=None):
    """
    Plot goodput vs window size for different frame sizes.

    Args:
        results: List of result dictionaries
        output_file: Path to save figure
    """
    # Group by frame size
    frame_sizes = sorted(set(r['frame_size'] for r in results))

    plt.figure(figsize=(12, 6))

    for f in frame_sizes:
        f_results = [r for r in results if r['frame_size'] == f]
        f_results.sort(key=lambda x: x['window_size'])

        window_sizes = [r['window_size'] for r in f_results]
        goodput = [r['goodput_kbps'] for r in f_results]

        plt.plot(window_sizes, goodput, marker='o', label=f'L={f} bytes')

    plt.xlabel('Window Size', fontsize=12)
    plt.ylabel('Goodput (Kbps)', fontsize=12)
    plt.title('Goodput vs Window Size', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xscale('log', base=2)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved goodput plot to {output_file}")
    else:
        plt.show()

    plt.close()


def generate_all_plots(csv_file, output_dir=None):
    """
    Generate all visualization plots from a CSV file.

    Args:
        csv_file: Path to CSV results file
        output_dir: Directory to save plots (if None, use same dir as CSV)
    """
    # Load results
    results = load_results_from_csv(csv_file)

    if not results:
        print("No results found in CSV")
        return

    # Determine output directory
    if output_dir is None:
        output_dir = os.path.dirname(csv_file)

    os.makedirs(output_dir, exist_ok=True)

    # Base filename
    base_name = os.path.splitext(os.path.basename(csv_file))[0]

    # Generate plots
    print(f"Generating plots from {csv_file}...")

    # Goodput heatmap
    create_heatmap(
        results,
        metric='goodput_kbps',
        title='Goodput (Kbps) - Window Size vs Frame Size',
        output_file=os.path.join(output_dir, f'{base_name}_goodput_heatmap.png')
    )

    # Efficiency heatmap
    create_heatmap(
        results,
        metric='efficiency',
        title='Protocol Efficiency - Window Size vs Frame Size',
        output_file=os.path.join(output_dir, f'{base_name}_efficiency_heatmap.png')
    )

    # Efficiency comparison
    plot_efficiency_comparison(
        results,
        output_file=os.path.join(output_dir, f'{base_name}_efficiency_comparison.png')
    )

    # Goodput vs window size
    plot_goodput_vs_window(
        results,
        output_file=os.path.join(output_dir, f'{base_name}_goodput_vs_window.png')
    )

    print(f"All plots saved to {output_dir}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize.py <csv_file> [output_dir]")
        sys.exit(1)

    csv_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    generate_all_plots(csv_file, output_dir)
