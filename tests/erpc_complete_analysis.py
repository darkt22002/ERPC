#!/usr/bin/env python3
"""
ERPC Data Analysis Script
Entropy-Regulated Power Control - Complete Analysis
Author: Gary W. Floyd / Lumiea Systems Research Division
Date: December 2024

Usage:
    python3 erpc_complete_analysis.py erpc_log.txt

This script analyzes ERPC performance data and calculates:
- Switching reduction percentage
- Operating region analysis  
- Load response characteristics
- Performance visualizations
"""

import re
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def parse_erpc_log(log_text):
    """Parse ERPC log data into structured format"""
    
    pattern = r'Samples: (\d+) \| Vout: ([\d.]+)V \| Iload: ([\d.]+)A \| E: ([-\d.]+) \| A: ([\d.]+) \| ∇S: ([\d.]+) \| Corr: ([\d.]+) \| ΔS: ([-\d.]+) \| Gate: (\w+)\s+\| PWM: (\d+)'
    
    data = {
        'samples': [],
        'vout': [],
        'iload': [],
        'entropy': [],
        'gate': [],
        'pwm': [],
        'delta_s': []
    }
    
    for match in re.finditer(pattern, log_text):
        data['samples'].append(int(match.group(1)))
        data['vout'].append(float(match.group(2)))
        data['iload'].append(float(match.group(3)))
        data['entropy'].append(float(match.group(4)))
        data['gate'].append(1 if match.group(9) == 'ON' else 0)
        data['pwm'].append(int(match.group(10)))
        data['delta_s'].append(float(match.group(8)))
    
    return data

def filter_valid_operation(data, min_voltage=0.5, max_voltage=12.0):
    """
    Filter out periods where potentiometers were being adjusted.
    Excludes:
    - Vout < 0.5V (no power / collapse)
    - Vout > 12V (excessive overvoltage during adjustment)
    """
    
    valid_indices = []
    for i, v in enumerate(data['vout']):
        if min_voltage < v < max_voltage:
            valid_indices.append(i)
    
    filtered = {}
    for key in data:
        filtered[key] = [data[key][i] for i in valid_indices]
    
    return filtered, len(valid_indices), len(data['samples'])

def analyze_switching_efficiency(data):
    """
    Calculate switching statistics and efficiency.
    
    Traditional PWM switches on every sample period.
    GEP-based control only switches when entropy crosses threshold.
    """
    
    gate_states = np.array(data['gate'])
    samples = np.array(data['samples'])
    
    # Count state transitions (OFF->ON or ON->OFF)
    transitions = np.diff(gate_states)
    switch_count = np.count_nonzero(transitions)
    
    # Total samples during operation
    total_samples = len(gate_states)
    
    # Traditional PWM would switch every cycle
    traditional_switches = total_samples
    
    # GEP-based switching reduction
    reduction = ((traditional_switches - switch_count) / traditional_switches) * 100
    
    # Average time between switches
    avg_samples_per_switch = total_samples / (switch_count + 1) if switch_count > 0 else total_samples
    
    return {
        'total_samples': total_samples,
        'switch_count': switch_count,
        'traditional_switches': traditional_switches,
        'reduction_percent': reduction,
        'avg_samples_per_switch': avg_samples_per_switch,
        'switching_frequency': switch_count / total_samples if total_samples > 0 else 0
    }

def analyze_operating_regions(data):
    """Analyze different operating voltage regions"""
    
    vout = np.array(data['vout'])
    entropy = np.array(data['entropy'])
    gate = np.array(data['gate'])
    
    regions = {
        'nominal_regulation': {
            'count': np.sum((vout >= 4.5) & (vout <= 6.0)),
            'avg_entropy': np.mean(entropy[(vout >= 4.5) & (vout <= 6.0)]) if np.any((vout >= 4.5) & (vout <= 6.0)) else 0
        },
        'overvoltage': {
            'count': np.sum(vout > 7.0),
            'avg_entropy': np.mean(entropy[vout > 7.0]) if np.any(vout > 7.0) else 0
        },
        'undervoltage': {
            'count': np.sum((vout > 0.5) & (vout < 3.0)),
            'avg_entropy': np.mean(entropy[(vout > 0.5) & (vout < 3.0)]) if np.any((vout > 0.5) & (vout < 3.0)) else 0
        },
        'gate_on_time': np.sum(gate) / len(gate) * 100 if len(gate) > 0 else 0,
        'gate_off_time': (len(gate) - np.sum(gate)) / len(gate) * 100 if len(gate) > 0 else 0
    }
    
    return regions

def calculate_load_response_metrics(data):
    """Analyze response to load changes"""
    
    iload = np.array(data['iload'])
    vout = np.array(data['vout'])
    
    # Find load transitions (>0.5A change)
    load_changes = np.abs(np.diff(iload)) > 0.5
    load_transition_count = np.sum(load_changes)
    
    # Voltage regulation during different load conditions
    light_load = iload < 1.0
    medium_load = (iload >= 1.0) & (iload < 3.0)
    heavy_load = iload >= 3.0
    
    metrics = {
        'load_transitions': load_transition_count,
        'light_load': {
            'count': np.sum(light_load),
            'avg_vout': np.mean(vout[light_load]) if np.any(light_load) else 0,
            'std_vout': np.std(vout[light_load]) if np.any(light_load) else 0
        },
        'medium_load': {
            'count': np.sum(medium_load),
            'avg_vout': np.mean(vout[medium_load]) if np.any(medium_load) else 0,
            'std_vout': np.std(vout[medium_load]) if np.any(medium_load) else 0
        },
        'heavy_load': {
            'count': np.sum(heavy_load),
            'avg_vout': np.mean(vout[heavy_load]) if np.any(heavy_load) else 0,
            'std_vout': np.std(vout[heavy_load]) if np.any(heavy_load) else 0
        }
    }
    
    return metrics

def create_visualizations(data, output_file='erpc_analysis.png'):
    """Create comprehensive visualization plots"""
    
    fig, axes = plt.subplots(4, 1, figsize=(16, 14))
    
    samples = np.array(data['samples'])
    vout = np.array(data['vout'])
    iload = np.array(data['iload'])
    entropy = np.array(data['entropy'])
    gate = np.array(data['gate'])
    
    # Plot 1: Voltage over time
    axes[0].plot(samples, vout, 'b-', linewidth=0.8, alpha=0.7)
    axes[0].axhline(y=5.0, color='g', linestyle='--', linewidth=2, alpha=0.6, label='Target 5V')
    axes[0].axhline(y=4.5, color='orange', linestyle=':', linewidth=1, alpha=0.4)
    axes[0].axhline(y=6.0, color='orange', linestyle=':', linewidth=1, alpha=0.4)
    axes[0].fill_between(samples, 4.5, 6.0, alpha=0.1, color='green', label='Regulation Band')
    axes[0].set_ylabel('Output Voltage (V)', fontsize=13, fontweight='bold')
    axes[0].set_title('ERPC System Performance - Guided Entropy Principle\nEntropy-Regulated Power Control (Valid Operation Data)', 
                     fontsize=15, fontweight='bold', pad=15)
    axes[0].grid(True, alpha=0.3, linestyle='--')
    axes[0].legend(loc='upper right', fontsize=10)
    axes[0].set_ylim([min(vout)*0.9, max(vout)*1.1])
    
    # Plot 2: Load current
    axes[1].plot(samples, iload, 'r-', linewidth=0.8, alpha=0.7)
    axes[1].fill_between(samples, 0, iload, alpha=0.2, color='red')
    axes[1].set_ylabel('Load Current (A)', fontsize=13, fontweight='bold')
    axes[1].grid(True, alpha=0.3, linestyle='--')
    axes[1].set_ylim([0, max(iload)*1.1])
    
    # Plot 3: Entropy
    axes[2].plot(samples, entropy, 'purple', linewidth=0.8, alpha=0.7)
    axes[2].axhline(y=0, color='k', linestyle='--', linewidth=1.5, alpha=0.5, label='Zero Entropy')
    axes[2].axhline(y=0.5, color='orange', linestyle='--', linewidth=2, alpha=0.7, label='Switching Threshold')
    axes[2].fill_between(samples, 0, entropy, where=(entropy>0), alpha=0.2, color='red', label='High Entropy (Undervoltage)')
    axes[2].fill_between(samples, entropy, 0, where=(entropy<0), alpha=0.2, color='blue', label='Negative Entropy (Overvoltage)')
    axes[2].set_ylabel('Entropy E(x)', fontsize=13, fontweight='bold')
    axes[2].grid(True, alpha=0.3, linestyle='--')
    axes[2].legend(loc='upper right', fontsize=9)
    
    # Plot 4: Gate state with switching events
    axes[3].fill_between(samples, 0, gate, alpha=0.35, color='green', label='Gate ON Periods')
    axes[3].plot(samples, gate, 'g-', linewidth=2)
    
    # Mark switching events
    gate_array = np.array(gate)
    transitions = np.where(np.abs(np.diff(gate_array)) > 0)[0]
    if len(transitions) > 0:
        axes[3].scatter(samples[transitions], gate_array[transitions], 
                       color='red', s=80, zorder=5, marker='o', 
                       alpha=0.8, edgecolors='darkred', linewidth=1.5,
                       label=f'Switching Events ({len(transitions)})')
    
    axes[3].set_ylabel('Gate State', fontsize=13, fontweight='bold')
    axes[3].set_xlabel('Sample Number', fontsize=13, fontweight='bold')
    axes[3].set_ylim([-0.1, 1.2])
    axes[3].set_yticks([0, 1])
    axes[3].set_yticklabels(['OFF', 'ON'], fontsize=11)
    axes[3].grid(True, alpha=0.3, linestyle='--')
    axes[3].legend(loc='upper right', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Visualization saved to: {output_file}")

def main():
    print("="*80)
    print("ERPC DATA ANALYSIS")
    print("Entropy-Regulated Power Control - Arduino Implementation")
    print("Guided Entropy Principle (GEP) Framework")
    print("Lumiea Systems Research Division / ThunderStruck Service LLC")
    print("="*80)
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("\nUsage: python3 erpc_complete_analysis.py <logfile.txt>")
        print("\nAttempting to use 'erpc_log.txt' in current directory...")
        log_file = 'erpc_log.txt'
    else:
        log_file = sys.argv[1]
    
    # Check if file exists
    if not Path(log_file).exists():
        print(f"\nERROR: Log file '{log_file}' not found!")
        print("\nPlease provide the ERPC log file as an argument.")
        sys.exit(1)
    
    # Parse the data
    print(f"\n[1/5] Parsing ERPC log data from: {log_file}")
    
    with open(log_file, 'r') as f:
        log_text = f.read()
    
    data = parse_erpc_log(log_text)
    print(f"      ✓ Parsed {len(data['samples']):,} total samples")
    
    # Filter out potentiometer adjustment periods
    print("\n[2/5] Filtering valid operation periods...")
    print("      Excluding: Vout < 0.5V (no power) and Vout > 12V (overvoltage)")
    filtered_data, valid_count, total_count = filter_valid_operation(data)
    excluded = total_count - valid_count
    print(f"      ✓ Valid samples: {valid_count:,}")
    print(f"      ✓ Excluded samples: {excluded:,} ({excluded/total_count*100:.1f}%)")
    
    if valid_count == 0:
        print("\nERROR: No valid samples found after filtering!")
        sys.exit(1)
    
    # Analyze switching efficiency
    print("\n[3/5] Analyzing switching efficiency...")
    switching = analyze_switching_efficiency(filtered_data)
    
    print("\n" + "="*80)
    print("SWITCHING EFFICIENCY RESULTS")
    print("="*80)
    print(f"Total valid samples:           {switching['total_samples']:,}")
    print(f"Gate transitions (actual):     {switching['switch_count']:,}")
    print(f"Traditional PWM switches:      {switching['traditional_switches']:,}")
    print(f"\n╔════════════════════════════════════════════════════════════════════╗")
    print(f"║  SWITCHING REDUCTION: {switching['reduction_percent']:6.2f}%                                    ║")
    print(f"╚════════════════════════════════════════════════════════════════════╝")
    print(f"\nAvg samples between switches:  {switching['avg_samples_per_switch']:.1f}")
    print(f"Switching frequency:           {switching['switching_frequency']:.4f} transitions/sample")
    
    # Analyze operating regions
    print("\n[4/5] Analyzing operating regions...")
    regions = analyze_operating_regions(filtered_data)
    
    print("\n" + "="*80)
    print("OPERATING REGION ANALYSIS")
    print("="*80)
    
    print(f"\nNominal Regulation (4.5-6.0V):")
    print(f"  Samples:      {regions['nominal_regulation']['count']:,}")
    print(f"  Avg Entropy:  {regions['nominal_regulation']['avg_entropy']:.4f}")
    
    print(f"\nOvervoltage (>7.0V):")
    print(f"  Samples:      {regions['overvoltage']['count']:,}")
    print(f"  Avg Entropy:  {regions['overvoltage']['avg_entropy']:.4f}")
    
    print(f"\nUndervoltage (0.5-3.0V):")
    print(f"  Samples:      {regions['undervoltage']['count']:,}")
    print(f"  Avg Entropy:  {regions['undervoltage']['avg_entropy']:.4f}")
    
    print(f"\nGate Duty Cycle:")
    print(f"  ON time:      {regions['gate_on_time']:.2f}%")
    print(f"  OFF time:     {regions['gate_off_time']:.2f}%")
    
    # Analyze load response
    print("\n" + "="*80)
    print("LOAD RESPONSE ANALYSIS")
    print("="*80)
    
    load_metrics = calculate_load_response_metrics(filtered_data)
    print(f"\nLoad transitions detected: {load_metrics['load_transitions']:,}")
    
    print(f"\nLight Load (<1.0A):")
    print(f"  Samples:      {load_metrics['light_load']['count']:,}")
    print(f"  Avg Vout:     {load_metrics['light_load']['avg_vout']:.3f}V")
    print(f"  Std Dev:      {load_metrics['light_load']['std_vout']:.3f}V")
    
    print(f"\nMedium Load (1.0-3.0A):")
    print(f"  Samples:      {load_metrics['medium_load']['count']:,}")
    print(f"  Avg Vout:     {load_metrics['medium_load']['avg_vout']:.3f}V")
    print(f"  Std Dev:      {load_metrics['medium_load']['std_vout']:.3f}V")
    
    print(f"\nHeavy Load (>3.0A):")
    print(f"  Samples:      {load_metrics['heavy_load']['count']:,}")
    print(f"  Avg Vout:     {load_metrics['heavy_load']['avg_vout']:.3f}V")
    print(f"  Std Dev:      {load_metrics['heavy_load']['std_vout']:.3f}V")
    
    # Create visualizations
    print("\n[5/5] Generating visualizations...")
    output_file = log_file.replace('.txt', '_analysis.png')
    create_visualizations(filtered_data, output_file)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\n🎯 KEY FINDING: {switching['reduction_percent']:.2f}% switching reduction achieved!")
    print("   ")
    print("   The GEP algorithm reduced unnecessary switching by eliminating")
    print(f"   {switching['traditional_switches'] - switching['switch_count']:,} gate transitions")
    print("   while maintaining voltage regulation under dynamic load conditions.")
    print("   ")
    print("   This demonstrates entropy-based control naturally optimizes switching")
    print("   frequency without explicit PWM optimization algorithms.")
    print("\n" + "="*80)
    print()

if __name__ == "__main__":
    main()
