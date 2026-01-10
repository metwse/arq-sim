# ARQ Simulator

A comprehensive Selective Repeat ARQ (Automatic Repeat Request) protocol simulator with asymmetric propagation delays and Gilbert-Elliot burst error channel model.

## Features

- **Selective Repeat ARQ Protocol**: Full implementation with configurable window sizes
- **Asymmetric Delays**: Realistic forward (40ms) and reverse (10ms) path delays
- **Gilbert-Elliot Channel**: Burst error modeling with two-state Markov chain
- **Event-Driven Simulation**: Accurate timing and event handling
- **Comprehensive Metrics**: Throughput, goodput, efficiency, retransmission rates
- **Parameter Sweep**: Automated testing across multiple configurations
- **Visualization**: Heatmaps and performance plots

## Simulation Parameters

### Timing
- **Forward path delay** (Data frames): 40 ms
- **Reverse path delay** (ACK frames): 10 ms
- **Processing delay** (per frame): 2 ms

### Gilbert-Elliot Channel Model
- **Good-state BER** (pg): 1 × 10⁻⁶
- **Bad-state BER** (pb): 5 × 10⁻³
- **Transition P(G → B)**: 0.002
- **Transition P(B → G)**: 0.05
- **Average target BER**: ≈ 1 × 10⁻⁴

### Protocol Parameters
- **Window sizes (W)**: {2, 4, 8, 16, 32, 64}
- **Frame payload sizes (L)**: {128, 256, 512, 1024, 2048, 4096} bytes
- **Frame header**: 20 bytes

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd arq-sim
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Test (Single Configuration)
```bash
# Test with W=8, L=512 bytes
python main.py --window-size 8 --frame-size 512
```

### Parameter Sweep (Small File - 100KB)
```bash
# Run all configurations with 100KB test file
python main.py
```

### Full Simulation (10MB File)
```bash
# Run all configurations with 10MB file
python main.py --full
```

### Custom Parameters
```bash
# Custom file size and number of runs
python main.py --file-size 1048576 --num-runs 10

# Specify output directory
python main.py --output-dir my_results
```

### Generate Visualizations
```bash
# Generate plots from results CSV
python visualize.py results/results_20260110_123456.csv
```

## Output

### CSV Results
Results are saved in the `results/` directory with columns:
- `window_size`, `frame_size`, `file_size`
- `simulation_time_sec`
- `frames_sent`, `frames_received`, `frames_retransmitted`
- `retransmission_rate`
- `throughput_bps`, `goodput_kbps`, `goodput_mbps`
- `efficiency`
- `average_channel_ber`

### Visualizations
Generated plots include:
- **Goodput heatmap**: Window size vs frame size
- **Efficiency heatmap**: Protocol efficiency across configurations
- **Efficiency comparison**: Line plots for each window size
- **Goodput vs window size**: Performance trends

## Project Structure

```
arq-sim/
├── channel.py          # Gilbert-Elliot channel model
├── config.py           # Configuration parameters
├── simulator.py        # Event-driven ARQ simulator
├── metrics.py          # Performance metrics calculation
├── main.py             # Main simulation runner
├── visualize.py        # Result visualization
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Example Output

```
Running ARQ simulation parameter sweep
File size: 100.0 KB (102400 bytes)
Configurations: 36
Runs per config: 5
Total simulations: 180
------------------------------------------------------------
[1/36] W=  2, L= 128 bytes ... Goodput:   45.23 Kbps, Efficiency: 78.45%
[2/36] W=  2, L= 256 bytes ... Goodput:   67.89 Kbps, Efficiency: 82.10%
...
```

## Performance Metrics

- **Throughput**: Total bits transmitted per second (including retransmissions)
- **Goodput**: Successfully delivered bits per second (payload only)
- **Efficiency**: Ratio of goodput to throughput (0-1)
- **Retransmission Rate**: Ratio of retransmitted frames to total frames sent

## License

See LICENSE file for details.
