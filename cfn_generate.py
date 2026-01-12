#!/usr/bin/env python3
"""
CFN Generator - Standalone Script Version

This is a single-file version of the CloudFormation template generator
that can be run directly without installation.

Usage:
    python cfn_generate.py              # Interactive mode
    python cfn_generate.py --quick      # Quick mode with defaults
    python cfn_generate.py --help       # Show help
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any


# ============================================================================
# ANSI Colors for Terminal Output
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


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_section(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> {text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*50}{Colors.END}")


def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str):
    print(f"{Colors.YELLOW}ℹ {text}{Colors.END}")


def prompt(text: str, default: str = None) -> str:
    if default:
        result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default}{Colors.END}]: ").strip()
        return result if result else default
    return input(f"{Colors.BOLD}{text}{Colors.END}: ").strip()


def prompt_yes_no(text: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default_str}{Colors.END}]: ").strip().lower()
    if not result:
        return default
    return result in ('y', 'yes', 'true', '1')


def prompt_choice(text: str, choices: List[str], default: int = 0) -> int:
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    for i, choice in enumerate(choices):
        marker = f"{Colors.GREEN}*{Colors.END}" if i == default else " "
        print(f"  {marker} [{i+1}] {choice}")
    while True:
        result = input(f"\nEnter choice (1-{len(choices)}) [{default+1}]: ").strip()
        if not result:
            return default
        try:
            idx = int(result) - 1
            if 0 <= idx < len(choices):
                return idx
        except ValueError:
            pass
        print_error(f"Invalid choice. Please enter 1-{len(choices)}")


def prompt_multi_choice(text: str, choices: List[str]) -> List[int]:
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.YELLOW}(Enter numbers separated by commas, or 'all'){Colors.END}")
    for i, choice in enumerate(choices):
        print(f"  [{i+1}] {choice}")
    while True:
        result = input(f"\nEnter choices: ").strip().lower()
        if result == 'all':
            return list(range(len(choices)))
        if not result:
            return []
        try:
            indices = [int(x.strip()) - 1 for x in result.split(',')]
            if all(0 <= idx < len(choices) for idx in indices):
                return indices
        except ValueError:
            pass
        print_error("Invalid input. Enter numbers separated by commas.")


# ============================================================================
# CloudFormation Generator Class
# ============================================================================
class CloudFormationGenerator:
    def __init__(self):
        self.project_name = "serverless-app"
        self.parameters = {
            "EnvironmentName": {"type": "String", "default": "dev", 
                "allowed_values": ["dev", "staging", "prod"], "description": "Environment name"},
            "ApplicationName": {"type": "String", "default": "serverless-app", 
                "description": "Application name"},
            "LogRetentionDays": {"type": "Number", "default": "14",
                "allowed_values": ["7", "14", "30", "60", "90"], "description": "Log retention days"}
        }
        
        self.has_api_gateway = False
        self.has_authorizer = False
        self.has_glue = False
        self.has_step_functions = False
        self.has_sns = False
        self.has_secrets = False
        self.has_dynamodb = False
        self.has_sqs = False
        
        self.lambda_functions = []
        self.glue_jobs = []
        self.step_functions = []
        self.sns_topics = []
        self.s3_buckets = []
        self.dynamodb_tables = []
        self.sqs_queues = []
        self.outputs = []

    def set_project_name(self, name: str):
        self.project_name = name
        self.parameters["ApplicationName"]["default"] = name

    def add_parameter(self, name: str, param_type: str, default: str = "", 
                     description: str = "", allowed_values: List[str] = None):
        self.parameters[name] = {"type": param_type, "default": default, "description": description}
        if allowed_values:
            self.parameters[name]["allowed_values"] = allowed_values

    def add_lambda_function(self, name: str, handler: str = "app.handler",
                           code_uri: str = "lambda/", timeout: int = 30,
                           memory_size: int = 256, env_vars: Dict = None,
                           api_events: List[Dict] = None):
        self.lambda_functions.append({
            "name": name, "handler": handler, "code_uri": code_uri,
            "timeout": timeout, "memory_size": memory_size,
            "env_vars": env_vars or {}, "api_events": api_events or []
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}FunctionArn",
            "description": f"{name} Lambda ARN",
            "value": f"!GetAtt {self._pascal(name)}Function.Arn"
        })

    def add_api_gateway(self, with_authorizer: bool = True):
        self.has_api_gateway = True
        self.has_authorizer = with_authorizer
        if with_authorizer:
            self.add_parameter("ValidClientIds", "CommaDelimitedList", 
                "client-app-1,client-app-2", "Valid Client IDs for authorization")
        self.outputs.append({
            "name": "ApiEndpoint", "description": "API Gateway endpoint",
            "value": "!Sub https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${EnvironmentName}"
        })

    def add_s3_bucket(self, name: str, suffix: str = "data", versioning: bool = False):
        self.s3_buckets.append({"name": name, "suffix": suffix, "versioning": versioning})
        self.outputs.append({"name": f"{name}Name", "description": f"{name} bucket", "value": f"!Ref {name}"})

    def add_glue_job(self, name: str, script_name: str, description: str = "",
                    worker_type: str = "G.1X", num_workers: int = 2, timeout: int = 60):
        self.has_glue = True
        if not any(b["name"] == "GlueDataBucket" for b in self.s3_buckets):
            self.add_s3_bucket("GlueDataBucket", "glue-data")
        self.glue_jobs.append({
            "name": name, "script_name": script_name, 
            "description": description or f"Glue job: {name}",
            "worker_type": worker_type, "num_workers": num_workers, "timeout": timeout
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}GlueJobName", 
            "description": f"{name} Glue job",
            "value": f"!Ref {self._pascal(name)}GlueJob"
        })

    def add_step_function(self, name: str, glue_jobs: List[str] = None,
                         lambda_functions: List[str] = None, with_sns: bool = True):
        self.has_step_functions = True
        if with_sns and not self.has_sns:
            self.add_sns_topic("JobFailure", "failure", "Job Failure Notifications")
        self.step_functions.append({
            "name": name, "glue_jobs": glue_jobs or [],
            "lambda_functions": lambda_functions or [], "with_sns": with_sns
        })
        self.outputs.append({
            "name": f"{self._pascal(name)}StateMachineArn",
            "description": f"{name} State Machine ARN",
            "value": f"!Ref {self._pascal(name)}StateMachine"
        })

    def add_sns_topic(self, name: str, suffix: str, display_name: str, email_count: int = 3):
        self.has_sns = True
        self.sns_topics.append({
            "name": name, "suffix": suffix, "display_name": display_name, "email_count": email_count
        })
        for i in range(1, email_count + 1):
            if f"NotificationEmail{i}" not in self.parameters:
                self.add_parameter(f"NotificationEmail{i}", "String", "", f"Email {i} for notifications")
        self.outputs.append({"name": f"{name}TopicArn", "description": f"{name} SNS topic", "value": f"!Ref {name}Topic"})

    def add_dynamodb_table(self, name: str, suffix: str, partition_key: str,
                          pk_type: str = "S", sort_key: str = None, sk_type: str = "S"):
        self.has_dynamodb = True
        self.dynamodb_tables.append({
            "name": name, "suffix": suffix, "pk": partition_key, "pk_type": pk_type,
            "sk": sort_key, "sk_type": sk_type
        })
        self.outputs.append({"name": f"{name}TableName", "description": f"{name} table", "value": f"!Ref {name}Table"})

    def add_sqs_queue(self, name: str, suffix: str, with_dlq: bool = True):
        self.has_sqs = True
        self.sqs_queues.append({"name": name, "suffix": suffix, "with_dlq": with_dlq})
        self.outputs.append({"name": f"{name}QueueUrl", "description": f"{name} queue", "value": f"!Ref {name}Queue"})

    def add_secrets_manager(self):
        self.has_secrets = True
        self.outputs.append({"name": "ApplicationSecretArn", "description": "Secret ARN", "value": "!Ref ApplicationSecret"})

    def _pascal(self, name: str) -> str:
        return ''.join(w.capitalize() for w in name.replace('-', '_').split('_'))

    def generate(self, output_path: str) -> str:
        template = self._build_template()
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(template)
        return template

    def _build_template(self) -> str:
        parts = [
            "AWSTemplateFormatVersion: '2010-09-09'",
            "Transform: AWS::Serverless-2016-10-31",
            f"Description: CloudFormation template for {self.project_name}",
            f"# Generated by CFN Generator on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "", self._gen_parameters(), self._gen_conditions(), "Resources:",
            self._gen_s3(), self._gen_secrets(), self._gen_lambda(),
            self._gen_api_gateway(), self._gen_glue(), self._gen_step_functions(),
            self._gen_sns(), self._gen_dynamodb(), self._gen_sqs(), "", self._gen_outputs()
        ]
        template = '\n'.join(p for p in parts if p)
        while '\n\n\n' in template:
            template = template.replace('\n\n\n', '\n\n')
        return template

    def _gen_parameters(self) -> str:
        lines = ["Parameters:"]
        for name, cfg in self.parameters.items():
            lines.append(f"  {name}:")
            lines.append(f"    Type: {cfg['type']}")
            if cfg.get('default'): lines.append(f"    Default: {cfg['default']}")
            if cfg.get('description'): lines.append(f"    Description: {cfg['description']}")
            if cfg.get('allowed_values'):
                lines.append("    AllowedValues:")
                for v in cfg['allowed_values']: lines.append(f"      - {v}")
        return '\n'.join(lines)

    def _gen_conditions(self) -> str:
        if not self.has_sns: return ""
        conds = []
        for t in self.sns_topics:
            for i in range(1, t["email_count"] + 1):
                conds.append(f"  HasNotificationEmail{i}: !Not [!Equals [!Ref NotificationEmail{i}, '']]")
        return "Conditions:\n" + '\n'.join(conds) if conds else ""

    def _gen_s3(self) -> str:
        if not self.s3_buckets: return ""
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
        RestrictPublicBuckets: true""")
        return '\n'.join(out)

    def _gen_secrets(self) -> str:
        if not self.has_secrets: return ""
        return """
  ApplicationSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub ${ApplicationName}-secrets-${EnvironmentName}
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: api_key
        PasswordLength: 32"""

    def _gen_lambda(self) -> str:
        if not self.lambda_functions: return ""
        out = []
        for f in self.lambda_functions:
            pn = self._pascal(f['name'])
            events = ""
            if f['api_events'] and self.has_api_gateway:
                events = "      Events:\n"
                for i, e in enumerate(f['api_events']):
                    events += f"""        Api{i+1}:
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
{events}
  {pn}LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/lambda/${{ApplicationName}}-{f['name']}-${{EnvironmentName}}
      RetentionInDays: !Ref LogRetentionDays""")
        return '\n'.join(out)

    def _gen_api_gateway(self) -> str:
        if not self.has_api_gateway: return ""
        auth = ""
        if self.has_authorizer:
            auth = """
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
      Cors:
        AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
        AllowHeaders: "'Content-Type,Authorization,Client-ID'"
        AllowOrigin: "'*'"
{auth}"""
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
      Environment:
        Variables:
          VALID_CLIENT_IDS: !Join [',', !Ref ValidClientIds]

  AuthorizerLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/lambda/${ApplicationName}-authorizer-${EnvironmentName}
      RetentionInDays: !Ref LogRetentionDays"""
        return out

    def _gen_glue(self) -> str:
        if not self.has_glue: return ""
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
                Action: [s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket]
                Resource:
                  - !Sub arn:aws:s3:::${GlueDataBucket}
                  - !Sub arn:aws:s3:::${GlueDataBucket}/*"""]
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
        '--ENVIRONMENT': !Ref EnvironmentName
        '--GLUE_BUCKET': !Ref GlueDataBucket""")
        return '\n'.join(out)

    def _gen_step_functions(self) -> str:
        if not self.has_step_functions: return ""
        perms = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns"]
        if self.lambda_functions: perms.append("lambda:InvokeFunction")
        if self.has_sns: perms.append("sns:Publish")
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
        - PolicyName: StepFunctionsPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: [{', '.join(perms)}]
                Resource: '*'"""]
        for sf in self.step_functions:
            pn = self._pascal(sf['name'])
            defn = self._build_state_machine(sf)
            out.append(f"""
  {pn}StateMachine:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      StateMachineName: !Sub ${{ApplicationName}}-{sf['name']}-${{EnvironmentName}}
      RoleArn: !GetAtt StepFunctionsRole.Arn
      DefinitionString: !Sub |
{self._indent(defn, 8)}""")
        return '\n'.join(out)

    def _build_state_machine(self, sf: Dict) -> str:
        states, order = {}, []
        for j in sf.get('glue_jobs', []):
            st = f"Run{self._pascal(j)}"
            order.append(st)
            states[st] = {
                "Type": "Task", "Resource": "arn:aws:states:::glue:startJobRun.sync",
                "Parameters": {"JobName": f"${{ApplicationName}}-{j}-${{EnvironmentName}}",
                    "Arguments": {"--INPUT_PATH.$": "$.inputPath", "--OUTPUT_PATH.$": "$.outputPath"}}
            }
        for f in sf.get('lambda_functions', []):
            st = f"Invoke{self._pascal(f)}"
            order.append(st)
            states[st] = {
                "Type": "Task", "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {"FunctionName": f"${{ApplicationName}}-{f}-${{EnvironmentName}}", "Payload.$": "$"}
            }
        order.append("JobSucceeded")
        states["JobSucceeded"] = {"Type": "Pass", "End": True}
        for i, s in enumerate(order[:-1]):
            states[s]["Next"] = order[i+1]
            if sf.get('with_sns') and s.startswith("Run"):
                states[s]["Catch"] = [{"ErrorEquals": ["States.ALL"], "Next": "NotifyFailure"}]
        if sf.get('with_sns'):
            states["NotifyFailure"] = {
                "Type": "Task", "Resource": "arn:aws:states:::sns:publish",
                "Parameters": {"TopicArn": "${JobFailureTopicArn}", "Message": "Job failed"},
                "Next": "JobFailed"
            }
            states["JobFailed"] = {"Type": "Fail", "Error": "JobFailed"}
        return json.dumps({"StartAt": order[0] if order else "JobSucceeded", "States": states}, indent=2)

    def _gen_sns(self) -> str:
        if not self.has_sns: return ""
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
        if not self.has_dynamodb: return ""
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
      SSESpecification:
        SSEEnabled: true""")
        return '\n'.join(out)

    def _gen_sqs(self) -> str:
        if not self.has_sqs: return ""
        out = []
        for q in self.sqs_queues:
            if q['with_dlq']:
                out.append(f"""
  {q['name']}QueueDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{q['suffix']}-dlq-${{EnvironmentName}}""")
            dlq_cfg = f"""
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt {q['name']}QueueDLQ.Arn
        maxReceiveCount: 3""" if q['with_dlq'] else ""
            out.append(f"""
  {q['name']}Queue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{q['suffix']}-${{EnvironmentName}}
      VisibilityTimeout: 30{dlq_cfg}""")
        return '\n'.join(out)

    def _gen_outputs(self) -> str:
        if not self.outputs: return ""
        lines = ["Outputs:"]
        for o in self.outputs:
            lines.extend([f"  {o['name']}:", f"    Description: {o['description']}", 
                         f"    Value: {o['value']}", ""])
        return '\n'.join(lines)

    def _indent(self, text: str, spaces: int) -> str:
        return '\n'.join(' ' * spaces + line for line in text.split('\n'))

    def generate_env_config(self, env: str, path: str):
        cfg = {"Parameters": {}, "Tags": {"Environment": env, "Application": self.project_name}}
        for n, p in self.parameters.items():
            cfg["Parameters"][n] = p.get("default", "")
        cfg["Parameters"]["EnvironmentName"] = env
        if env == "staging": cfg["Parameters"]["LogRetentionDays"] = "30"
        if env == "prod": cfg["Parameters"]["LogRetentionDays"] = "90"
        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2)

    def generate_buildspec(self, path: str):
        bs = f"""version: 0.2
env:
  variables:
    SAM_TEMPLATE: serverless-app-template.yml
    APPLICATION_NAME: {self.project_name}
phases:
  install:
    runtime-versions:
      python: 3.9
    commands:
      - pip install aws-sam-cli
  build:
    commands:
      - sam build --template $SAM_TEMPLATE
      - sam package --output-template-file packaged-template.yaml --s3-bucket $ARTIFACT_BUCKET
artifacts:
  files: [packaged-template.yaml, dev.json, staging.json, prod.json]
  discard-paths: yes
"""
        with open(path, 'w') as f:
            f.write(bs)


# ============================================================================
# Interactive CLI Functions
# ============================================================================
def configure_resources(gen: CloudFormationGenerator):
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
    
    print_section("Select Resources")
    choices = [f"{n} - {d}" for n, d in resources]
    selected = prompt_multi_choice("Available resources:", choices)
    names = [resources[i][0] for i in selected]
    
    lambda_funcs, glue_jobs = [], []
    
    if "API Gateway" in names:
        print_section("API Gateway")
        auth = prompt_yes_no("Include Client-ID authorization?", True)
        gen.add_api_gateway(with_authorizer=auth)
        print_success("API Gateway configured")
    
    if "Lambda Functions" in names:
        print_section("Lambda Functions")
        while True:
            name = prompt("Function name (empty to finish)")
            if not name: break
            handler = prompt("Handler", f"{name}.handler")
            code_uri = prompt("Code URI", f"lambda/{name}/")
            events = []
            if gen.has_api_gateway and prompt_yes_no("Add API endpoints?", True):
                while True:
                    path = prompt("Path (empty to finish)")
                    if not path: break
                    method = prompt("Method", "GET").upper()
                    events.append({"path": path, "method": method})
            gen.add_lambda_function(name, handler, code_uri, api_events=events)
            lambda_funcs.append(name)
            print_success(f"Lambda '{name}' added")
    
    if "S3 Buckets" in names:
        print_section("S3 Buckets")
        while True:
            name = prompt("Bucket name (empty to finish)")
            if not name: break
            suffix = prompt("Suffix", "data")
            gen.add_s3_bucket(name, suffix)
            print_success(f"S3 bucket '{name}' added")
    
    if "Glue Jobs" in names:
        print_section("Glue Jobs")
        while True:
            name = prompt("Job name (empty to finish)")
            if not name: break
            script = prompt("Script filename", f"{name.replace('-','_')}.py")
            wt = ["G.025X", "G.1X", "G.2X"][prompt_choice("Worker type:", 
                ["G.025X (2 vCPU)", "G.1X (4 vCPU)", "G.2X (8 vCPU)"], 1)]
            gen.add_glue_job(name, script, worker_type=wt)
            glue_jobs.append(name)
            print_success(f"Glue job '{name}' added")
    
    if "Step Functions" in names:
        print_section("Step Functions")
        while True:
            name = prompt("State machine name (empty to finish)")
            if not name: break
            sel_glue = [glue_jobs[i] for i in prompt_multi_choice("Glue jobs:", glue_jobs)] if glue_jobs else []
            sel_lambda = [lambda_funcs[i] for i in prompt_multi_choice("Lambda functions:", lambda_funcs)] if lambda_funcs else []
            sns = prompt_yes_no("SNS on failure?", True)
            gen.add_step_function(name, sel_glue, sel_lambda, sns)
            print_success(f"Step Function '{name}' added")
    
    if "SNS Topics" in names:
        print_section("SNS Topics")
        while True:
            name = prompt("Topic name (empty to finish)")
            if not name: break
            suffix = prompt("Suffix", name.lower())
            gen.add_sns_topic(name, suffix, f"{name} Notifications")
            print_success(f"SNS topic '{name}' added")
    
    if "DynamoDB Tables" in names:
        print_section("DynamoDB Tables")
        while True:
            name = prompt("Table name (empty to finish)")
            if not name: break
            pk = prompt("Partition key", "id")
            sk = prompt("Sort key (empty for none)", "")
            gen.add_dynamodb_table(name, name.lower(), pk, sort_key=sk if sk else None)
            print_success(f"DynamoDB table '{name}' added")
    
    if "SQS Queues" in names:
        print_section("SQS Queues")
        while True:
            name = prompt("Queue name (empty to finish)")
            if not name: break
            dlq = prompt_yes_no("Create DLQ?", True)
            gen.add_sqs_queue(name, name.lower(), dlq)
            print_success(f"SQS queue '{name}' added")
    
    if "Secrets Manager" in names:
        gen.add_secrets_manager()
        print_success("Secrets Manager added")


def generate_files(gen: CloudFormationGenerator, output_dir: str):
    print_section("Generating Files")
    os.makedirs(output_dir, exist_ok=True)
    
    gen.generate(os.path.join(output_dir, "serverless-app-template.yml"))
    print_success("serverless-app-template.yml")
    
    for env in ["dev", "staging", "prod"]:
        gen.generate_env_config(env, os.path.join(output_dir, f"{env}.json"))
        print_success(f"{env}.json")
    
    gen.generate_buildspec(os.path.join(output_dir, "buildspec.yml"))
    print_success("buildspec.yml")
    
    # Lambda stubs
    for f in gen.lambda_functions:
        d = os.path.join(output_dir, f["code_uri"].rstrip('/'))
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f["handler"].split('.')[0] + ".py")
        with open(p, 'w') as fp:
            fp.write(f'''import json
import os

def handler(event, context):
    return {{
        "statusCode": 200,
        "body": json.dumps({{"message": "Hello from {f['name']}"}})
    }}
''')
        print_success(p)
    
    if gen.has_authorizer:
        d = os.path.join(output_dir, "lambda/authorizer")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "authorizer.py")
        with open(p, 'w') as fp:
            fp.write('''import os

VALID_CLIENT_IDS = os.environ.get('VALID_CLIENT_IDS', '').split(',')

def handler(event, context):
    headers = event.get('headers', {})
    client_id = headers.get('Client-ID') or headers.get('client-id')
    method_arn = event.get('methodArn', '')
    effect = 'Allow' if client_id in VALID_CLIENT_IDS else 'Deny'
    return {
        'principalId': client_id or 'unknown',
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{'Action': 'execute-api:Invoke', 'Effect': effect, 'Resource': method_arn}]
        }
    }
''')
        print_success(p)


def main():
    parser = argparse.ArgumentParser(description="AWS CloudFormation Template Generator")
    parser.add_argument('--config', '-c', help='Load config from JSON file')
    parser.add_argument('--output', '-o', default='./output', help='Output directory')
    parser.add_argument('--quick', '-q', action='store_true', help='Quick mode with defaults')
    args = parser.parse_args()
    
    try:
        print_header("AWS CloudFormation Template Generator")
        
        gen = CloudFormationGenerator()
        
        if args.quick:
            name = prompt("Project name", "serverless-app")
            gen.set_project_name(name)
            gen.add_api_gateway(True)
            gen.add_lambda_function("api", api_events=[{"path": "/health", "method": "GET"}])
            gen.add_s3_bucket("DataBucket", "data")
            gen.add_glue_job("etl-processor", "etl_processor.py")
            gen.add_step_function("orchestrator", glue_jobs=["etl-processor"])
        else:
            print_section("Project Configuration")
            name = prompt("Project name", "serverless-app")
            gen.set_project_name(name)
            configure_resources(gen)
        
        print_section("Summary")
        print(f"  Project: {Colors.CYAN}{gen.project_name}{Colors.END}")
        print(f"  Lambda: {Colors.CYAN}{len(gen.lambda_functions)}{Colors.END}")
        print(f"  API Gateway: {Colors.CYAN}{'Yes' if gen.has_api_gateway else 'No'}{Colors.END}")
        print(f"  Glue Jobs: {Colors.CYAN}{len(gen.glue_jobs)}{Colors.END}")
        print(f"  Step Functions: {Colors.CYAN}{len(gen.step_functions)}{Colors.END}")
        
        if prompt_yes_no("\nGenerate template?", True):
            generate_files(gen, args.output)
            print_header("Complete!")
            print(f"Files generated in: {Colors.CYAN}{args.output}{Colors.END}")
        
    except KeyboardInterrupt:
        print("\n")
        print_info("Cancelled")


if __name__ == "__main__":
    main()
