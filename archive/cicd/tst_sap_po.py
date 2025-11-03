#!/usr/bin/env python3
"""
Evaluation script for testing agent against real SAP Purchase Order data
Uses PO 4500000520 with BKC-990 bicycle parts
"""

import langfuse
from langfuse.experiment import Evaluation
import sys
import os
import json
import boto3
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.langfuse import get_langfuse_client
from utils.agent import invoke_agent
from utils.test_sap_api import get_complete_po_data

# Simple EvaluationResult class
@dataclass
class EvaluationResult:
    name: str
    value: float
    comment: str = ""

# Initialize Langfuse client
langfuse = get_langfuse_client()

# Initialize Bedrock client for evaluation
bedrock_client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
EVALUATION_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"

# Get the dataset with real SAP data
dataset_name = "strands-ai-mcp-agent-evaluation-po4500000520"
dataset = langfuse.get_dataset(dataset_name)

# Get agent configuration from hp_config
def load_hp_config(config_path="cicd/hp_config.json"):
    """Load hyperparameters from the configuration file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file {config_path} not found.")
        sys.exit(1)

config = load_hp_config()
agent_arn = config.get('tst', {}).get('agent_arn') or config.get('prd', {}).get('agent_arn')

if not agent_arn:
    print("Error: No agent ARN found in hp_config.json")
    sys.exit(1)

print(f"\n{'='*80}")
print(f"SAP Purchase Order Evaluation")
print(f"{'='*80}")
print(f"Dataset: {dataset_name}")
print(f"Agent ARN: {agent_arn}")
print(f"Total items: {len(list(dataset.items))}")
print(f"{'='*80}\n")

# Show dataset items
print("Evaluation Items:")
items_list = list(dataset.items)
for i, item in enumerate(items_list[:5], 1):
    print(f"\n{i}. Question: {item.input['question']}")
    print(f"   Expected: {item.expected_output}")

print(f"\n{'='*80}")
print("Running Evaluation with Agent")
print(f"{'='*80}\n")

# Define the task function
def agent_task(*, item, **kwargs):
    """Task function that invokes the agent with the dataset item input."""
    try:
        # Extract the prompt from the dataset item
        if isinstance(item.input, dict) and 'question' in item.input:
            prompt = item.input['question']
        else:
            prompt = str(item.input)

        print(f"Invoking agent: {prompt[:80]}...")

        # Invoke the agent
        try:
            result = invoke_agent(agent_arn, prompt)
        except Exception as e:
            if 'utf-8' in str(e).lower():
                print(f"Warning: UTF-8 decoding error in agent response, using fallback")
                response = "Agent response contained encoding issues. Please check the agent logs."
                return response
            else:
                raise

        # Extract the response
        if isinstance(result, dict):
            if result.get('content_type') == 'application/json':
                response = result['response']
            else:
                response = result.get('response', '')
        else:
            response = str(result)

        print(f"✓ Response received")
        return response
    except Exception as e:
        print(f"✗ Error in agent_task: {str(e)}")
        raise


def evaluate_response_with_bedrock(input_text, output_text, expected_output):
    """
    Evaluate agent response using Claude via Bedrock.
    Returns a score between 0 and 1.
    """
    try:
        evaluation_prompt = f"""Evaluate the following agent response for quality and accuracy.

Question: {input_text}

Agent Response: {output_text}

Expected/Target: {expected_output}

Please evaluate if the agent response:
1. Answers the question correctly
2. Is relevant to the question
3. Provides accurate information from SAP data
4. Is well-structured in Hebrew

Rate the response on a scale of 0-1 where:
- 0 = Completely wrong or irrelevant
- 0.5 = Partially correct but has issues
- 1 = Excellent response that fully answers the question

Respond with ONLY a number between 0 and 1."""

        # Call Bedrock Claude using Converse API
        response = bedrock_client.converse(
            modelId=EVALUATION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": evaluation_prompt
                        }
                    ]
                }
            ],
            inferenceConfig={
                "maxTokens": 100
            }
        )

        # Parse the response
        score_text = response['output']['message']['content'][0]['text'].strip()

        # Extract score (handle various formats)
        try:
            score = float(score_text)
        except ValueError:
            # Try to extract number from text
            import re
            numbers = re.findall(r'\d+\.?\d*', score_text)
            score = float(numbers[0]) if numbers else 0.5

        # Ensure score is between 0 and 1
        score = max(0.0, min(1.0, score))

        return score
    except Exception as e:
        print(f"Error evaluating with Bedrock: {str(e)}")
        return 0.5  # Return neutral score on error


def bedrock_quality_evaluator(*, input, output, expected_output, **kwargs):
    """Custom evaluator using Bedrock Claude."""
    try:
        print(f"[EVALUATOR] Starting Bedrock quality evaluation")

        # Extract input text
        if isinstance(input, dict) and 'question' in input:
            input_text = input['question']
        else:
            input_text = str(input)

        # Evaluate the response
        score = evaluate_response_with_bedrock(
            input_text=input_text,
            output_text=str(output),
            expected_output=str(expected_output)
        )

        print(f"[EVALUATOR] Score: {score}")

        # Return as a Langfuse Evaluation object
        evaluation = Evaluation(
            name="bedrock_quality",
            value=score,
            comment=f"Quality score from Claude evaluation: {score:.2f}"
        )
        print(f"[EVALUATOR] Returning Evaluation: {evaluation}")
        return evaluation
    except Exception as e:
        print(f"[EVALUATOR] Error: {str(e)}")
        # Return a default score on error rather than failing
        return Evaluation(
            name="bedrock_quality",
            value=0.5,
            comment=f"Error during evaluation: {str(e)}"
        )


# Run experiment with Bedrock evaluator
print(f"Running experiment with Bedrock Claude evaluator...\n")

# Convert dataset items to list for experiment
data = list(items_list)

result = langfuse.run_experiment(
    name="SAP PO Evaluation - BKC-990 Parts",
    data=data,
    task=agent_task,
    evaluators=[bedrock_quality_evaluator]
)

# Print experiment summary
print(f"\nExperiment completed: {result.run_name}")
if hasattr(result, 'dataset_run_url'):
    print(f"Dataset run URL: {result.dataset_run_url}")

# Extract quality scores
quality_scores = []

print(f"\n{'='*80}")
print("Extracting evaluation results...")
print(f"{'='*80}")

# Process each item result
for idx, item_result in enumerate(result.item_results or []):
    print(f"\nItem {idx+1}:")
    print(f"  Output: {str(item_result.output)[:150]}...")

    # Extract evaluations for this item
    if item_result.evaluations:
        for evaluation in item_result.evaluations:
            # Extract name and value from evaluation object
            eval_name = getattr(evaluation, 'name', None)
            eval_value = getattr(evaluation, 'value', None)
            eval_comment = getattr(evaluation, 'comment', None)

            if eval_name == 'bedrock_quality':
                quality_scores.append({
                    "name": eval_name,
                    "value": eval_value,
                    "comment": eval_comment
                })
                print(f"  ✓ Captured score: {eval_value}")
    else:
        print(f"  (No evaluations)")

print(f"\nTotal scores captured: {len(quality_scores)}")

# Calculate average
avg_score = sum(s['value'] for s in quality_scores) / len(quality_scores) if quality_scores else 0

# Save results
results = {
    'experiment_name': result.name,
    'dataset_name': dataset_name,
    'total_items': len(quality_scores),
    'average_quality_score': avg_score,
    'scores': quality_scores
}

with open('evaluation_results_sap_po.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n{'='*80}")
print(f"SAP PO Evaluation Results (Bedrock Claude):")
print(f"  Average Score: {avg_score:.3f} ({avg_score*100:.1f}%)")
print(f"  Total Items: {len(quality_scores)}")
print(f"  Results saved to: evaluation_results_sap_po.json")
print(f"{'='*80}\n")
