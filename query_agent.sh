#!/bin/bash
#
# Query Agent Script
# Quick utility to query the SAP Agent with example questions
#
# Usage:
#   ./query_agent.sh                          # Interactive mode - select from example questions
#   ./query_agent.sh "hello"        # Direct query
#   ./query_agent.sh --environment PRD        # Query PRD environment (default: TST)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENVIRONMENT="TST"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [QUESTION]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Environment to query (TST or PRD, default: TST)"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Interactive mode"
            echo "  $0 'מה המידע על הזמנה 4500000520?'   # Direct query (use single quotes)"
            echo "  $0 -e PRD 'מי הספק?'"
            exit 0
            ;;
        *)
            CUSTOM_QUESTION="$1"
            shift
            ;;
    esac
done

# Get agent ARN from hp_config.json
# Convert environment to lowercase
ENV_LOWER=$(echo "$ENVIRONMENT" | tr '[:upper:]' '[:lower:]')
AGENT_ARN=$(python3 -c "
import json
with open('cicd/hp_config.json', 'r') as f:
    config = json.load(f)
    print(config.get('$ENV_LOWER', {}).get('agent_arn', ''))
")

if [ -z "$AGENT_ARN" ]; then
    echo -e "${RED}Error: Could not find agent ARN for environment ${ENVIRONMENT}${NC}"
    echo "Make sure the agent is deployed."
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           SAP Agent Query Tool                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} ${ENVIRONMENT}"
echo -e "${GREEN}Agent ARN:${NC} ${AGENT_ARN}"
echo ""

# Example questions
declare -a QUESTIONS=(
    "מה המידע על הזמנת רכש 4500000520?"
    "כמה פריטים יש בהזמנת רכש 4500000520?"
    "מה הערך הכולל של הזמנת רכש 4500000520?"
    "מי הספק של הזמנה 4500000520?"
    "מה מצב המלאי של המוצר MZ-RM-C990-01?"
    "תן לי פרטים על גלגלי BKC-990"
    "מה המחיר ליחידה של כל פריט בהזמנה 4500000520?"
    "אילו פריטים צריך להזמין מחדש?"
)

declare -a DESCRIPTIONS=(
    "Get complete purchase order details"
    "Check item count in purchase order"
    "Get total value of purchase order"
    "Get supplier information"
    "Check inventory status of a product"
    "Get product details (wheels)"
    "Get unit price breakdown"
    "Get reorder recommendations"
)

# If custom question provided, use it
if [ ! -z "$CUSTOM_QUESTION" ]; then
    QUESTION="$CUSTOM_QUESTION"
else
    # Interactive mode - show menu
    echo -e "${YELLOW}Select a question to ask the agent:${NC}"
    echo ""

    for i in "${!QUESTIONS[@]}"; do
        echo -e "${GREEN}$((i+1)).${NC} ${DESCRIPTIONS[$i]}"
        echo -e "   ${BLUE}${QUESTIONS[$i]}${NC}"
        echo ""
    done

    echo -e "${GREEN}9.${NC} Custom question (enter your own)"
    echo ""

    read -p "Enter your choice (1-9): " choice

    if [ "$choice" -eq 9 ]; then
        echo ""
        read -p "Enter your question: " QUESTION
    elif [ "$choice" -ge 1 ] && [ "$choice" -le 8 ]; then
        QUESTION="${QUESTIONS[$((choice-1))]}"
    else
        echo -e "${RED}Invalid choice${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Question:${NC} ${QUESTION}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Query the agent
echo -e "${BLUE}Querying agent...${NC}"
echo ""

python3 -c "
from utils.agent import invoke_agent
import sys
import json

result = invoke_agent(
    agent_arn='${AGENT_ARN}',
    prompt='''${QUESTION}'''
)

if 'error' in result:
    print(f'Error: {result[\"error\"]}', file=sys.stderr)
    sys.exit(1)
elif 'response' in result:
    response = result['response']
    # Handle different response types
    if isinstance(response, str):
        print(response)
    elif isinstance(response, dict):
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        print(str(response))
    sys.exit(0)
else:
    print('Error: Unexpected response format', file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)
"

EXIT_CODE=$?

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Query completed successfully${NC}"
else
    echo -e "${RED}✗ Query failed${NC}"
fi

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit $EXIT_CODE
