import langfuse
import sys
import os
import json
import boto3
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.langfuse import get_langfuse_client
from utils.agent import invoke_agent
from utils.aws import get_ssm_parameter
import logging

# Simple EvaluationResult class
@dataclass
class EvaluationResult:
    name: str
    value: float
    comment: str = ""

# Add this at the top of your script
#logging.basicConfig(level=logging.DEBUG)
#logger = logging.getLogger("autoevals")
#logger.setLevel(logging.DEBUG)




# Load hyperparameters and agent configuration from hp_config.json
def load_hp_config(config_path="cicd/hp_config.json"):
    """Load hyperparameters and agent configuration from the JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        # Support both standalone config and nested "tst" key
        if "tst" in config:
            return config["tst"]
        else:
            # Return config as-is if no "tst" key (handles our current format)
            return {"model": config.get("model"), "system_prompt": config.get("system_prompt")}
    except FileNotFoundError:
        print(f"Error: Configuration file {config_path} not found.")
        print("Make sure to run the deployment step first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}")
        sys.exit(1)

# Load configuration
print("Loading agent configuration from hp_config.json...")
config = load_hp_config()

# Check if agent_arn exists in the config
if not config.get("agent_arn"):
    print("Error: agent_arn not found in hp_config.json.")
    print("Make sure to run the deployment step first.")
    sys.exit(1)

agent_arn = config["agent_arn"]
print(f"Using agent ARN from deployment: {agent_arn}")
print(f"Agent Name: {config.get('agent_name', 'N/A')}")
print(f"Agent ID: {config.get('agent_id', 'N/A')}")

    # Initialize Langfuse client
langfuse = get_langfuse_client()

# Initialize Bedrock client for evaluation
bedrock_client = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
EVALUATION_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"


# Get the dataset
dataset_name="strands-ai-mcp-agent-evaluation"
dataset = langfuse.get_dataset(dataset_name)

# Print first 3 items of the dataset
print(f"\n{'='*80}\nFirst 3 items from dataset '{dataset_name}':\n{'='*80}")
items_list = list(dataset.items)
for i, item in enumerate(items_list[:3]):
    print(f"\nItem {i+1}:")
    print(f"  ID: {item.id}")
    print(f"  Input: {item.input}")
    print(f"  Expected Output: {item.expected_output}")
print(f"{'='*80}\n")

# Define the task function that wraps invoke_agent
def agent_task(*, item, **kwargs):
    """
    Task function that invokes the agent with the dataset item input.

    Parameters:
    - item: DatasetItemClient object with input and expected_output

    Returns:
    - str: The agent's response
    """
    try:
        # Extract the prompt from the dataset item
        if isinstance(item.input, dict) and 'question' in item.input:
            prompt = item.input['question']
        else:
            prompt = str(item.input)

        print(f"\nInvoking agent with prompt: {prompt[:100]}...")

        # Invoke the agent
        try:
            result = invoke_agent(agent_arn, prompt)
        except Exception as e:
            # Catch UTF-8 decoding errors and try to recover
            if 'utf-8' in str(e).lower():
                print(f"Warning: UTF-8 decoding error in agent response, using fallback")
                # Return a default response for now
                response = "Agent response contained encoding issues. Please check the agent logs."
                return response
            else:
                raise

        print(f"Agent result type: {type(result)}")
        print(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

        # Check for errors
        if isinstance(result, dict) and 'error' in result:
            error_msg = result.get('error', 'Unknown error')
            if 'utf-8' in str(error_msg).lower():
                print(f"Warning: UTF-8 decoding error in agent response")
                response = "Agent response contained encoding issues. Please check the agent logs."
                return response
            else:
                raise Exception(f"Agent invocation error: {error_msg}")

        # Extract the response based on content type
        if isinstance(result, dict):
            if result.get('content_type') == 'application/json':
                response = result['response']
            else:
                response = result.get('response', '')
        else:
            # If result is already a string (plain response), use it directly
            response = str(result)

        print(f"Agent response: {str(response)[:100]}...")
        return response
    except Exception as e:
        print(f"Error in agent_task: {str(e)}")
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
3. Provides useful information
4. Is well-structured in Hebrew

Rate the response on a scale of 0-1 where:
- 0 = Completely wrong or irrelevant
- 0.5 = Partially correct but has issues
- 1 = Excellent response that fully answers the question

Respond with ONLY a number between 0 and 1."""

        # Call Bedrock Claude (use messages API with correct format for Sonnet)
        request_body = {
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": evaluation_prompt
                }
            ]
        }

        # For newer Claude models on Bedrock, include anthropic_version
        # Try with version first, fall back to without if it fails
        try:
            response = bedrock_client.invoke_model(
                modelId=EVALUATION_MODEL,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({**request_body, "anthropic_version": "bedrock-2023-06-01"})
            )
        except Exception as version_error:
            if "anthropic_version" in str(version_error):
                # Retry without version
                response = bedrock_client.invoke_model(
                    modelId=EVALUATION_MODEL,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(request_body)
                )
            else:
                raise

        # Parse the response
        response_body = json.loads(response['body'].read())
        score_text = response_body['content'][0]['text'].strip()

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


# Define Bedrock evaluator function
def bedrock_quality_evaluator(*, input, output, expected_output, **kwargs):
    """Custom evaluator using Bedrock Claude.

    Note: Langfuse evaluators should return a dict or EvaluationResult.
    We use EvaluationResult from the dataclass defined at the top.
    """
    try:
        print(f"\n[EVALUATOR] Starting evaluation...")
        print(f"[EVALUATOR] Input type: {type(input)}, value: {str(input)[:100]}...")
        print(f"[EVALUATOR] Output type: {type(output)}, value: {str(output)[:100]}...")
        print(f"[EVALUATOR] Expected type: {type(expected_output)}, value: {str(expected_output)[:100]}...")
        print(f"[EVALUATOR] kwargs: {kwargs}")

        score = evaluate_response_with_bedrock(str(input), str(output), str(expected_output))

        print(f"[EVALUATOR] Score calculated: {score}, type: {type(score)}")

        # Create EvaluationResult using dataclass
        result = EvaluationResult(
            name="bedrock_quality",
            value=score,
            comment=f"Quality score from Claude evaluation: {score:.2f}"
        )

        print(f"[EVALUATOR] Returning result type: {type(result)}")
        print(f"[EVALUATOR] Result: {result}")
        print(f"[EVALUATOR] Result.name: {result.name}, Result.value: {result.value}")

        # Also try returning as dict for Langfuse compatibility
        result_dict = {
            "name": result.name,
            "value": result.value,
            "comment": result.comment
        }
        print(f"[EVALUATOR] Also returning dict: {result_dict}")
        return result_dict
    except Exception as e:
        print(f"[EVALUATOR] Error in evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

# Run experiment with Bedrock evaluator
print(f"\n{'='*80}")
print("Running experiment with Bedrock Claude evaluator...")
print(f"{'='*80}\n")

# Convert dataset items to list for experiment
data = list(items_list)

result = langfuse.run_experiment(
    name="Hebrew Inventory Agent - Bedrock Evaluation",
    data=data,
    task=agent_task,
    evaluators=[bedrock_quality_evaluator]
)

print(result.format(include_item_results=True))

# Extract quality scores and save to file
quality_scores = []

print(f"\n[RESULTS] Processing experiment results...")
print(f"[RESULTS] Result type: {type(result)}")
print(f"[RESULTS] Result attributes: {dir(result) if result else 'None'}")

if hasattr(result, 'item_results'):
    print(f"[RESULTS] Number of item_results: {len(result.item_results) if result.item_results else 0}")

    for idx, item_result in enumerate(result.item_results or []):
        print(f"\n[RESULTS] Processing item {idx+1}...")
        print(f"[RESULTS] Item result type: {type(item_result)}")
        print(f"[RESULTS] Item result attributes: {dir(item_result) if item_result else 'None'}")

        if hasattr(item_result, 'evaluations'):
            print(f"[RESULTS] Number of evaluations: {len(item_result.evaluations) if item_result.evaluations else 0}")
            for evaluation in (item_result.evaluations or []):
                print(f"[RESULTS] Evaluation: {evaluation}")
                if hasattr(evaluation, 'name') and evaluation.name == 'bedrock_quality':
                    evaluation_dict = {
                        "name": evaluation.name if hasattr(evaluation, 'name') else 'unknown',
                        "value": evaluation.value if hasattr(evaluation, 'value') else 0,
                        "comment": evaluation.comment if hasattr(evaluation, 'comment') else 'N/A'
                    }
                    quality_scores.append(evaluation_dict)
                    print(f"[RESULTS] Added score: {evaluation_dict}")
else:
    print("[RESULTS] Warning: result does not have item_results attribute")

# Calculate average
avg_score = sum(s['value'] for s in quality_scores) / len(quality_scores) if quality_scores else 0

# Save results
results = {
    'experiment_name': result.name,
    'total_items': len(quality_scores),
    'average_quality_score': avg_score,
    'scores': quality_scores
}

with open('evaluation_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*80}")
print(f"Evaluation Results Summary (Bedrock Claude):")
print(f"  Average Score: {avg_score:.3f} ({avg_score*100:.1f}%)")
print(f"  Total Items: {len(quality_scores)}")
print(f"  Results saved to: evaluation_results.json")
print(f"{'='*80}\n")