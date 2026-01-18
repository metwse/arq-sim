use arq_sim::{simulate_arq, SimulationStats};
use dotenvy::dotenv;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

// CLI argument parsing
use clap::{Parser, Subcommand};
use std::path::PathBuf;

// Parallel execution
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;

// CSV export
use std::fs::File;
use std::io::Write;

/// ARQ Simulation with parameter search capability
#[derive(Parser)]
#[command(name = "arq-sim")]
#[command(about = "Selective-Repeat ARQ Protocol Simulator", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a single simulation
    Single {
        /// Window size (number of frames)
        #[arg(short, long)]
        window_size: u64,

        /// Frame payload size in bytes
        #[arg(short = 'l', long)]
        frame_payload: u64,
    },

    /// Run parameter space search
    Search {
        /// Window sizes to test (comma-separated)
        #[arg(long, value_delimiter = ',')]
        window_sizes: Option<Vec<u64>>,

        /// Frame payload sizes to test (comma-separated)
        #[arg(long, value_delimiter = ',')]
        frame_payloads: Option<Vec<u64>>,

        /// Number of runs per (W, L) pair
        #[arg(long, default_value = "10")]
        num_runs: usize,

        /// Enable parallel execution
        #[arg(long)]
        parallel: bool,

        /// Output CSV file path
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

/// Default window sizes from HW2 specification
const DEFAULT_WINDOW_SIZES: &[u64] = &[2, 4, 8, 16, 32, 64];

/// Default frame payload sizes from HW2 specification
const DEFAULT_FRAME_PAYLOADS: &[u64] = &[128, 256, 512, 1024, 2048, 4096];

fn main() {
    dotenv().ok();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| format!("{}=error", env!("CARGO_CRATE_NAME")).into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Single {
            window_size,
            frame_payload,
        }) => {
            run_single_simulation(window_size, frame_payload);
        }
        Some(Commands::Search {
            window_sizes,
            frame_payloads,
            num_runs,
            parallel,
            output,
        }) => {
            run_parameter_search(window_sizes, frame_payloads, num_runs, parallel, output);
        }
        None => {
            // Default behavior: run single simulation
            println!("Running default simulation (W=2048, L=256)...");
            run_single_simulation(2048, 256);
        }
    }
}

fn run_single_simulation(window_size: u64, frame_payload: u64) {
    println!("Running simulation:");
    println!("  Window size: {}", window_size);
    println!("  Frame payload: {} bytes", frame_payload);
    println!();

    let stats = simulate_arq(window_size, frame_payload);

    println!("Results:");
    println!("  Goodput: {:.6} Mbps", stats.goodput / 1_000_000.0);
    println!("  Retransmissions: {}", stats.retransmissions);
    println!("  Time: {:.3} s", stats.time);
}

fn run_parameter_search(
    window_sizes: Option<Vec<u64>>,
    frame_payloads: Option<Vec<u64>>,
    num_runs: usize,
    parallel: bool,
    output: Option<PathBuf>,
) {
    // Use defaults if not specified
    let window_sizes = window_sizes.unwrap_or_else(|| DEFAULT_WINDOW_SIZES.to_vec());
    let frame_payloads = frame_payloads.unwrap_or_else(|| DEFAULT_FRAME_PAYLOADS.to_vec());

    println!("Parameter Search Configuration:");
    println!("  Window sizes: {:?}", window_sizes);
    println!("  Frame payloads: {:?}", frame_payloads);
    println!("  Runs per combination: {}", num_runs);
    println!("  Parallel: {}", parallel);
    println!();

    // Generate all combinations
    let mut params: Vec<(u64, u64, usize)> = Vec::new();
    for &w in &window_sizes {
        for &l in &frame_payloads {
            for run in 0..num_runs {
                params.push((w, l, run));
            }
        }
    }

    let total = params.len();
    println!("Total simulations: {}", total);
    println!();

    // Create progress bar
    let pb = ProgressBar::new(total as u64);
    pb.set_style(
        ProgressStyle::default_bar()
            .template("[{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} ({eta})")
            .unwrap()
            .progress_chars("#>-"),
    );

    // Run simulations
    let results: Vec<(u64, u64, usize, SimulationStats)> = if parallel {
        params
            .par_iter()
            .map(|&(w, l, run)| {
                let stats = simulate_arq(w, l);
                pb.inc(1);
                (w, l, run, stats)
            })
            .collect()
    } else {
        params
            .iter()
            .map(|&(w, l, run)| {
                let stats = simulate_arq(w, l);
                pb.inc(1);
                (w, l, run, stats)
            })
            .collect()
    };

    pb.finish_with_message("Complete!");
    println!();

    // Calculate average goodput for each (W, L) pair
    let mut avg_goodput: std::collections::HashMap<(u64, u64), Vec<f64>> =
        std::collections::HashMap::new();

    for (w, l, _run, stats) in &results {
        avg_goodput
            .entry((*w, *l))
            .or_default()
            .push(stats.goodput / 1_000_000.0); // Convert to Mbps
    }

    // Find optimal
    let mut best_w = 0;
    let mut best_l = 0;
    let mut best_goodput = 0.0;

    for ((w, l), goodputs) in &avg_goodput {
        let avg: f64 = goodputs.iter().sum::<f64>() / goodputs.len() as f64;
        if avg > best_goodput {
            best_goodput = avg;
            best_w = *w;
            best_l = *l;
        }
    }

    println!("{}", "=".repeat(70));
    println!("OPTIMAL PARAMETERS");
    println!("{}", "=".repeat(70));
    println!("  Window Size (W): {}", best_w);
    println!("  Frame Payload (L): {} bytes", best_l);
    println!("  Average Goodput: {:.6} Mbps", best_goodput);
    println!("{}", "=".repeat(70));
    println!();

    // Export to CSV if requested
    if let Some(output_path) = output {
        export_to_csv(&results, &output_path);
    }
}

fn export_to_csv(results: &[(u64, u64, usize, SimulationStats)], path: &PathBuf) {
    let mut file = File::create(path).expect("Failed to create CSV file");

    // Write header
    writeln!(
        file,
        "window_size,frame_payload,run,goodput_mbps,retransmissions,time_seconds"
    )
    .expect("Failed to write header");

    // Write data
    for (w, l, run, stats) in results {
        writeln!(
            file,
            "{},{},{},{:.6},{},{:.6}",
            w,
            l,
            run,
            stats.goodput / 1_000_000.0,
            stats.retransmissions,
            stats.time
        )
        .expect("Failed to write row");
    }

    println!("Results exported to: {}", path.display());
}
