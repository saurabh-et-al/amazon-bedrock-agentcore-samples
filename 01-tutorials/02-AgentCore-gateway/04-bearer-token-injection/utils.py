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

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Dict
import requests
import boto3
import yaml
from boto3.session import Session

sts_client = boto3.client("sts")

# Get AWS account details
REGION = boto3.session.Session().region_name

username = "testuser"
secret_name = "asana_integration_demo_agent"

role_name = "AgentCoreGwyAsanaIntegrationRole"
policy_name = "AgentCoreGwyAsanaIntegrationPolicy"

def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data

def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]

def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
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
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/asana/demo/agentcoregwy/userpool_id"),
        ClientId=get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def fetch_access_token(client_id, client_secret, token_url):
    response = requests.post(
        token_url,
        data="grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}".format(client_id=client_id, client_secret=client_secret),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

    return response.json()['access_token']
  
    
def delete_gateway(gateway_client,gatewayId): 
    print("Deleting all targets for gateway", gatewayId)
    list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier = gatewayId,
            maxResults=100
    )
    for item in list_response['items']:
        targetId = item["targetId"]
        print("Deleting target ", targetId)
        gateway_client.delete_gateway_target(
            gatewayIdentifier = gatewayId,
            targetId = targetId
        )
    print("Deleting gateway ", gatewayId)
    gateway_client.delete_gateway(gatewayIdentifier = gatewayId)
