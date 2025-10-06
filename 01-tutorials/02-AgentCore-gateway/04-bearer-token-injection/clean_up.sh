#!/bin/sh

# Enable strict error handling
set -euo pipefail

# ----- Config -----
INFRA_STACK_NAME=${1:-AsanaIntegrationStackInfra}
COGNITO_STACK_NAME=${2:-AsanaIntegrationStackCognito}
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

echo "🧹 Starting cleanup process..."
echo "Region: $REGION"
echo "Infrastructure Stack: $INFRA_STACK_NAME"
echo "Cognito Stack: $COGNITO_STACK_NAME"

# Function to delete a CloudFormation stack
delete_stack() {
    local stack_name=$1
    
    echo "🗑️  Checking if stack $stack_name exists..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" >/dev/null 2>&1; then
        echo "📦 Deleting stack: $stack_name"
        
        aws cloudformation delete-stack \
            --stack-name "$stack_name" \
            --region "$REGION"
        
        echo "⏳ Waiting for stack $stack_name to be deleted..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$stack_name" \
            --region "$REGION"
        
        echo "✅ Stack $stack_name deleted successfully"
    else
        echo "ℹ️  Stack $stack_name does not exist or is already deleted"
    fi
}

# Delete stacks in reverse order (infrastructure first, then cognito)
echo "🔧 Deleting infrastructure stack first..."
delete_stack "$INFRA_STACK_NAME"

echo "🔧 Deleting Cognito stack..."
delete_stack "$COGNITO_STACK_NAME"

echo "🎉 Cleanup complete! Both stacks have been deleted."