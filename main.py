"""
Main simulation runner for ARQ protocol analysis.
"""

import csv
import os
from datetime import datetime
import argparse

from simulator import run_simulation
import config


def run_parameter_sweep(file_size=None, num_runs=None, output_dir='results'):
    """
    Run simulation for all parameter combinations.

    Args:
        file_size: File size to use (default: TEST_FILE_SIZE)
        num_runs: Number of runs per configuration (default: from config)
        output_dir: Directory to save results

    Returns:
        list: List of result dictionaries
    """
    if file_size is None:
        file_size = config.TEST_FILE_SIZE

    if num_runs is None:
        num_runs = config.NUM_RUNS

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get all configurations
    configs_list = config.get_all_configs()
    total_configs = len(configs_list)

    print(f"Running ARQ simulation parameter sweep")
    print(f"File size: {file_size / 1024:.1f} KB ({file_size} bytes)")
    print(f"Configurations: {total_configs}")
    print(f"Runs per config: {num_runs}")
    print(f"Total simulations: {total_configs * num_runs}")
    print("-" * 60)

    all_results = []

    for idx, cfg in enumerate(configs_list, 1):
        window_size = cfg['window_size']
        frame_size = cfg['frame_size']

        print(f"[{idx}/{total_configs}] W={window_size:3d}, L={frame_size:4d} bytes ... ", end='', flush=True)

        # Run simulation
        results = run_simulation(
            window_size=window_size,
            frame_size=frame_size,
            file_size=file_size,
            seed=config.RANDOM_SEED,
            num_runs=num_runs
        )

        all_results.append(results)

        # Print summary
        goodput_kbps = results['goodput_kbps']
        efficiency = results['efficiency'] * 100
        print(f"Goodput: {goodput_kbps:7.2f} Kbps, Efficiency: {efficiency:5.2f}%")

    print("-" * 60)
    print(f"Completed all {total_configs} configurations")

    # Save results to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(output_dir, f'results_{timestamp}.csv')
    save_results_to_csv(all_results, csv_filename)
    print(f"Results saved to: {csv_filename}")

    return all_results


def save_results_to_csv(results, filename):
    """
    Save simulation results to CSV file.

    Args:
        results: List of result dictionaries
        filename: Output CSV filename
    """
    if not results:
        print("No results to save")
        return

    # Define CSV columns
    columns = [
        'window_size', 'frame_size', 'file_size',
        'simulation_time_sec', 'frames_sent', 'frames_received',
        'frames_retransmitted', 'retransmission_rate',
        'throughput_bps', 'goodput_bps', 'goodput_kbps', 'goodput_mbps',
        'efficiency', 'average_channel_ber'
    ]

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} results to {filename}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='ARQ Simulation Runner')
    parser.add_argument('--file-size', type=int, help='File size in bytes (default: 100KB for test)')
    parser.add_argument('--full', action='store_true', help='Use full 10MB file size')
    parser.add_argument('--num-runs', type=int, default=config.NUM_RUNS,
                        help=f'Number of runs per configuration (default: {config.NUM_RUNS})')
    parser.add_argument('--window-size', type=int, help='Single window size to test')
    parser.add_argument('--frame-size', type=int, help='Single frame size to test')
    parser.add_argument('--output-dir', default='results', help='Output directory for results')

    args = parser.parse_args()

    # Determine file size
    if args.file_size:
        file_size = args.file_size
    elif args.full:
        file_size = config.FULL_FILE_SIZE
    else:
        file_size = config.TEST_FILE_SIZE

    # Single configuration or full sweep?
    if args.window_size and args.frame_size:
        # Single configuration
        print(f"Running single configuration:")
        print(f"Window size: {args.window_size}")
        print(f"Frame size: {args.frame_size} bytes")
        print(f"File size: {file_size / 1024:.1f} KB")
        print(f"Runs: {args.num_runs}")
        print("-" * 60)

        results = run_simulation(
            window_size=args.window_size,
            frame_size=args.frame_size,
            file_size=file_size,
            seed=config.RANDOM_SEED,
            num_runs=args.num_runs
        )

        # Print detailed results
        print("\nResults:")
        print(f"  Simulation time: {results['simulation_time_sec']:.3f} seconds")
        print(f"  Frames sent: {results['frames_sent']}")
        print(f"  Frames received: {results['frames_received']}")
        print(f"  Retransmissions: {results['frames_retransmitted']} ({results['retransmission_rate']*100:.2f}%)")
        print(f"  Throughput: {results['goodput_kbps']:.2f} Kbps")
        print(f"  Efficiency: {results['efficiency']*100:.2f}%")
        print(f"  Channel BER: {results['average_channel_ber']:.2e}")

        # Save single result
        os.makedirs(args.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(args.output_dir, f'result_single_{timestamp}.csv')
        save_results_to_csv([results], csv_filename)

    else:
        # Full parameter sweep
        run_parameter_sweep(
            file_size=file_size,
            num_runs=args.num_runs,
            output_dir=args.output_dir
        )


if __name__ == '__main__':
    main()
