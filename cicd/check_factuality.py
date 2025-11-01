#!/usr/bin/env python3
"""
Factuality Check Module

This module extracts the factuality score checking logic from the GitHub workflow
and provides a reusable function to validate factuality results.
"""

import sys
import json
import os
from typing import Dict, Any, Optional


def load_factuality_results(results_file: str = 'evaluation_results.json') -> Dict[str, Any]:
    """
    Load evaluation results from JSON file.

    Args:
        results_file: Path to the evaluation results JSON file

    Returns:
        Dictionary containing the evaluation results

    Raises:
        FileNotFoundError: If the results file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        return results
    except FileNotFoundError:
        print(f'✗ ERROR: {results_file} not found')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'✗ ERROR: Invalid JSON in {results_file}: {e}')
        sys.exit(1)


def print_factuality_summary(results: Dict[str, Any]) -> None:
    """
    Print a formatted summary of evaluation results.

    Args:
        results: Dictionary containing evaluation results
    """
    # Extract metrics - support both old and new key names
    avg_score = results.get('average_quality_score') or results.get('average_factuality_score', 0)
    total_items = results['total_items']
    experiment_name = results['experiment_name']

    print(f'Experiment: {experiment_name}')
    print(f'Total items evaluated: {total_items}')
    print(f'Average Quality Score (Bedrock Claude): {avg_score:.3f} ({avg_score*100:.1f}%)')

    # Print individual scores
    print('\nIndividual scores:')
    for i, score_data in enumerate(results['scores']):
        print(f"  Item {i+1}: {score_data['value']:.3f} ({score_data.get('name', 'Unknown')})")
        if score_data.get('comment'):
            print(f"    Comment: {score_data['comment']}")


def check_factuality_threshold(results: Dict[str, Any], threshold: float = 0.5) -> bool:
    """
    Check if the average quality score meets the threshold requirement.

    Args:
        results: Dictionary containing evaluation results
        threshold: Minimum acceptable quality score (default: 0.5)

    Returns:
        True if the score meets the threshold, False otherwise
    """
    avg_score = results.get('average_quality_score') or results.get('average_factuality_score', 0)

    print(f'\nThreshold: {threshold*100:.0f}%')

    if avg_score >= threshold:
        print(f'✓ PASSED: Quality score {avg_score*100:.1f}% is above {threshold*100:.0f}%')
        return True
    else:
        print(f'✗ FAILED: Quality score {avg_score*100:.1f}% is below {threshold*100:.0f}%')
        return False


def main(results_file: str = 'evaluation_results.json', threshold: float = 0.5) -> int:
    """
    Main function to check evaluation results.

    Args:
        results_file: Path to the evaluation results JSON file
        threshold: Minimum acceptable quality score

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    # Load results from file
    results = load_factuality_results(results_file)
    
    # Print summary
    print_factuality_summary(results)
    
    # Check threshold
    passed = check_factuality_threshold(results, threshold)
    
    return 0 if passed else 1


if __name__ == '__main__':
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description='Check evaluation results from Bedrock Claude')
    parser.add_argument('--results-file', '-f',
                       default='evaluation_results.json',
                       help='Path to evaluation results JSON file (default: evaluation_results.json)')
    parser.add_argument('--threshold', '-t',
                       type=float,
                       default=0.5,
                       help='Minimum acceptable quality score (default: 0.5)')
    
    args = parser.parse_args()
    
    # Run the check
    exit_code = main(args.results_file, args.threshold)
    sys.exit(exit_code)
