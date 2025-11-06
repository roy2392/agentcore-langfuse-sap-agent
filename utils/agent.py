import base64
import boto3
import sys
import os
from boto3.session import Session

# Only import Runtime if needed (not for web UI)
try:
    from bedrock_agentcore_starter_toolkit import Runtime
    agentcore_runtime = Runtime()
except ImportError:
    Runtime = None
    agentcore_runtime = None

# Add parent directory to path for proper imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

try:
    from langfuse import get_client as langfuse_get_client
except ImportError:
    langfuse_get_client = None

try:
    from utils.aws import get_ssm_parameter
except ImportError:
    def get_ssm_parameter(param_name):
        return os.getenv(param_name.split('/')[-1], '')

boto_session = Session()
region = boto_session.region_name


class ExistingAgentLaunchResult:
    """Mock launch result object for already-deployed agents to maintain API compatibility."""
    def __init__(self, agent_arn, agent_id, ecr_uri=None, status='ACTIVE'):
        self.agent_arn = agent_arn
        self.agent_id = agent_id
        self.ecr_uri = ecr_uri
        self.status = status
        self.already_deployed = True


# Langfuse configuration - optional for web UI
try:
    LANGFUSE_PROJECT_NAME = get_ssm_parameter("/langfuse/LANGFUSE_PROJECT_NAME")
    LANGFUSE_SECRET_KEY = get_ssm_parameter("/langfuse/LANGFUSE_SECRET_KEY")
    LANGFUSE_PUBLIC_KEY = get_ssm_parameter("/langfuse/LANGFUSE_PUBLIC_KEY")
    LANGFUSE_HOST = get_ssm_parameter("/langfuse/LANGFUSE_HOST")

    # Langfuse configuration
    otel_endpoint = f'{LANGFUSE_HOST}/api/public/otel'
    langfuse_project_name = LANGFUSE_PROJECT_NAME
    langfuse_secret_key = LANGFUSE_SECRET_KEY
    langfuse_public_key = LANGFUSE_PUBLIC_KEY
    langfuse_auth_token = base64.b64encode(f"{langfuse_public_key}:{langfuse_secret_key}".encode()).decode()
    otel_auth_header = f"Authorization=Basic {langfuse_auth_token}"
except Exception as e:
    print(f"Warning: Langfuse configuration not available: {str(e)}")
    LANGFUSE_PROJECT_NAME = ""
    LANGFUSE_SECRET_KEY = ""
    LANGFUSE_PUBLIC_KEY = ""
    LANGFUSE_HOST = ""
    otel_endpoint = ""
    langfuse_project_name = ""
    langfuse_secret_key = ""
    langfuse_public_key = ""
    langfuse_auth_token = ""
    otel_auth_header = ""




def deploy_agent(model, system_prompt, gateway_url, cognito_client_id, cognito_client_secret, cognito_domain, force_redeploy=False, environment="DEV"):
    """
    Deploys an Amazon Bedrock AgentCore Runtime agent with the specified configuration.
    
    Parameters:
    - model (dict): Dictionary containing model name and model_id
    - system_prompt (dict): Dictionary containing prompt name and prompt text
    - force_redeploy (bool): If True, redeploys the agent even if it already exists (default: False)
    
    Returns:
    - dict: The launch result from AgentCore Runtime, or existing agent info if already deployed
    """
    agent_name = f'strands_{model["name"]}_{system_prompt["name"]}_{environment}'
    
    # Check if the agent already exists
    try:
        agentcore_control_client = boto3.client(
            'bedrock-agentcore-control',
            region_name=region
        )
        
        # List all agent runtimes to check if this agent already exists
        list_response = agentcore_control_client.list_agent_runtimes()
        existing_agents = list_response.get('agentRuntimes', [])        
        # Check if an agent with this name already exists
        existing_agent = None
        for agent_summary in existing_agents:
            if agent_summary.get('agentRuntimeName') == agent_name:
                existing_agent = agent_summary
                break
        
        # If agent exists and force_redeploy is False, return existing agent info
        if existing_agent and not force_redeploy:
            print(f"Agent '{agent_name}' already exists. Skipping deployment.")
            print(f"Agent Runtime ARN: {existing_agent.get('agentRuntimeArn')}")
            print(f"Status: {existing_agent.get('status')}")
            
            # Get full agent runtime details to extract ECR URI
            agent_runtime_id = existing_agent.get('agentRuntimeId')
            agent_runtime_arn = existing_agent.get('agentRuntimeArn')
            
            try:
                get_response = agentcore_control_client.get_agent_runtime(
                    agentRuntimeId=agent_runtime_id
                )
                ecr_uri = get_response.get('ecrUri', '')
            except Exception as e:
                print(f"Warning: Could not retrieve ECR URI: {str(e)}")
                ecr_uri = ''
            
            # Create a compatible launch result object
            launch_result = ExistingAgentLaunchResult(
                agent_arn=agent_runtime_arn,
                agent_id=agent_runtime_id,
                ecr_uri=ecr_uri,
                status=existing_agent.get('status', 'ACTIVE')
            )
            
            return {
                'agent_name': agent_name,
                'launch_result': launch_result,
                'model_id': model["model_id"],
                'system_prompt_id': system_prompt["name"]
            }
        
        # If agent exists and force_redeploy is True, inform the user
        if existing_agent and force_redeploy:
            print(f"Agent '{agent_name}' already exists. Force redeploying...")
    
    except Exception as e:
        print(f"Error checking existing agents: {str(e)}")
        print("Proceeding with deployment...")
    
    # Proceed with deployment
    if not agentcore_runtime:
        raise ImportError("bedrock_agentcore_starter_toolkit is required for deployment")

    response = agentcore_runtime.configure(
        entrypoint="./agents/strands_claude.py",
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="./agents/requirements.txt",
        region=region,
        agent_name=agent_name,
        disable_otel=True,
       memory_mode='NO_MEMORY'
    )

    print(response)


    # Agent configuration
    bedrock_model_id = model["model_id"]
    system_prompt_value = system_prompt["prompt"]

    # AWS AgentCore Gateway pattern: Agent uses Gateway endpoint for tools
    # NO direct SAP credentials in agent environment!
    launch_result = agentcore_runtime.launch(
        auto_update_on_conflict=True,
        env_vars={
            "BEDROCK_MODEL_ID": bedrock_model_id,
            "LANGFUSE_PROJECT_NAME": langfuse_project_name,
            "LANGFUSE_TRACING_ENVIRONMENT": environment,
            "OTEL_EXPORTER_OTLP_ENDPOINT": otel_endpoint,  # Use Langfuse OTEL endpoint
            "OTEL_EXPORTER_OTLP_HEADERS": otel_auth_header,  # Add Langfuse OTEL auth header
            "DISABLE_ADOT_OBSERVABILITY": "true",
            "SYSTEM_PROMPT": system_prompt_value,
            "GATEWAY_ENDPOINT_URL": gateway_url,
            "COGNITO_CLIENT_ID": cognito_client_id,
            "COGNITO_CLIENT_SECRET": cognito_client_secret,
            "COGNITO_DOMAIN": cognito_domain,
        }
    )

    print(launch_result)

    return {
        'agent_name': agent_name,
        'launch_result': launch_result,
        'model_id': model["model_id"],
        'system_prompt_id': system_prompt["name"]
    }


def invoke_agent(agent_arn, prompt, session_id=None):
    """
    Invokes an Amazon Bedrock AgentCore Runtime agent with the given prompt.
    
    Parameters:
    - agent_arn (str): The ARN of the deployed agent runtime
    - prompt (str): The input prompt for the agent
    - session_id (str, optional): A unique identifier for the session
    
    Returns:
    - dict: The agent's response
    """
    import json
    import uuid
    
    try:
        # Initialize the Bedrock AgentCore client
        agent_core_client = boto3.client('bedrock-agentcore', region_name=region)
        

        # Try to get Langfuse context, but don't fail if unavailable
        trace_id = None
        obs_id = None
        if langfuse_get_client:
            try:
                client = langfuse_get_client()
                trace_id = client.get_current_trace_id() if client else None
                obs_id = client.get_current_observation_id() if client else None
            except Exception as e:
                print(f"Note: Langfuse context not available: {str(e)}")

        # Prepare the payload
        payload = json.dumps({"prompt": prompt, 
        "trace_id": trace_id, 
        "parent_obs_id": obs_id
        }).encode()
        
        # Generate session_id if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
        



        # Invoke the agent
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload
        )
        
        # Process the response based on content type
        content_type = response.get("contentType", "")
        
        if "text/event-stream" in content_type:
            # Handle streaming response - extract only text from contentBlockDelta events
            extracted_text = []

            # Read the entire stream
            stream = response["response"]
            stream_data = stream.read().decode('utf-8', errors='replace')

            # Process line by line (Server-Sent Events format)
            for line in stream_data.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # SSE format: lines start with "data: "
                if line.startswith('data: '):
                    line = line[6:]  # Remove "data: " prefix

                # Skip empty lines after prefix removal
                if not line:
                    continue

                # Skip Python debug output (starts with "{'data':")
                if line.startswith('"{') and ("'data':" in line or '"data":' in line):
                    continue

                # Must be valid JSON starting with {
                if not line.startswith('{'):
                    continue

                # Try to parse as JSON event
                try:
                    event = json.loads(line)

                    # Extract text from contentBlockDelta events
                    if isinstance(event, dict) and 'event' in event:
                        event_data = event['event']
                        if isinstance(event_data, dict) and 'contentBlockDelta' in event_data:
                            delta = event_data['contentBlockDelta'].get('delta', {})
                            if isinstance(delta, dict) and 'text' in delta:
                                extracted_text.append(delta['text'])
                except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                    # Skip lines that aren't valid JSON or don't have expected structure
                    continue

            return {
                'response': ''.join(extracted_text),
                'session_id': session_id,
                'content_type': content_type
            }
        
        elif content_type == "application/json":
            # Handle standard JSON response
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8', errors='replace'))

            return {
                'response': json.loads(''.join(content)),
                'session_id': session_id,
                'content_type': content_type
            }
        
        else:
            # Return raw response for other content types
            return {
                'response': response,
                'session_id': session_id,
                'content_type': content_type
            }
            
    except Exception as e:
        return {
            'error': str(e),
            'agent_arn': agent_arn
        }


def delete_agent(agent_runtime_id, ecr_uri):
    """
    Deletes an Amazon Bedrock AgentCore Runtime agent and its ECR repository.
    
    Parameters:
    - agent_runtime_id (str): The agent runtime ID to delete
    - ecr_uri (str): The ECR URI of the agent's container repository
    
    Returns:
    - dict: The status of the deletion operation
    """
    try:
        # Initialize the Bedrock AgentCore Control client
        agentcore_control_client = boto3.client(
            'bedrock-agentcore-control',
            region_name=region
        )
        
        # Initialize the ECR client
        ecr_client = boto3.client(
            'ecr',
            region_name=region
        )
        
        # Delete the agent runtime
        runtime_delete_response = agentcore_control_client.delete_agent_runtime(
            agentRuntimeId=agent_runtime_id,
        )

        print(f'ECR repository: {ecr_uri}')
        
        # Delete the ECR repository
        repository_name_tmp = ecr_uri.split('/')[1] if '/' in ecr_uri else ecr_uri

        print(f'Repository name 1: {repository_name_tmp}')

        repository_name = repository_name_tmp.split(':')[0] if ':' in repository_name_tmp else repository_name_tmp

        print(f'Repository name 1: {repository_name}')

        print(f"Deleting ECR repository: {repository_name}")

        ecr_delete_response = ecr_client.delete_repository(
            repositoryName=repository_name,
            force=True
        )
        
        return {
            'status': 'success',
            'agent_runtime_id': agent_runtime_id,
            'runtime_delete_response': runtime_delete_response,
            'ecr_delete_response': ecr_delete_response
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'agent_runtime_id': agent_runtime_id,
            'error': str(e)
        }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Bedrock AgentCore agent utilities")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Invoke command
    invoke_parser = subparsers.add_parser('invoke', help='Invoke an agent')
    invoke_parser.add_argument('agent_arn', help='ARN of the agent to invoke')
    invoke_parser.add_argument('prompt', help='Prompt to send to the agent')
    invoke_parser.add_argument('--session-id', help='Session ID (optional)', default=None)

    args = parser.parse_args()

    if args.command == 'invoke':
        print(f"\n{'='*80}")
        print("INVOKING AGENT")
        print(f"{'='*80}")
        print(f"Agent ARN: {args.agent_arn}")
        print(f"Prompt: {args.prompt}\n")

        result = invoke_agent(args.agent_arn, args.prompt, args.session_id)

        print(f"{'='*80}")
        print("RESPONSE")
        print(f"{'='*80}\n")
        print(json.dumps(result, indent=2, default=str))
        print(f"\n{'='*80}\n")
    else:
        parser.print_help()

