import json
import sys
from datetime import datetime
import numpy as np


def analyze_locust_stats(stats_file: str):
    with open(stats_file, 'r') as f:
        data = json.load(f)
    
    print("=" * 80)
    print("PANOPTICON STRESS TEST ANALYSIS")
    print("=" * 80)
    print(f"Analysis Time: {datetime.now().isoformat()}")
    print()
    
    if 'stats' in data:
        for stat in data['stats']:
            if stat['name'] == 'Aggregated':
                print(f"Total Requests: {stat['num_requests']:,}")
                print(f"Total Failures: {stat['num_failures']:,}")
                print(f"Failure Rate: {stat['num_failures'] / stat['num_requests'] * 100:.2f}%")
                print(f"Average Response Time: {stat['avg_response_time']:.2f}ms")
                print(f"Min Response Time: {stat['min_response_time']:.2f}ms")
                print(f"Max Response Time: {stat['max_response_time']:.2f}ms")
                print(f"Median Response Time: {stat['median_response_time']:.2f}ms")
                print(f"RPS: {stat['total_rps']:.2f}")
                print()
                
                percentiles = stat.get('response_times', {})
                print("Latency Percentiles:")
                print(f"  P50: {percentiles.get('50', 0):.2f}ms")
                print(f"  P75: {percentiles.get('75', 0):.2f}ms")
                print(f"  P90: {percentiles.get('90', 0):.2f}ms")
                print(f"  P95: {percentiles.get('95', 0):.2f}ms")
                print(f"  P99: {percentiles.get('99', 0):.2f}ms")
                print()
                
                p99 = percentiles.get('99', 0)
                if p99 > 0:
                    if p99 <= 200:
                        print(f"RESULT: PASS - P99 latency {p99:.2f}ms meets target")
                    else:
                        print(f"RESULT: FAIL - P99 latency {p99:.2f}ms exceeds 200ms target")
                
                if stat['total_rps'] >= 5000:
                    print(f"THROUGHPUT: PASS - {stat['total_rps']:.2f} RPS meets 5000 TPS target")
                else:
                    print(f"THROUGHPUT: FAIL - {stat['total_rps']:.2f} RPS below 5000 TPS target")
    
    print()
    print("=" * 80)


def generate_report(stats_file: str, output_file: str = "STRESS_TEST_REPORT.md"):
    with open(stats_file, 'r') as f:
        data = json.load(f)
    
    with open(output_file, 'w') as f:
        f.write("# PANOPTICON Stress Test Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        
        f.write("## Test Configuration\n\n")
        f.write("- Target Throughput: 5000 TPS\n")
        f.write("- P99 Latency Target: < 200ms\n")
        f.write("- Duration: 5 minutes\n")
        f.write("- Spawn Rate: 100 users/second\n\n")
        
        if 'stats' in data:
            for stat in data['stats']:
                if stat['name'] == 'Aggregated':
                    f.write("## Results\n\n")
                    f.write(f"- Total Requests: {stat['num_requests']:,}\n")
                    f.write(f"- Failed Requests: {stat['num_failures']:,}\n")
                    f.write(f"- Failure Rate: {stat['num_failures'] / stat['num_requests'] * 100:.2f}%\n")
                    f.write(f"- Throughput: {stat['total_rps']:.2f} RPS\n\n")
                    
                    f.write("## Latency Distribution\n\n")
                    f.write("| Percentile | Latency (ms) |\n")
                    f.write("|------------|-------------|\n")
                    
                    percentiles = stat.get('response_times', {})
                    for p in ['50', '75', '90', '95', '99']:
                        f.write(f"| P{p} | {percentiles.get(p, 0):.2f} |\n")
                    
                    f.write("\n")
                    
                    p99 = percentiles.get('99', 0)
                    rps = stat['total_rps']
                    
                    f.write("## Verdict\n\n")
                    
                    if p99 <= 200 and rps >= 5000:
                        f.write("**PASS** - System meets all performance targets\n")
                    else:
                        f.write("**FAIL** - System does not meet performance targets\n\n")
                        if p99 > 200:
                            f.write(f"- P99 latency {p99:.2f}ms exceeds 200ms target\n")
                        if rps < 5000:
                            f.write(f"- Throughput {rps:.2f} RPS below 5000 TPS target\n")
    
    print(f"Report generated: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <stats_file.json>")
        sys.exit(1)
    
    stats_file = sys.argv[1]
    
    analyze_locust_stats(stats_file)
    generate_report(stats_file)
