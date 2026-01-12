#!/usr/bin/env python3
"""
CFN Generator - AWS CloudFormation Template Generator
======================================================

A standalone script to interactively generate CloudFormation/SAM templates
for serverless applications. No installation required.

Usage:
    python cfn_generate.py                    # Interactive mode
    python cfn_generate.py --quick            # Quick mode with defaults
    python cfn_generate.py -o ./my-project    # Specify output directory
    python cfn_generate.py --help             # Show help

Author: DevOps Team
Version: 1.0.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List

__version__ = "1.0.0"


# ============================================================================
# TERMINAL COLORS
# ============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

    @staticmethod
    def disable():
        """Disable colors for non-TTY output."""
        Colors.HEADER = Colors.BLUE = Colors.CYAN = ''
        Colors.GREEN = Colors.YELLOW = Colors.RED = ''
        Colors.BOLD = Colors.END = ''


# Disable colors if not running in terminal
if not sys.stdout.isatty():
    Colors.disable()


# ============================================================================
# PRINT HELPERS
# ============================================================================
def print_header(text: str):
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> {text}{Colors.END}")
    print(f"{Colors.BLUE}{'-' * 50}{Colors.END}")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.YELLOW}ℹ {text}{Colors.END}")


# ============================================================================
# INPUT HELPERS
# ============================================================================
def prompt(text: str, default: str = None) -> str:
    """Prompt user for input with optional default value."""
    try:
        if default:
            result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default}{Colors.END}]: ").strip()
            return result if result else default
        return input(f"{Colors.BOLD}{text}{Colors.END}: ").strip()
    except EOFError:
        return default or ""


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Prompt user for yes/no input."""
    try:
        default_str = "Y/n" if default else "y/N"
        result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default_str}{Colors.END}]: ").strip().lower()
        if not result:
            return default
        return result in ('y', 'yes', 'true', '1')
    except EOFError:
        return default


def prompt_choice(text: str, choices: List[str], default: int = 0) -> int:
    """Prompt user to choose from a list of options."""
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    for i, choice in enumerate(choices):
        marker = f"{Colors.GREEN}*{Colors.END}" if i == default else " "
        print(f"  {marker} [{i + 1}] {choice}")

    while True:
        try:
            result = input(f"\nEnter choice (1-{len(choices)}) [{default + 1}]: ").strip()
            if not result:
                return default
            idx = int(result) - 1
            if 0 <= idx < len(choices):
                return idx
        except (ValueError, EOFError):
            pass
        print_error(f"Invalid choice. Please enter 1-{len(choices)}")


def prompt_multi_choice(text: str, choices: List[str]) -> List[int]:
    """Prompt user to select multiple options."""
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.YELLOW}(Enter numbers separated by commas, or 'all' for all options){Colors.END}")
    for i, choice in enumerate(choices):
        print(f"  [{i + 1}] {choice}")

    while True:
        try:
            result = input(f"\nEnter choices: ").strip().lower()
            if result == 'all':
                return list(range(len(choices)))
            if not result:
                return []
            indices = [int(x.strip()) - 1 for x in result.split(',')]
            if all(0 <= idx < len(choices) for idx in indices):
                return indices
        except (ValueError, EOFError):
            pass
        print_error("Invalid input. Enter numbers separated by commas (e.g., 1,3,5)")


# ============================================================================
# CLOUDFORMATION GENERATOR CLASS
# ============================================================================
class CloudFormationGenerator:
    """Main class for generating CloudFormation templates."""

    def __init__(self):
        self.project_name = "serverless-app"
        self.parameters = {
            "EnvironmentName": {
                "type": "String", "default": "dev",
                "allowed_values": ["dev", "staging", "prod"],
                "description": "Environment name (dev, staging, prod)"
            },
            "ApplicationName": {
                "type": "String", "default": "serverless-app",
                "description": "Application name used for resource naming"
            },
            "LogRetentionDays": {
                "type": "Number", "default": "14",
                "allowed_values": ["7", "14", "30", "60", "90"],
                "description": "CloudWatch log retention in days"
            }
        }

        # Resource flags
        self.has_api_gateway = False
        self.has_authorizer = False
        self.has_glue = False
        self.has_step_functions = False
        self.has_sns = False
        self.has_secrets = False
        self.has_dynamodb = False
        self.has_sqs = False

        # Resource configurations
        self.lambda_functions = []
        self.glue_jobs = []
        self.step_functions = []
        self.sns_topics = []
        self.s3_buckets = []
        self.dynamodb_tables = []
        self.sqs_queues = []
        self.outputs = []

    def set_project_name(self, name: str):
        """Set the project/application name."""
        self.project_name = name
        self.parameters["ApplicationName"]["default"] = name

    def add_parameter(self, name: str, param_type: str, default: str = "",
                      description: str = "", allowed_values: List[str] = None):
        """Add a custom parameter to the template."""
        self.parameters[name] = {
            "type": param_type, "default": default, "description": description
        }
        if allowed_values:
            self.parameters[name]["allowed_values"] = allowed_values

    def add_lambda_function(self, name: str, handler: str = "app.handler",
                            code_uri: str = "lambda/", timeout: int = 30,
                            memory_size: int = 256, env_vars: Dict = None,
                            api_events: List[Dict] = None):
        """Add a Lambda function to the template."""
        self.lambda_functions.append({
            "name": name,
            "handler": handler,
            "code_uri": code_uri,
            "timeout": timeout,
            "memory_size": memory_size,
            "env_vars": env_vars or {},
            "api_events": api_events or []
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}FunctionArn",
            "description": f"{name} Lambda function ARN",
            "value": f"!GetAtt {self._pascal(name)}Function.Arn"
        })

    def add_api_gateway(self, with_authorizer: bool = True):
        """Add API Gateway to the template."""
        self.has_api_gateway = True
        self.has_authorizer = with_authorizer
        if with_authorizer:
            self.add_parameter(
                "ValidClientIds", "CommaDelimitedList",
                "client-app-1,client-app-2",
                "Comma-separated list of valid Client IDs for API authorization"
            )
        self.outputs.append({
            "name": "ApiEndpoint",
            "description": "API Gateway endpoint URL",
            "value": "!Sub https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${EnvironmentName}"
        })

    def add_s3_bucket(self, name: str, suffix: str = "data", versioning: bool = False):
        """Add an S3 bucket to the template."""
        self.s3_buckets.append({
            "name": name, "suffix": suffix, "versioning": versioning
        })
        self.outputs.append({
            "name": f"{name}Name",
            "description": f"{name} S3 bucket name",
            "value": f"!Ref {name}"
        })

    def add_glue_job(self, name: str, script_name: str, description: str = "",
                     worker_type: str = "G.1X", num_workers: int = 2, timeout: int = 60):
        """Add a Glue job to the template."""
        self.has_glue = True
        if not any(b["name"] == "GlueDataBucket" for b in self.s3_buckets):
            self.add_s3_bucket("GlueDataBucket", "glue-data")
        self.glue_jobs.append({
            "name": name,
            "script_name": script_name,
            "description": description or f"Glue ETL job for {name}",
            "worker_type": worker_type,
            "num_workers": num_workers,
            "timeout": timeout
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}GlueJobName",
            "description": f"{name} Glue job name",
            "value": f"!Ref {self._pascal(name)}GlueJob"
        })

    def add_step_function(self, name: str, glue_jobs: List[str] = None,
                          lambda_functions: List[str] = None, with_sns: bool = True):
        """Add a Step Functions state machine to the template."""
        self.has_step_functions = True
        if with_sns and not self.has_sns:
            self.add_sns_topic("JobFailure", "failure", "Job Failure Notifications")
        self.step_functions.append({
            "name": name,
            "glue_jobs": glue_jobs or [],
            "lambda_functions": lambda_functions or [],
            "with_sns": with_sns
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}StateMachineArn",
            "description": f"{name} Step Functions state machine ARN",
            "value": f"!Ref {self._pascal(name)}StateMachine"
        })

    def add_sns_topic(self, name: str, suffix: str, display_name: str, email_count: int = 3):
        """Add an SNS topic to the template."""
        self.has_sns = True
        self.sns_topics.append({
            "name": name,
            "suffix": suffix,
            "display_name": display_name,
            "email_count": email_count
        })
        for i in range(1, email_count + 1):
            param_name = f"NotificationEmail{i}"
            if param_name not in self.parameters:
                self.add_parameter(param_name, "String", "", f"Email {i} for SNS notifications")
        self.outputs.append({
            "name": f"{name}TopicArn",
            "description": f"{name} SNS topic ARN",
            "value": f"!Ref {name}Topic"
        })

    def add_dynamodb_table(self, name: str, suffix: str, partition_key: str,
                           pk_type: str = "S", sort_key: str = None, sk_type: str = "S"):
        """Add a DynamoDB table to the template."""
        self.has_dynamodb = True
        self.dynamodb_tables.append({
            "name": name, "suffix": suffix,
            "pk": partition_key, "pk_type": pk_type,
            "sk": sort_key, "sk_type": sk_type
        })
        self.outputs.append({
            "name": f"{name}TableName",
            "description": f"{name} DynamoDB table name",
            "value": f"!Ref {name}Table"
        })

    def add_sqs_queue(self, name: str, suffix: str, with_dlq: bool = True):
        """Add an SQS queue to the template."""
        self.has_sqs = True
        self.sqs_queues.append({
            "name": name, "suffix": suffix, "with_dlq": with_dlq
        })
        self.outputs.append({
            "name": f"{name}QueueUrl",
            "description": f"{name} SQS queue URL",
            "value": f"!Ref {name}Queue"
        })

    def add_secrets_manager(self):
        """Add Secrets Manager secret to the template."""
        self.has_secrets = True
        self.outputs.append({
            "name": "ApplicationSecretArn",
            "description": "Application secret ARN",
            "value": "!Ref ApplicationSecret"
        })

    def _pascal(self, name: str) -> str:
        """Convert string to PascalCase."""
        return ''.join(w.capitalize() for w in name.replace('-', '_').split('_'))

    # ========================================================================
    # TEMPLATE GENERATION METHODS
    # ========================================================================
    def generate(self, output_path: str) -> str:
        """Generate the complete CloudFormation template."""
        template = self._build_template()
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(template)
        return template

    def _build_template(self) -> str:
        """Build the complete template string."""
        parts = [
            "AWSTemplateFormatVersion: '2010-09-09'",
            "Transform: AWS::Serverless-2016-10-31",
            f"Description: CloudFormation template for {self.project_name}",
            "",
            f"# Generated by CFN Generator v{__version__}",
            f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            self._gen_parameters(),
            self._gen_conditions(),
            "Resources:",
            self._gen_s3(),
            self._gen_secrets(),
            self._gen_lambda(),
            self._gen_api_gateway(),
            self._gen_glue(),
            self._gen_step_functions(),
            self._gen_sns(),
            self._gen_dynamodb(),
            self._gen_sqs(),
            "",
            self._gen_outputs()
        ]
        template = '\n'.join(p for p in parts if p)
        # Clean up multiple blank lines
        while '\n\n\n' in template:
            template = template.replace('\n\n\n', '\n\n')
        return template

    def _gen_parameters(self) -> str:
        """Generate Parameters section."""
        lines = ["Parameters:"]
        for name, cfg in self.parameters.items():
            lines.append(f"  {name}:")
            lines.append(f"    Type: {cfg['type']}")
            if cfg.get('default'):
                lines.append(f"    Default: {cfg['default']}")
            if cfg.get('description'):
                lines.append(f"    Description: {cfg['description']}")
            if cfg.get('allowed_values'):
                lines.append("    AllowedValues:")
                for v in cfg['allowed_values']:
                    lines.append(f"      - {v}")
            lines.append("")
        return '\n'.join(lines)

    def _gen_conditions(self) -> str:
        """Generate Conditions section."""
        if not self.has_sns:
            return ""
        conds = []
        for t in self.sns_topics:
            for i in range(1, t["email_count"] + 1):
                conds.append(f"  HasNotificationEmail{i}: !Not [!Equals [!Ref NotificationEmail{i}, '']]")
        return "Conditions:\n" + '\n'.join(conds) + "\n" if conds else ""

    def _gen_s3(self) -> str:
        """Generate S3 bucket resources."""
        if not self.s3_buckets:
            return ""
        out = []
        for b in self.s3_buckets:
            out.append(f"""
  {b['name']}:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${{ApplicationName}}-{b['suffix']}-${{AWS::AccountId}}-${{AWS::Region}}
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      VersioningConfiguration:
        Status: {'Enabled' if b['versioning'] else 'Suspended'}""")
        return '\n'.join(out)

    def _gen_secrets(self) -> str:
        """Generate Secrets Manager resources."""
        if not self.has_secrets:
            return ""
        return """
  ApplicationSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub ${ApplicationName}-secrets-${EnvironmentName}
      Description: Application secrets
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: api_key
        PasswordLength: 32
        ExcludeCharacters: '"@/\\\\'"""

    def _gen_lambda(self) -> str:
        """Generate Lambda function resources."""
        if not self.lambda_functions:
            return ""
        out = []
        for f in self.lambda_functions:
            pn = self._pascal(f['name'])

            # API events
            events = ""
            if f['api_events'] and self.has_api_gateway:
                events = "      Events:\n"
                for i, e in enumerate(f['api_events']):
                    events += f"""        Api{i + 1}:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: {e['path']}
            Method: {e['method']}
"""

            out.append(f"""
  {pn}Role:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${{ApplicationName}}-{f['name']}-role-${{EnvironmentName}}
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: {pn}Policy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: '*'

  {pn}Function:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ${{ApplicationName}}-{f['name']}-${{EnvironmentName}}
      Handler: {f['handler']}
      Runtime: python3.9
      CodeUri: {f['code_uri']}
      Role: !GetAtt {pn}Role.Arn
      Timeout: {f['timeout']}
      MemorySize: {f['memory_size']}
      Environment:
        Variables:
          ENVIRONMENT: !Ref EnvironmentName
          APPLICATION_NAME: !Ref ApplicationName
          AWS_REGION_NAME: !Ref AWS::Region
{events}
  {pn}LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/lambda/${{ApplicationName}}-{f['name']}-${{EnvironmentName}}
      RetentionInDays: !Ref LogRetentionDays""")
        return '\n'.join(out)

    def _gen_api_gateway(self) -> str:
        """Generate API Gateway resources."""
        if not self.has_api_gateway:
            return ""

        auth_config = ""
        if self.has_authorizer:
            auth_config = """
      Auth:
        DefaultAuthorizer: ClientIdAuthorizer
        Authorizers:
          ClientIdAuthorizer:
            FunctionArn: !GetAtt ClientIdAuthorizerFunction.Arn
            Identity:
              Headers:
                - Client-ID
              ReauthorizeEvery: 300"""

        out = f"""
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub ${{ApplicationName}}-api-${{EnvironmentName}}
      StageName: !Ref EnvironmentName
      TracingEnabled: true
      Cors:
        AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
        AllowHeaders: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,Client-ID'"
        AllowOrigin: "'*'"
{auth_config}"""

        if self.has_authorizer:
            out += """

  AuthorizerRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${ApplicationName}-authorizer-role-${EnvironmentName}
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

  ClientIdAuthorizerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ${ApplicationName}-authorizer-${EnvironmentName}
      Handler: authorizer.handler
      Runtime: python3.9
      CodeUri: lambda/authorizer/
      Role: !GetAtt AuthorizerRole.Arn
      Timeout: 10
      MemorySize: 128
      Environment:
        Variables:
          VALID_CLIENT_IDS: !Join [',', !Ref ValidClientIds]

  AuthorizerLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/lambda/${ApplicationName}-authorizer-${EnvironmentName}
      RetentionInDays: !Ref LogRetentionDays

  ClientIdAuthorizerPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ClientIdAuthorizerFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiGateway}/*"""
        return out

    def _gen_glue(self) -> str:
        """Generate Glue job resources."""
        if not self.has_glue:
            return ""
        out = ["""
  GlueJobRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${ApplicationName}-glue-role-${EnvironmentName}
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: glue.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
      Policies:
        - PolicyName: GlueS3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:DeleteObject
                  - s3:ListBucket
                Resource:
                  - !Sub arn:aws:s3:::${GlueDataBucket}
                  - !Sub arn:aws:s3:::${GlueDataBucket}/*
              - Effect: Allow
                Action:
                  - logs:CreateLogGroup
                  - logs:CreateLogStream
                  - logs:PutLogEvents
                Resource: '*'"""]

        for j in self.glue_jobs:
            pn = self._pascal(j['name'])
            out.append(f"""
  {pn}GlueJob:
    Type: AWS::Glue::Job
    Properties:
      Name: !Sub ${{ApplicationName}}-{j['name']}-${{EnvironmentName}}
      Description: {j['description']}
      Role: !GetAtt GlueJobRole.Arn
      GlueVersion: '4.0'
      WorkerType: {j['worker_type']}
      NumberOfWorkers: {j['num_workers']}
      Timeout: {j['timeout']}
      Command:
        Name: glueetl
        ScriptLocation: !Sub s3://${{GlueDataBucket}}/scripts/{j['script_name']}
        PythonVersion: '3'
      DefaultArguments:
        '--job-language': python
        '--enable-metrics': 'true'
        '--enable-continuous-cloudwatch-log': 'true'
        '--ENVIRONMENT': !Ref EnvironmentName
        '--APPLICATION_NAME': !Ref ApplicationName
        '--AWS_REGION_NAME': !Ref AWS::Region
        '--GLUE_BUCKET': !Ref GlueDataBucket""")
        return '\n'.join(out)

    def _gen_step_functions(self) -> str:
        """Generate Step Functions resources."""
        if not self.has_step_functions:
            return ""

        # Build permissions
        perms = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
        if self.lambda_functions:
            perms.append("lambda:InvokeFunction")
        if self.has_sns:
            perms.append("sns:Publish")

        out = [f"""
  StepFunctionsRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${{ApplicationName}}-stepfn-role-${{EnvironmentName}}
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: states.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: StepFunctionsExecutionPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - {chr(10).join('                  - ' + p for p in perms).strip().replace('                  - ', '', 1)}
                Resource: '*'
              - Effect: Allow
                Action:
                  - logs:CreateLogDelivery
                  - logs:GetLogDelivery
                  - logs:UpdateLogDelivery
                  - logs:DeleteLogDelivery
                  - logs:ListLogDeliveries
                  - logs:PutResourcePolicy
                  - logs:DescribeResourcePolicies
                  - logs:DescribeLogGroups
                Resource: '*'"""]

        for sf in self.step_functions:
            pn = self._pascal(sf['name'])
            defn = self._build_state_machine(sf)
            indented = '\n'.join('        ' + line for line in defn.split('\n'))
            out.append(f"""
  {pn}StateMachine:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      StateMachineName: !Sub ${{ApplicationName}}-{sf['name']}-${{EnvironmentName}}
      RoleArn: !GetAtt StepFunctionsRole.Arn
      TracingConfiguration:
        Enabled: true
      DefinitionString: !Sub |
{indented}

  {pn}LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/stepfunctions/${{ApplicationName}}-{sf['name']}-${{EnvironmentName}}
      RetentionInDays: !Ref LogRetentionDays""")
        return '\n'.join(out)

    def _build_state_machine(self, sf: Dict) -> str:
        """Build a state machine definition."""
        states = {}
        order = []

        # Add Glue job states
        for j in sf.get('glue_jobs', []):
            st = f"Run{self._pascal(j)}"
            order.append(st)
            states[st] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::glue:startJobRun.sync",
                "Parameters": {
                    "JobName": f"${{ApplicationName}}-{j}-${{EnvironmentName}}",
                    "Arguments": {
                        "--INPUT_PATH.$": "$.inputPath",
                        "--OUTPUT_PATH.$": "$.outputPath"
                    }
                }
            }

        # Add Lambda invocation states
        for f in sf.get('lambda_functions', []):
            st = f"Invoke{self._pascal(f)}"
            order.append(st)
            states[st] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": f"${{ApplicationName}}-{f}-${{EnvironmentName}}",
                    "Payload.$": "$"
                },
                "ResultPath": f"$.{f}Result"
            }

        # Add success state
        order.append("JobSucceeded")
        states["JobSucceeded"] = {"Type": "Pass", "End": True}

        # Link states
        for i, s in enumerate(order[:-1]):
            states[s]["Next"] = order[i + 1]
            if sf.get('with_sns') and s.startswith("Run"):
                states[s]["Catch"] = [{
                    "ErrorEquals": ["States.ALL"],
                    "ResultPath": "$.error",
                    "Next": "NotifyFailure"
                }]

        # Add failure notification
        if sf.get('with_sns'):
            states["NotifyFailure"] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::sns:publish",
                "Parameters": {
                    "TopicArn": "${JobFailureTopicArn}",
                    "Subject": "Step Function Execution Failed",
                    "Message.$": "States.Format('Execution failed. Error: {}', $.error)"
                },
                "Next": "JobFailed"
            }
            states["JobFailed"] = {
                "Type": "Fail",
                "Error": "JobExecutionFailed",
                "Cause": "One or more jobs failed during execution"
            }

        return json.dumps({
            "Comment": f"State machine for {sf['name']}",
            "StartAt": order[0] if order else "JobSucceeded",
            "States": states
        }, indent=2)

    def _gen_sns(self) -> str:
        """Generate SNS topic resources."""
        if not self.has_sns:
            return ""
        out = []
        for t in self.sns_topics:
            out.append(f"""
  {t['name']}Topic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub ${{ApplicationName}}-{t['suffix']}-${{EnvironmentName}}
      DisplayName: {t['display_name']}""")

            for i in range(1, t['email_count'] + 1):
                out.append(f"""
  {t['name']}Subscription{i}:
    Type: AWS::SNS::Subscription
    Condition: HasNotificationEmail{i}
    Properties:
      TopicArn: !Ref {t['name']}Topic
      Protocol: email
      Endpoint: !Ref NotificationEmail{i}""")
        return '\n'.join(out)

    def _gen_dynamodb(self) -> str:
        """Generate DynamoDB table resources."""
        if not self.has_dynamodb:
            return ""
        out = []
        for t in self.dynamodb_tables:
            attrs = f"        - AttributeName: {t['pk']}\n          AttributeType: {t['pk_type']}"
            keys = f"        - AttributeName: {t['pk']}\n          KeyType: HASH"
            if t['sk']:
                attrs += f"\n        - AttributeName: {t['sk']}\n          AttributeType: {t['sk_type']}"
                keys += f"\n        - AttributeName: {t['sk']}\n          KeyType: RANGE"

            out.append(f"""
  {t['name']}Table:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${{ApplicationName}}-{t['suffix']}-${{EnvironmentName}}
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
{attrs}
      KeySchema:
{keys}
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true""")
        return '\n'.join(out)

    def _gen_sqs(self) -> str:
        """Generate SQS queue resources."""
        if not self.has_sqs:
            return ""
        out = []
        for q in self.sqs_queues:
            if q['with_dlq']:
                out.append(f"""
  {q['name']}QueueDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{q['suffix']}-dlq-${{EnvironmentName}}
      MessageRetentionPeriod: 1209600""")

            dlq_cfg = f"""
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt {q['name']}QueueDLQ.Arn
        maxReceiveCount: 3""" if q['with_dlq'] else ""

            out.append(f"""
  {q['name']}Queue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{q['suffix']}-${{EnvironmentName}}
      VisibilityTimeout: 30
      MessageRetentionPeriod: 345600{dlq_cfg}""")
        return '\n'.join(out)

    def _gen_outputs(self) -> str:
        """Generate Outputs section."""
        if not self.outputs:
            return ""
        lines = ["Outputs:"]
        for o in self.outputs:
            lines.extend([
                f"  {o['name']}:",
                f"    Description: {o['description']}",
                f"    Value: {o['value']}",
                ""
            ])
        return '\n'.join(lines)

    # ========================================================================
    # ADDITIONAL FILE GENERATION
    # ========================================================================
    def generate_env_config(self, env: str, path: str):
        """Generate environment configuration file."""
        cfg = {
            "Parameters": {},
            "Tags": {
                "Environment": env,
                "Application": self.project_name,
                "ManagedBy": "CloudFormation"
            }
        }
        for n, p in self.parameters.items():
            cfg["Parameters"][n] = p.get("default", "")

        cfg["Parameters"]["EnvironmentName"] = env
        if env == "staging":
            cfg["Parameters"]["LogRetentionDays"] = "30"
        elif env == "prod":
            cfg["Parameters"]["LogRetentionDays"] = "90"

        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2)

    def generate_buildspec(self, path: str):
        """Generate buildspec.yml for CodeBuild."""
        buildspec = f"""version: 0.2

env:
  variables:
    SAM_TEMPLATE: serverless-app-template.yml
    PACKAGED_TEMPLATE: packaged-template.yaml
    APPLICATION_NAME: {self.project_name}
    ENVIRONMENT_NAME: dev

phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - echo "Installing SAM CLI..."
      - pip install aws-sam-cli
      - sam --version

  pre_build:
    commands:
      - echo "Running pre-build checks..."
      - python --version
      - aws --version

  build:
    commands:
      - echo "Building SAM application..."
      - sam build --template ${{SAM_TEMPLATE}}
      
      - echo "Packaging SAM application..."
      - sam package \\
          --template-file .aws-sam/build/template.yaml \\
          --output-template-file ${{PACKAGED_TEMPLATE}} \\
          --s3-bucket ${{ARTIFACT_BUCKET}}

  post_build:
    commands:
      - echo "Build completed successfully!"

artifacts:
  files:
    - packaged-template.yaml
    - dev.json
    - staging.json
    - prod.json
  discard-paths: yes

cache:
  paths:
    - '/root/.cache/pip/**/*'
"""
        with open(path, 'w') as f:
            f.write(buildspec)

    def to_json(self, path: str):
        """Save configuration to JSON file."""
        config = {
            "project_name": self.project_name,
            "lambda_functions": self.lambda_functions,
            "glue_jobs": self.glue_jobs,
            "step_functions": self.step_functions,
            "sns_topics": self.sns_topics,
            "s3_buckets": self.s3_buckets,
            "dynamodb_tables": self.dynamodb_tables,
            "sqs_queues": self.sqs_queues,
            "has_api_gateway": self.has_api_gateway,
            "has_authorizer": self.has_authorizer,
            "has_secrets": self.has_secrets
        }
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)


# ============================================================================
# LAMBDA CODE GENERATORS
# ============================================================================
def generate_lambda_stub(name: str) -> str:
    """Generate Lambda function stub code."""
    return f'''"""
Lambda function: {name}
"""
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
APPLICATION_NAME = os.environ.get('APPLICATION_NAME', 'serverless-app')


def handler(event, context):
    """Main Lambda handler."""
    logger.info(f"Event: {{json.dumps(event)}}")
    
    try:
        # TODO: Implement your logic here
        
        return {{
            'statusCode': 200,
            'headers': {{
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }},
            'body': json.dumps({{
                'message': 'Success',
                'environment': ENVIRONMENT,
                'function': '{name}'
            }})
        }}
    except Exception as e:
        logger.error(f"Error: {{str(e)}}")
        return {{
            'statusCode': 500,
            'headers': {{'Content-Type': 'application/json'}},
            'body': json.dumps({{'error': str(e)}})
        }}
'''


def generate_authorizer_stub() -> str:
    """Generate API Gateway authorizer stub code."""
    return '''"""
API Gateway Client-ID Header Authorizer
"""
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_CLIENT_IDS = [cid.strip() for cid in os.environ.get('VALID_CLIENT_IDS', '').split(',')]


def handler(event, context):
    """Validate Client-ID header and return IAM policy."""
    logger.info(f"Authorizer event: {event}")
    
    headers = event.get('headers', {})
    client_id = headers.get('Client-ID') or headers.get('client-id') or headers.get('CLIENT-ID')
    method_arn = event.get('methodArn', '')
    
    # Extract base ARN for caching
    arn_parts = method_arn.split('/')
    base_arn = '/'.join(arn_parts[:2]) if len(arn_parts) >= 2 else method_arn
    resource_arn = f"{base_arn}/*"
    
    if client_id and client_id.strip() in VALID_CLIENT_IDS:
        logger.info(f"Authorized client: {client_id}")
        effect = 'Allow'
    else:
        logger.warning(f"Unauthorized client: {client_id}")
        effect = 'Deny'
    
    return {
        'principalId': client_id or 'unknown',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource_arn
            }]
        },
        'context': {
            'clientId': client_id or 'unknown'
        }
    }
'''


def generate_glue_script(job_name: str) -> str:
    """Generate Glue ETL script stub."""
    return f'''"""
Glue ETL Job: {job_name}
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# Get job arguments
args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'INPUT_PATH', 'OUTPUT_PATH',
    'ENVIRONMENT', 'APPLICATION_NAME', 'AWS_REGION_NAME', 'GLUE_BUCKET'
])

# Initialize contexts
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Log configuration
print(f"Job: {{args['JOB_NAME']}}")
print(f"Environment: {{args['ENVIRONMENT']}}")
print(f"Input: {{args['INPUT_PATH']}}")
print(f"Output: {{args['OUTPUT_PATH']}}")

# ============================================================================
# TODO: Implement your ETL logic here
# ============================================================================

# Example: Read CSV
# input_df = spark.read.csv(args['INPUT_PATH'], header=True, inferSchema=True)

# Example: Transform
# transformed_df = input_df.filter(input_df['column'] > 0)

# Example: Write Parquet
# transformed_df.write.mode('overwrite').parquet(args['OUTPUT_PATH'])

# ============================================================================

job.commit()
print("Job completed successfully!")
'''


# ============================================================================
# INTERACTIVE CLI
# ============================================================================
def configure_resources(gen: CloudFormationGenerator):
    """Interactive resource configuration."""
    resources = [
        ("API Gateway", "REST API with Client-ID authorization"),
        ("Lambda Functions", "Serverless compute functions"),
        ("S3 Buckets", "Object storage buckets"),
        ("Glue Jobs", "ETL/data processing jobs"),
        ("Step Functions", "Workflow orchestration"),
        ("SNS Topics", "Notification service"),
        ("DynamoDB Tables", "NoSQL database tables"),
        ("SQS Queues", "Message queues"),
        ("Secrets Manager", "Secure secrets storage"),
    ]

    print_section("Select Resources to Include")
    choices = [f"{n} - {d}" for n, d in resources]
    selected = prompt_multi_choice("Available resources:", choices)
    names = [resources[i][0] for i in selected]

    lambda_funcs, glue_jobs = [], []

    # API Gateway
    if "API Gateway" in names:
        print_section("API Gateway Configuration")
        auth = prompt_yes_no("Include Client-ID authorization?", True)
        gen.add_api_gateway(with_authorizer=auth)
        if auth:
            client_ids = prompt("Default Client IDs (comma-separated)", "client-app-1,client-app-2")
            gen.parameters["ValidClientIds"]["default"] = client_ids
        print_success("API Gateway configured")

    # Lambda Functions
    if "Lambda Functions" in names:
        print_section("Lambda Functions Configuration")
        while True:
            name = prompt("Function name (empty to finish)")
            if not name:
                if not lambda_funcs:
                    print_info("At least one function recommended")
                break
            handler = prompt("Handler", f"{name.replace('-', '_')}.handler")
            code_uri = prompt("Code URI", f"lambda/{name}/")
            timeout = int(prompt("Timeout (seconds)", "30"))
            memory = int(prompt("Memory (MB)", "256"))

            events = []
            if gen.has_api_gateway and prompt_yes_no("Add API endpoints?", True):
                while True:
                    path = prompt("Endpoint path (empty to finish)", "")
                    if not path:
                        break
                    method = prompt("HTTP method", "GET").upper()
                    events.append({"path": path, "method": method})

            gen.add_lambda_function(name, handler, code_uri, timeout, memory, api_events=events)
            lambda_funcs.append(name)
            print_success(f"Lambda function '{name}' added")

    # S3 Buckets
    if "S3 Buckets" in names:
        print_section("S3 Buckets Configuration")
        while True:
            name = prompt("Bucket logical name (empty to finish)")
            if not name:
                break
            suffix = prompt("Bucket name suffix", "data")
            versioning = prompt_yes_no("Enable versioning?", False)
            gen.add_s3_bucket(name, suffix, versioning)
            print_success(f"S3 bucket '{name}' added")

    # Glue Jobs
    if "Glue Jobs" in names:
        print_section("Glue Jobs Configuration")
        while True:
            name = prompt("Job name (empty to finish)")
            if not name:
                if not glue_jobs:
                    print_info("At least one Glue job recommended")
                break
            script = prompt("Script filename", f"{name.replace('-', '_')}.py")
            desc = prompt("Description", f"Glue ETL job for {name}")
            worker_types = ["G.025X", "G.1X", "G.2X"]
            wt_idx = prompt_choice("Worker type:", [
                "G.025X (2 vCPU, 4GB - smallest)",
                "G.1X (4 vCPU, 16GB - standard)",
                "G.2X (8 vCPU, 32GB - large)"
            ], 1)
            workers = int(prompt("Number of workers", "2"))
            timeout = int(prompt("Timeout (minutes)", "60"))

            gen.add_glue_job(name, script, desc, worker_types[wt_idx], workers, timeout)
            glue_jobs.append(name)
            print_success(f"Glue job '{name}' added")

    # Step Functions
    if "Step Functions" in names:
        print_section("Step Functions Configuration")
        while True:
            name = prompt("State machine name (empty to finish)")
            if not name:
                break

            sel_glue = []
            if glue_jobs:
                print("\nSelect Glue jobs to orchestrate:")
                indices = prompt_multi_choice("Available Glue jobs:", glue_jobs)
                sel_glue = [glue_jobs[i] for i in indices]

            sel_lambda = []
            if lambda_funcs:
                print("\nSelect Lambda functions to invoke:")
                indices = prompt_multi_choice("Available Lambda functions:", lambda_funcs)
                sel_lambda = [lambda_funcs[i] for i in indices]

            with_sns = prompt_yes_no("Send SNS notification on failure?", True)
            gen.add_step_function(name, sel_glue, sel_lambda, with_sns)
            print_success(f"Step Function '{name}' added")

    # SNS Topics
    if "SNS Topics" in names:
        print_section("SNS Topics Configuration")
        while True:
            name = prompt("Topic logical name (empty to finish)")
            if not name:
                break
            suffix = prompt("Topic name suffix", name.lower())
            display = prompt("Display name", f"{name} Notifications")
            emails = int(prompt("Number of email parameters", "3"))
            gen.add_sns_topic(name, suffix, display, emails)
            print_success(f"SNS topic '{name}' added")

    # DynamoDB Tables
    if "DynamoDB Tables" in names:
        print_section("DynamoDB Tables Configuration")
        while True:
            name = prompt("Table logical name (empty to finish)")
            if not name:
                break
            suffix = prompt("Table name suffix", name.lower())
            pk = prompt("Partition key name", "id")
            pk_type = prompt("Partition key type (S/N/B)", "S").upper()
            sk = prompt("Sort key name (empty for none)", "")
            sk_type = "S"
            if sk:
                sk_type = prompt("Sort key type (S/N/B)", "S").upper()
            gen.add_dynamodb_table(name, suffix, pk, pk_type, sk if sk else None, sk_type)
            print_success(f"DynamoDB table '{name}' added")

    # SQS Queues
    if "SQS Queues" in names:
        print_section("SQS Queues Configuration")
        while True:
            name = prompt("Queue logical name (empty to finish)")
            if not name:
                break
            suffix = prompt("Queue name suffix", name.lower())
            dlq = prompt_yes_no("Create dead-letter queue?", True)
            gen.add_sqs_queue(name, suffix, dlq)
            print_success(f"SQS queue '{name}' added")

    # Secrets Manager
    if "Secrets Manager" in names:
        gen.add_secrets_manager()
        print_success("Secrets Manager added")


def generate_files(gen: CloudFormationGenerator, output_dir: str):
    """Generate all output files."""
    print_section("Generating Files")
    os.makedirs(output_dir, exist_ok=True)

    # Main template
    template_path = os.path.join(output_dir, "serverless-app-template.yml")
    gen.generate(template_path)
    print_success(f"serverless-app-template.yml")

    # Environment configs
    for env in ["dev", "staging", "prod"]:
        cfg_path = os.path.join(output_dir, f"{env}.json")
        gen.generate_env_config(env, cfg_path)
        print_success(f"{env}.json")

    # Buildspec
    buildspec_path = os.path.join(output_dir, "buildspec.yml")
    gen.generate_buildspec(buildspec_path)
    print_success("buildspec.yml")

    # Generator config (for reuse)
    config_path = os.path.join(output_dir, "generator-config.json")
    gen.to_json(config_path)
    print_success("generator-config.json")

    # Lambda function stubs
    for f in gen.lambda_functions:
        func_dir = os.path.join(output_dir, f["code_uri"].rstrip('/'))
        os.makedirs(func_dir, exist_ok=True)
        handler_file = f["handler"].split('.')[0] + ".py"
        handler_path = os.path.join(func_dir, handler_file)
        with open(handler_path, 'w') as fp:
            fp.write(generate_lambda_stub(f["name"]))
        print_success(f"{f['code_uri']}{handler_file}")

    # Authorizer stub
    if gen.has_authorizer:
        auth_dir = os.path.join(output_dir, "lambda/authorizer")
        os.makedirs(auth_dir, exist_ok=True)
        auth_path = os.path.join(auth_dir, "authorizer.py")
        with open(auth_path, 'w') as fp:
            fp.write(generate_authorizer_stub())
        print_success("lambda/authorizer/authorizer.py")

    # Glue script stubs
    if gen.glue_jobs:
        glue_dir = os.path.join(output_dir, "glue")
        os.makedirs(glue_dir, exist_ok=True)
        for j in gen.glue_jobs:
            script_path = os.path.join(glue_dir, j["script_name"])
            with open(script_path, 'w') as fp:
                fp.write(generate_glue_script(j["name"]))
            print_success(f"glue/{j['script_name']}")


def display_summary(gen: CloudFormationGenerator):
    """Display configuration summary."""
    print_section("Configuration Summary")
    print(f"  Project Name:      {Colors.CYAN}{gen.project_name}{Colors.END}")
    print(f"  Lambda Functions:  {Colors.CYAN}{len(gen.lambda_functions)}{Colors.END}")
    print(f"  API Gateway:       {Colors.CYAN}{'Yes' if gen.has_api_gateway else 'No'}{Colors.END}")
    if gen.has_api_gateway:
        print(f"    └─ Authorizer:   {Colors.CYAN}{'Yes' if gen.has_authorizer else 'No'}{Colors.END}")
    print(f"  S3 Buckets:        {Colors.CYAN}{len(gen.s3_buckets)}{Colors.END}")
    print(f"  Glue Jobs:         {Colors.CYAN}{len(gen.glue_jobs)}{Colors.END}")
    print(f"  Step Functions:    {Colors.CYAN}{len(gen.step_functions)}{Colors.END}")
    print(f"  SNS Topics:        {Colors.CYAN}{len(gen.sns_topics)}{Colors.END}")
    print(f"  DynamoDB Tables:   {Colors.CYAN}{len(gen.dynamodb_tables)}{Colors.END}")
    print(f"  SQS Queues:        {Colors.CYAN}{len(gen.sqs_queues)}{Colors.END}")
    print(f"  Secrets Manager:   {Colors.CYAN}{'Yes' if gen.has_secrets else 'No'}{Colors.END}")


def interactive_mode(output_dir: str):
    """Run the interactive template generator."""
    print_header("AWS CloudFormation Template Generator")
    print("This tool will help you create a customized CloudFormation/SAM template")
    print("for your serverless application.\n")

    gen = CloudFormationGenerator()

    # Project configuration
    print_section("Project Configuration")
    project_name = prompt("Enter project/application name", "serverless-app")
    gen.set_project_name(project_name)
    print_success(f"Project name: {project_name}")

    # Resource configuration
    configure_resources(gen)

    # Display summary
    display_summary(gen)

    # Confirm and generate
    if prompt_yes_no("\nGenerate template with this configuration?", True):
        generate_files(gen, output_dir)

        print_header("Generation Complete!")
        print(f"Files generated in: {Colors.CYAN}{output_dir}{Colors.END}\n")
        print("Generated files:")
        print(f"  • serverless-app-template.yml  (Main CloudFormation template)")
        print(f"  • buildspec.yml                (CodeBuild configuration)")
        print(f"  • dev.json, staging.json, prod.json (Environment configs)")
        print(f"  • generator-config.json        (Reusable configuration)")
        if gen.lambda_functions:
            print(f"  • lambda/*/                    (Lambda function stubs)")
        if gen.glue_jobs:
            print(f"  • glue/                        (Glue script stubs)")

        print(f"\n{Colors.BOLD}Next steps:{Colors.END}")
        print("  1. Review and customize the generated template")
        print("  2. Update Lambda function code in lambda/ directory")
        print("  3. Update Glue scripts in glue/ directory")
        print("  4. Configure environment parameters in *.json files")
        print("  5. Deploy using: sam build && sam deploy --guided")
    else:
        print_info("Generation cancelled")


def quick_mode(output_dir: str):
    """Quick mode with common defaults."""
    print_header("AWS CloudFormation Template Generator")
    print_info("Quick mode - generating template with common defaults\n")

    project_name = prompt("Enter project name", "serverless-app")

    gen = CloudFormationGenerator()
    gen.set_project_name(project_name)

    # Add common resources
    gen.add_api_gateway(with_authorizer=True)
    gen.add_lambda_function(
        "api",
        handler="app.handler",
        code_uri="lambda/api/",
        api_events=[{"path": "/health", "method": "GET"}]
    )
    gen.add_s3_bucket("DataBucket", "data")
    gen.add_glue_job("etl-processor", "etl_processor.py")
    gen.add_step_function("orchestrator", glue_jobs=["etl-processor"])
    gen.add_secrets_manager()

    display_summary(gen)

    if prompt_yes_no("\nGenerate template?", True):
        generate_files(gen, output_dir)
        print_header("Generation Complete!")
        print(f"Files generated in: {Colors.CYAN}{output_dir}{Colors.END}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AWS CloudFormation Template Generator for Serverless Applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cfn_generate.py                    # Interactive mode
  python cfn_generate.py --quick            # Quick mode with defaults
  python cfn_generate.py -o ./my-project    # Specify output directory
  python cfn_generate.py --version          # Show version

Resources supported:
  • API Gateway (with Client-ID authorization)
  • Lambda Functions
  • S3 Buckets
  • Glue Jobs
  • Step Functions
  • SNS Topics
  • DynamoDB Tables
  • SQS Queues
  • Secrets Manager
"""
    )

    parser.add_argument(
        '--output', '-o',
        metavar='DIR',
        default='./output',
        help='Output directory (default: ./output)'
    )

    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='Quick mode with common defaults'
    )

    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'CFN Generator v{__version__}'
    )

    args = parser.parse_args()

    try:
        if args.quick:
            quick_mode(args.output)
        else:
            interactive_mode(args.output)
    except KeyboardInterrupt:
        print("\n")
        print_info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
