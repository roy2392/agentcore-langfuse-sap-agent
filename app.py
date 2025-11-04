#!/usr/bin/env python3
"""
Simple Flask Web UI for SAP Agent
Provides a chat interface to interact with the Bedrock AgentCore agent
"""

import os
import sys
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.agent import invoke_agent

# Load agent configuration
import json
with open('cicd/hp_config.json', 'r') as f:
    config = json.load(f)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['JSON_AS_ASCII'] = False
CORS(app)

# Default to PRD environment, can be changed via env var
DEFAULT_ENV = os.getenv('AGENT_ENV', 'PRD').upper()

# Get AGENT_ARN from environment variable first, then fallback to config file
AGENT_ARN = os.getenv('AGENT_ARN')
if not AGENT_ARN:
    AGENT_ARN = config.get(DEFAULT_ENV.lower(), {}).get('agent_arn', '')

@app.route('/')
def index():
    """Render the chat interface"""
    return render_template('index.html', environment=DEFAULT_ENV)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        environment = data.get('environment', DEFAULT_ENV)

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        session_id = session['session_id']

        # Get agent ARN for the environment
        agent_arn = config.get(environment.lower(), {}).get('agent_arn', AGENT_ARN)

        if not agent_arn:
            return jsonify({'error': f'No agent configured for environment {environment}'}), 400

        # Invoke the agent
        result = invoke_agent(
            agent_arn=agent_arn,
            prompt=user_message,
            session_id=session_id
        )

        if 'error' in result:
            return jsonify({
                'error': result['error'],
                'agent_arn': agent_arn
            }), 500

        # Extract the response
        response_text = result.get('response', '')
        if isinstance(response_text, dict):
            response_text = json.dumps(response_text, ensure_ascii=False, indent=2)

        return jsonify({
            'response': response_text,
            'session_id': session_id,
            'environment': environment
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset the conversation session"""
    session.pop('session_id', None)
    return jsonify({'status': 'success', 'message': 'Session reset'})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'environment': DEFAULT_ENV})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    print(f"\n{'='*60}")
    print(f"SAP Agent Web UI")
    print(f"{'='*60}")
    print(f"Environment: {DEFAULT_ENV}")
    print(f"Agent ARN: {AGENT_ARN}")
    print(f"Running on: http://localhost:{port}")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
