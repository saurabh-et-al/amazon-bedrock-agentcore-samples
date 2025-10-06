"""
Utility functions for Asana Integration Demo AgentCore setup and management.

This module provides helper functions for:
- AWS SSM parameter management
- Cognito user pool setup and authentication
- IAM role and policy creation for AgentCore
- DynamoDB operations
- AWS Secrets Manager operations
- Resource cleanup functions
"""

import json

import boto3
import requests

STS_CLIENT = boto3.client("sts")

# Get AWS account details
REGION = boto3.session.Session().region_name

USERNAME = "testuser"
SECRET_NAME = "asana_integration_demo_agent"

ROLE_NAME = "AgentCoreGwyAsanaIntegrationRole"
POLICY_NAME = "AgentCoreGwyAsanaIntegrationPolicy"

def load_api_spec(file_path: str) -> list:
    """Load API specification from JSON file.
    
    Args:
        file_path: Path to the JSON file containing API specification
        
    Returns:
        List containing the API specification data
        
    Raises:
        ValueError: If the JSON file doesn't contain a list
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data

def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """Get parameter value from AWS Systems Manager Parameter Store.
    
    Args:
        name: Parameter name to retrieve
        with_decryption: Whether to decrypt secure string parameters
        
    Returns:
        Parameter value as string
    """
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]

def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
    """Store parameter value in AWS Systems Manager Parameter Store.
    
    Args:
        name: Parameter name to store
        value: Parameter value to store
        parameter_type: Type of parameter (String, StringList, SecureString)
        with_encryption: Whether to encrypt the parameter as SecureString
    """
    ssm = boto3.client("ssm")

    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }

    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)

def get_cognito_client_secret() -> str:
    """Get Cognito user pool client secret.
    
    Returns:
        Client secret string from Cognito user pool client
    """
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/asana/demo/agentcoregwy/userpool_id"),
        ClientId=get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def fetch_access_token(client_id, client_secret, token_url):
    """Fetch OAuth access token using client credentials flow.
    
    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint URL
        
    Returns:
        Access token string
    """
    data = (f"grant_type=client_credentials&client_id={client_id}"
            f"&client_secret={client_secret}")
    response = requests.post(
        token_url,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30
    )
    return response.json()['access_token']


def delete_gateway(gateway_client, gateway_id):
    """Delete AgentCore gateway and all its targets.
    
    Args:
        gateway_client: Boto3 client for bedrock-agentcore-control
        gateway_id: ID of the gateway to delete
    """
    print("Deleting all targets for gateway", gateway_id)
    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gateway_id,
        maxResults=100
    )
    for item in list_response['items']:
        target_id = item["targetId"]
        print("Deleting target ", target_id)
        gateway_client.delete_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
    print("Deleting gateway ", gateway_id)
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
