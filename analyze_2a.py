#!/usr/bin/env python3
"""Analyze baseline LRU vs Task 2A I-RRIP ChampSim logs."""

from pathlib import Path
import argparse
import csv
import re
import sys

import matplotlib.pyplot as plt

TRACE_ORDER = ["Trace1", "Trace2", "Trace3"]


def number_after(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def parse_log(path):
    text = path.read_text(errors="replace")
    # ChampSim versions differ slightly in whitespace and punctuation.
    ipc = number_after([
        r"CPU\s*0\s+cumulative\s+IPC\s*:\s*([0-9.eE+-]+)",
        r"cumulative\s+IPC\s*:\s*([0-9.eE+-]+)",
    ], text)

    # Typical ChampSim summary line: L2C LOAD ACCESS: ... MPKI: 19.0036
    # Keep LOAD MPKI and TOTAL MPKI as separate metrics: they are not interchangeable.
    l2_load = number_after([
        r"L2C\s+LOAD\s+ACCESS[^\n]*?MPKI\s*:\s*([0-9.eE+-]+)",
        r"L2C[^\n]*LOAD[^\n]*MPKI\s*:\s*([0-9.eE+-]+)",
    ], text)

    instr = number_after([
        r"L2C\s+INSTRUCTION\s+LOAD\s+MPKI\s*:\s*([0-9.eE+-]+)",
        r"L2C[^\n]*INSTRUCTION[^\n]*MPKI\s*:\s*([0-9.eE+-]+)",
        r"L2\s+Instruction\s+Load\s+MPKI\s*:\s*([0-9.eE+-]+)",
    ], text)

    data = number_after([
        r"L2C\s+DATA\s+LOAD\s+MPKI\s*:\s*([0-9.eE+-]+)",
        r"L2C[^\n]*DATA[^\n]*MPKI\s*:\s*([0-9.eE+-]+)",
        r"L2\s+Data\s+Load\s+MPKI\s*:\s*([0-9.eE+-]+)",
    ], text)

    # Fallback: derive instruction/data MPKI from common ChampSim stat names
    if instr is None:
        instr = number_after([
            r"L2C\s+LOAD\s+INSTRUCTION\s+MPKI\s*:\s*([0-9.eE+-]+)",
            r"instruction\s+load[^\n]*MPKI\s*:\s*([0-9.eE+-]+)",
        ], text)
    if data is None:
        data = number_after([
            r"L2C\s+LOAD\s+DATA\s+MPKI\s*:\s*([0-9.eE+-]+)",
            r"data\s+load[^\n]*MPKI\s*:\s*([0-9.eE+-]+)",
        ], text)

    return {"ipc": ipc, "l2c_load_mpki": l2_load,
            "l2_instruction_load_mpki": instr, "l2_data_load_mpki": data}


def trace_from_name(name):
    m = re.search(r"trace\s*([123])(?:-\d+)?", name, re.IGNORECASE)
    return f"Trace{m.group(1)}" if m else None


def policy_from_name(name):
    low = name.lower()
    if "baseline" in low:
        return "Baseline LRU"
    if "irrip" in low or "task2a" in low:
        return "I-RRIP"
    return None


def discover(input_dir):
    files = sorted(p for p in input_dir.rglob("*.txt") if p.is_file())
    rows = []
    for path in files:
        trace = trace_from_name(path.name)
        policy = policy_from_name(path.name)
        if not trace or not policy:
            continue
        metrics = parse_log(path)
        rows.append({"trace": trace, "policy": policy,
                     **metrics, "source_log": str(path)})
    return rows, files


def write_plot(rows, key, title, ylabel, outpath):
    traces = TRACE_ORDER
    baseline, irrip = [], []
    for trace in traces:
        pair = {(r["policy"]): r for r in rows if r["trace"] == trace}
        b = pair.get("Baseline LRU", {}).get(key)
        i = pair.get("I-RRIP", {}).get(key)
        if key == "speedup":
            baseline.append(1.0 if b is not None else float("nan"))
            irrip.append(i / b if b not in (None, 0) and i is not None else float("nan"))
        else:
            baseline.append(b if b is not None else float("nan"))
            irrip.append(i if i is not None else float("nan"))

    x = list(range(len(traces)))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars1 = ax.bar([v - width / 2 for v in x], baseline, width, label="Baseline LRU")
    bars2 = ax.bar([v + width / 2 for v in x], irrip, width, label="I-RRIP")
    ax.set_xticks(x, traces)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    # Show the exact numeric value above every bar.
    for bar in list(bars1) + list(bars2):
        height = bar.get_height()
        if height == height:  # not NaN
            ax.annotate(f"{height:.4g}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, rotation=0)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="results_2a_comparison",
                        help="Folder containing the six ChampSim .txt logs")
    parser.add_argument("--output", default="analysis_2a_comparison",
                        help="Folder for CSV, report, and plots")
    args = parser.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    if not input_dir.is_dir():
        sys.exit(f"ERROR: input folder does not exist: {input_dir}")

    rows, all_txt = discover(input_dir)
    if not rows:
        print(f"ERROR: found {len(all_txt)} .txt file(s) under {input_dir},")
        print("but none matched the expected names (baseline_LRU_Trace1.txt, task2A_IRRIP_Trace1.txt, etc.).")
        if all_txt:
            print("Found .txt files:")
            for p in all_txt:
                print("  ", p.name)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "task2a_comparison.csv"
    fields = ["trace", "policy", "ipc", "speedup", "l2c_load_mpki",
              "l2_instruction_load_mpki", "l2_data_load_mpki", "source_log"]

    # Calculate speedup against baseline for each trace.
    baseline_ipc = {r["trace"]: r["ipc"] for r in rows if r["policy"] == "Baseline LRU"}
    for row in rows:
        b = baseline_ipc.get(row["trace"])
        row["speedup"] = row["ipc"] / b if row["ipc"] is not None and b not in (None, 0) else None

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (TRACE_ORDER.index(r["trace"]), r["policy"])):
            writer.writerow(row)

    report_path = output_dir / "task2a_report.txt"
    with report_path.open("w") as f:
        f.write("Task 2A: Baseline LRU vs I-RRIP\\n")
        f.write("=" * 48 + "\\n\\n")
        f.write("Results table (speedup is relative to Baseline LRU for the same trace)\\n")
        f.write("| Trace | Policy | IPC | Speedup | L2C Load MPKI | L2 Instruction Load MPKI | L2 Data Load MPKI |\\n")
        f.write("|---|---|---:|---:|---:|---:|---:|\\n")
        def fmt(v):
            return f"{v:.6f}" if isinstance(v, (int, float)) else "N/A"
        for trace in TRACE_ORDER:
            for policy in ("Baseline LRU", "I-RRIP"):
                rr = next((x for x in rows if x["trace"] == trace and x["policy"] == policy), None)
                if rr is None:
                    f.write(f"| {trace} | {policy} | N/A | N/A | N/A | N/A | N/A |\\n")
                    continue
                f.write(f"| {trace} | {policy} | {fmt(rr['ipc'])} | {fmt(rr['speedup'])} | "
                        f"{fmt(rr['l2c_load_mpki'])} | {fmt(rr['l2_instruction_load_mpki'])} | "
                        f"{fmt(rr['l2_data_load_mpki'])} |\\n")
        f.write("\\nDetailed values by trace\\n\\n")
        for trace in TRACE_ORDER:
            f.write(f"{trace}\\n")
            for policy in ("Baseline LRU", "I-RRIP"):
                matches = [r for r in rows if r["trace"] == trace and r["policy"] == policy]
                if not matches:
                    f.write(f"  {policy}: MISSING LOG\\n")
                    continue
                r = matches[0]
                f.write(f"  {policy}: IPC={r['ipc']}, L2C Load MPKI={r['l2c_load_mpki']}, "
                        f"Instruction MPKI={r['l2_instruction_load_mpki']}, "
                        f"Data MPKI={r['l2_data_load_mpki']}\\n")
            b = baseline_ipc.get(trace)
            i = next((r["ipc"] for r in rows if r["trace"] == trace and r["policy"] == "I-RRIP"), None)
            f.write(f"  I-RRIP speedup over baseline: {i / b:.6f}\\n\\n" if b and i is not None
                    else "  I-RRIP speedup over baseline: unavailable (missing IPC)\\n\\n")

    plot_specs = [
        ("ipc", "IPC: Baseline LRU vs I-RRIP", "IPC", "ipc.png"),
        ("speedup", "Relative performance (baseline = 1.0)", "Speedup", "speedup.png"),
        ("l2c_load_mpki", "L2C Load MPKI", "MPKI", "l2c_load_mpki.png"),
        ("l2_instruction_load_mpki", "L2 Instruction Load MPKI", "MPKI", "instruction_mpki.png"),
        ("l2_data_load_mpki", "L2 Data Load MPKI", "MPKI", "data_mpki.png"),
    ]
    for key, title, ylabel, filename in plot_specs:
        write_plot(rows, key, title, ylabel, output_dir / filename)

    print(f"Read {len(rows)} log(s) from: {input_dir}")
    for row in sorted(rows, key=lambda r: (TRACE_ORDER.index(r["trace"]), r["policy"])):
        print(f"{row['trace']:6} | {row['policy']:12} | IPC={row['ipc']} | "
              f"L2C Load MPKI={row['l2c_load_mpki']} | "              f"Instr={row['l2_instruction_load_mpki']} | "
              f"Data={row['l2_data_load_mpki']} | {Path(row['source_log']).name}")
    print(f"\nCSV: {csv_path}")
    print(f"Report: {report_path}")
    print(f"Plots: {output_dir}")


if __name__ == "__main__":
    main()
