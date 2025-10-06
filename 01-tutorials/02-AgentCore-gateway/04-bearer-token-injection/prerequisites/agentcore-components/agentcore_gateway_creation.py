# Import libraries
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
import os
import sys
import boto3
import json
from bedrock_agentcore.identity.auth import requires_access_token
from mcp.client.streamable_http import streamablehttp_client
import requests


from utils import get_ssm_parameter, put_ssm_parameter, load_api_spec, get_cognito_client_secret

sts_client = boto3.client('sts')

# Get AWS account details
REGION = boto3.session.Session().region_name

gateway_client = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)

print("✅ Fetching AgentCore gateway!")

gateway_name = "agentcore-gw-asana-integration"

def create_agentcore_gateway():
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [
                get_ssm_parameter("/app/asana/demo/agentcoregwy/machine_client_id")
            ],
            "discoveryUrl": get_ssm_parameter("/app/asana/demo/agentcoregwy/cognito_discovery_url")
        }
    }

    try:
        # create new gateway
        print(f"Creating gateway in region {REGION} with name: {gateway_name}")

        create_response = gateway_client.create_gateway(
            name=gateway_name,
            roleArn= get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_iam_role"),
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Asana Integration Demo AgentCore Gateway",
        )

        gateway_id = create_response["gatewayId"]

        gateway = {
            "id": gateway_id,
            "name": gateway_name,
            "gateway_url": create_response["gatewayUrl"],
            "gateway_arn": create_response["gatewayArn"],
        }
        put_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id", gateway_id)

        print(f"✅ Gateway created successfully with ID: {gateway_id}")

        return gateway

    except Exception as e:
        # If gateway exists, collect existing gateway ID from SSM
        existing_gateway_id = get_ssm_parameter("/app/asana/demo/agentcoregwy/gateway_id")
        print(f"Found existing gateway with ID: {existing_gateway_id}")
        
        # Get existing gateway details
        gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)
        gateway = {
            "id": existing_gateway_id,
            "name": gateway_response["name"],
            "gateway_url": gateway_response["gatewayUrl"],
            "gateway_arn": gateway_response["gatewayArn"],
        }
        gateway_id = gateway['id']
        return gateway

# gateway_id = create_agentcore_gateway()

def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
        
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data

def add_gateway_target(gateway_id):
    try:
        api_spec_file = "../openapi-spec/openapi_simple.json"

        # Validate API spec file exists
        if not os.path.exists(api_spec_file):
            print(f"❌ API specification file not found: {api_spec_file}")
            sys.exit(1)

        api_spec = load_api_spec(api_spec_file)
        print(f"✅ Loaded API specification file: {api_spec}")


        api_gateway_url = get_ssm_parameter("/app/asana/demo/agentcoregwy/apigateway_url")

        api_spec[0]["servers"][0]["url"] = api_gateway_url

        print(f"✅ Replaced API Gateway URL: {api_gateway_url}")


        print("✅ Creating credential provider...")
        acps = boto3.client(service_name="bedrock-agentcore-control")

        credential_provider_name = "AgentCoreAPIGatewayAPIKey"

        existing_credential_provider_response = acps.get_api_key_credential_provider(
            name=credential_provider_name
        )
        print(f"Found existing credential provider with ARN: {existing_credential_provider_response['credentialProviderArn']}")

        if existing_credential_provider_response['credentialProviderArn'] is None:
            print(f"❌ Credential provider not found, creating new: {credential_provider_name}")
            response=acps.create_api_key_credential_provider(
                name=credential_provider_name,
                apiKey=get_ssm_parameter("/app/asana/demo/agentcoregwy/api_key")
            )

            print(response)
            credentialProviderARN = response['credentialProviderArn']
            print(f"Outbound Credentials provider ARN, {credentialProviderARN}")
        else:
            credentialProviderARN = existing_credential_provider_response['credentialProviderArn']
        
        # API Key credentials provider configuration
        api_key_credential_config = [
            {
                "credentialProviderType" : "API_KEY", 
                "credentialProvider": {
                    "apiKeyCredentialProvider": {
                            "credentialParameterName": "api_key", # Replace this with the name of the api key name expected by the respective API provider. For passing token in the header, use "Authorization"
                            "providerArn": credentialProviderARN,
                            "credentialLocation":"QUERY_PARAMETER", # Location of api key. Possible values are "HEADER" and "QUERY_PARAMETER".
                            #"credentialPrefix": " " # Prefix for the token. Valid values are "Basic". Applies only for tokens.
                    }
                }
            }
        ]

        inline_spec = json.dumps(api_spec[0])
        print(f"✅ Created inline_spec: {inline_spec}")
        # S3 Uri for OpenAPI spec file
        agentcoregwy_openapi_target_config = {
            "mcp": {
                "openApiSchema": {
                    "inlinePayload": inline_spec
                }
            }
        }
        print("✅ Creating gateway target...")
        create_target_response = gateway_client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="AgentCoreGwyAPIGatewayTarget",
            description="APIGateway Target for Asana and other 3P APIs",
            targetConfiguration=agentcoregwy_openapi_target_config,
            credentialProviderConfigurations=api_key_credential_config,
        )

        print(f"✅ Gateway target created: {create_target_response['targetId']}")

    except Exception as e:
        print(f"❌ Error creating gateway target: {str(e)}")


gateway = create_agentcore_gateway()
add_gateway_target(gateway["id"])
