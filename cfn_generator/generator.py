"""
CloudFormation Template Generator

This module contains the core logic for generating CloudFormation/SAM templates
based on user-specified resource requirements.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from . import resources


class CloudFormationGenerator:
    """
    Main class for generating CloudFormation templates.
    
    Usage:
        generator = CloudFormationGenerator()
        generator.set_project_name("my-app")
        generator.add_lambda_function("api", handler="app.handler", code_uri="lambda/api/")
        generator.add_api_gateway(with_authorizer=True)
        generator.add_glue_job("etl-processor", script_name="processor.py")
        generator.add_step_function("orchestrator", glue_jobs=["etl-processor"])
        generator.generate("output/template.yml")
    """
    
    def __init__(self):
        self.project_name = "serverless-app"
        self.resources = []
        self.outputs = []
        self.parameters = {}
        self.conditions = []
        
        # Track added components
        self.has_api_gateway = False
        self.has_authorizer = False
        self.has_glue = False
        self.has_step_functions = False
        self.has_sns = False
        self.has_secrets = False
        self.has_dynamodb = False
        self.has_sqs = False
        self.has_eventbridge = False
        
        # Store configurations
        self.lambda_functions = []
        self.glue_jobs = []
        self.step_functions = []
        self.sns_topics = []
        self.s3_buckets = []
        self.dynamodb_tables = []
        self.sqs_queues = []
        self.eventbridge_rules = []
        
        # Default parameters
        self._init_default_parameters()
    
    def _init_default_parameters(self):
        """Initialize default CloudFormation parameters."""
        self.parameters = {
            "EnvironmentName": {
                "type": "String",
                "default": "dev",
                "allowed_values": ["dev", "staging", "prod"],
                "description": "Environment name (dev, staging, prod)"
            },
            "ApplicationName": {
                "type": "String",
                "default": "serverless-app",
                "description": "Application name used for resource naming"
            },
            "LogRetentionDays": {
                "type": "Number",
                "default": "14",
                "allowed_values": ["7", "14", "30", "60", "90"],
                "description": "CloudWatch log retention in days"
            }
        }
    
    def set_project_name(self, name: str):
        """Set the project/application name."""
        self.project_name = name
        self.parameters["ApplicationName"]["default"] = name
    
    def add_parameter(self, name: str, param_type: str, default: str = "", 
                     description: str = "", allowed_values: List[str] = None):
        """Add a custom parameter to the template."""
        self.parameters[name] = {
            "type": param_type,
            "default": default,
            "description": description
        }
        if allowed_values:
            self.parameters[name]["allowed_values"] = allowed_values
    
    def add_lambda_function(self, name: str, handler: str = "app.handler",
                           code_uri: str = "lambda/", timeout: int = 30,
                           memory_size: int = 256, env_vars: Dict = None,
                           api_events: List[Dict] = None, with_role: bool = True,
                           extra_permissions: List[Dict] = None):
        """
        Add a Lambda function to the template.
        
        Args:
            name: Function name suffix (e.g., "api", "processor")
            handler: Handler path (e.g., "app.handler")
            code_uri: Path to Lambda code
            timeout: Function timeout in seconds
            memory_size: Memory allocation in MB
            env_vars: Additional environment variables
            api_events: API Gateway events [{path, method}, ...]
            with_role: Create dedicated IAM role
            extra_permissions: Additional IAM permissions
        """
        func_config = {
            "name": name,
            "handler": handler,
            "code_uri": code_uri,
            "timeout": timeout,
            "memory_size": memory_size,
            "env_vars": env_vars or {},
            "api_events": api_events or [],
            "with_role": with_role,
            "extra_permissions": extra_permissions or []
        }
        self.lambda_functions.append(func_config)
        
        # Add output
        self.outputs.append({
            "name": f"{self._to_pascal_case(name)}FunctionArn",
            "description": f"{name} Lambda function ARN",
            "value": f"!GetAtt {self._to_pascal_case(name)}Function.Arn"
        })
    
    def add_api_gateway(self, with_authorizer: bool = True, cors: bool = True):
        """
        Add API Gateway to the template.
        
        Args:
            with_authorizer: Include Client-ID header authorizer
            cors: Enable CORS
        """
        self.has_api_gateway = True
        self.has_authorizer = with_authorizer
        
        if with_authorizer:
            self.add_parameter(
                "ValidClientIds",
                "CommaDelimitedList",
                "client-app-1,client-app-2",
                "Comma-separated list of valid Client IDs for API authorization"
            )
        
        # Add outputs
        self.outputs.append({
            "name": "ApiEndpoint",
            "description": "API Gateway endpoint URL",
            "value": "!Sub https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/${EnvironmentName}"
        })
    
    def add_s3_bucket(self, name: str, suffix: str = "data", 
                     versioning: bool = False, lifecycle_days: int = None):
        """
        Add an S3 bucket to the template.
        
        Args:
            name: Logical name for the bucket resource
            suffix: Bucket name suffix
            versioning: Enable versioning
            lifecycle_days: Days before transitioning to Glacier (None = no lifecycle)
        """
        bucket_config = {
            "name": name,
            "suffix": suffix,
            "versioning": versioning,
            "lifecycle_days": lifecycle_days
        }
        self.s3_buckets.append(bucket_config)
        
        # Add output
        self.outputs.append({
            "name": f"{name}Name",
            "description": f"{name} S3 bucket name",
            "value": f"!Ref {name}"
        })
    
    def add_glue_job(self, name: str, script_name: str, description: str = "",
                    worker_type: str = "G.1X", num_workers: int = 2,
                    timeout: int = 60, extra_args: Dict = None):
        """
        Add a Glue job to the template.
        
        Args:
            name: Job name suffix
            script_name: Python script filename
            description: Job description
            worker_type: Glue worker type (G.1X, G.2X, G.025X)
            num_workers: Number of workers
            timeout: Job timeout in minutes
            extra_args: Additional job arguments
        """
        self.has_glue = True
        
        # Ensure Glue data bucket exists
        if not any(b["name"] == "GlueDataBucket" for b in self.s3_buckets):
            self.add_s3_bucket("GlueDataBucket", "glue-data")
        
        job_config = {
            "name": name,
            "script_name": script_name,
            "description": description or f"Glue ETL job for {name}",
            "worker_type": worker_type,
            "num_workers": num_workers,
            "timeout": timeout,
            "extra_args": extra_args or {}
        }
        self.glue_jobs.append(job_config)
        
        # Add output
        self.outputs.append({
            "name": f"{self._to_pascal_case(name)}GlueJobName",
            "description": f"{name} Glue job name",
            "value": f"!Ref {self._to_pascal_case(name)}GlueJob"
        })
    
    def add_step_function(self, name: str, glue_jobs: List[str] = None,
                         lambda_functions: List[str] = None,
                         with_sns_notification: bool = True,
                         custom_definition: str = None):
        """
        Add a Step Functions state machine to the template.
        
        Args:
            name: State machine name suffix
            glue_jobs: List of Glue job names to orchestrate
            lambda_functions: List of Lambda function names to invoke
            with_sns_notification: Add SNS notification on failure
            custom_definition: Custom state machine definition (ASL JSON)
        """
        self.has_step_functions = True
        
        if with_sns_notification and not self.has_sns:
            self.add_sns_topic("JobFailure", "failure-notifications", 
                             "Job Failure Notifications")
        
        sf_config = {
            "name": name,
            "glue_jobs": glue_jobs or [],
            "lambda_functions": lambda_functions or [],
            "with_sns_notification": with_sns_notification,
            "custom_definition": custom_definition
        }
        self.step_functions.append(sf_config)
        
        # Add output
        self.outputs.append({
            "name": f"{self._to_pascal_case(name)}StateMachineArn",
            "description": f"{name} Step Functions state machine ARN",
            "value": f"!Ref {self._to_pascal_case(name)}StateMachine"
        })
    
    def add_sns_topic(self, name: str, suffix: str, display_name: str,
                     email_subscriptions: int = 3):
        """
        Add an SNS topic to the template.
        
        Args:
            name: Logical name for the topic
            suffix: Topic name suffix
            display_name: Display name for the topic
            email_subscriptions: Number of email subscription parameters to create
        """
        self.has_sns = True
        
        topic_config = {
            "name": name,
            "suffix": suffix,
            "display_name": display_name,
            "email_count": email_subscriptions
        }
        self.sns_topics.append(topic_config)
        
        # Add email parameters
        for i in range(1, email_subscriptions + 1):
            param_name = f"NotificationEmail{i}"
            if param_name not in self.parameters:
                self.add_parameter(
                    param_name, "String", "",
                    f"Email address {i} for SNS notifications"
                )
        
        # Add output
        self.outputs.append({
            "name": f"{name}TopicArn",
            "description": f"{name} SNS topic ARN",
            "value": f"!Ref {name}Topic"
        })
    
    def add_dynamodb_table(self, name: str, suffix: str,
                          partition_key: str, partition_key_type: str = "S",
                          sort_key: str = None, sort_key_type: str = "S",
                          billing_mode: str = "PAY_PER_REQUEST",
                          gsi: List[Dict] = None):
        """
        Add a DynamoDB table to the template.
        
        Args:
            name: Logical name for the table
            suffix: Table name suffix
            partition_key: Partition key attribute name
            partition_key_type: Partition key type (S, N, B)
            sort_key: Sort key attribute name (optional)
            sort_key_type: Sort key type
            billing_mode: PAY_PER_REQUEST or PROVISIONED
            gsi: Global secondary indexes
        """
        self.has_dynamodb = True
        
        table_config = {
            "name": name,
            "suffix": suffix,
            "partition_key": partition_key,
            "partition_key_type": partition_key_type,
            "sort_key": sort_key,
            "sort_key_type": sort_key_type,
            "billing_mode": billing_mode,
            "gsi": gsi or []
        }
        self.dynamodb_tables.append(table_config)
        
        # Add output
        self.outputs.append({
            "name": f"{name}TableName",
            "description": f"{name} DynamoDB table name",
            "value": f"!Ref {name}Table"
        })
    
    def add_sqs_queue(self, name: str, suffix: str,
                     visibility_timeout: int = 30,
                     retention_period: int = 345600,
                     with_dlq: bool = True):
        """
        Add an SQS queue to the template.
        
        Args:
            name: Logical name for the queue
            suffix: Queue name suffix
            visibility_timeout: Visibility timeout in seconds
            retention_period: Message retention period in seconds
            with_dlq: Create a dead-letter queue
        """
        self.has_sqs = True
        
        queue_config = {
            "name": name,
            "suffix": suffix,
            "visibility_timeout": visibility_timeout,
            "retention_period": retention_period,
            "with_dlq": with_dlq
        }
        self.sqs_queues.append(queue_config)
        
        # Add output
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
    
    def add_eventbridge_rule(self, name: str, suffix: str,
                            schedule: str, target_type: str,
                            target_name: str, description: str = ""):
        """
        Add an EventBridge rule to the template.
        
        Args:
            name: Logical name for the rule
            suffix: Rule name suffix
            schedule: Cron or rate expression
            target_type: "lambda" or "stepfunction"
            target_name: Name of the target resource
            description: Rule description
        """
        self.has_eventbridge = True
        
        rule_config = {
            "name": name,
            "suffix": suffix,
            "schedule": schedule,
            "target_type": target_type,
            "target_name": target_name,
            "description": description or f"EventBridge rule for {name}"
        }
        self.eventbridge_rules.append(rule_config)
    
    def _to_pascal_case(self, name: str) -> str:
        """Convert string to PascalCase."""
        return ''.join(word.capitalize() for word in name.replace('-', '_').split('_'))
    
    def _generate_parameters_section(self) -> str:
        """Generate the Parameters section of the template."""
        lines = ["Parameters:"]
        
        for name, config in self.parameters.items():
            lines.append(f"  {name}:")
            lines.append(f"    Type: {config['type']}")
            if config.get('default'):
                lines.append(f"    Default: {config['default']}")
            if config.get('description'):
                lines.append(f"    Description: {config['description']}")
            if config.get('allowed_values'):
                lines.append("    AllowedValues:")
                for val in config['allowed_values']:
                    lines.append(f"      - {val}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_conditions_section(self) -> str:
        """Generate the Conditions section of the template."""
        conditions = []
        
        # Add conditions for SNS email subscriptions
        if self.has_sns:
            for topic in self.sns_topics:
                for i in range(1, topic["email_count"] + 1):
                    conditions.append(
                        f"  HasNotificationEmail{i}: !Not [!Equals [!Ref NotificationEmail{i}, '']]"
                    )
        
        if conditions:
            return "Conditions:\n" + '\n'.join(conditions) + "\n"
        return ""
    
    def _generate_lambda_resources(self) -> str:
        """Generate Lambda function resources."""
        output = []
        
        for func in self.lambda_functions:
            pascal_name = self._to_pascal_case(func["name"])
            
            # Generate IAM role
            if func["with_role"]:
                role_output = self._generate_lambda_role(func)
                output.append(role_output)
            
            # Generate extra environment variables
            extra_env = ""
            if func["env_vars"]:
                for key, value in func["env_vars"].items():
                    extra_env += f"          {key}: {value}\n"
            
            # Generate API events
            events = ""
            if func["api_events"] and self.has_api_gateway:
                events = "      Events:\n"
                for i, event in enumerate(func["api_events"]):
                    events += f"        Api{i+1}:\n"
                    events += "          Type: Api\n"
                    events += "          Properties:\n"
                    events += "            RestApiId: !Ref ApiGateway\n"
                    events += f"            Path: {event['path']}\n"
                    events += f"            Method: {event['method']}\n"
            
            # Generate function
            func_template = resources.LAMBDA_FUNCTION.format(
                function_name=f"{pascal_name}Function",
                function_suffix=func["name"],
                handler=func["handler"],
                code_uri=func["code_uri"],
                role_name=f"{pascal_name}Role" if func["with_role"] else "LambdaExecutionRole",
                timeout=func["timeout"],
                memory_size=func["memory_size"],
                extra_env_vars=extra_env,
                events=events
            )
            output.append(func_template)
            
            # Generate log group
            log_group = resources.LAMBDA_LOG_GROUP.format(
                function_name=pascal_name,
                function_suffix=func["name"]
            )
            output.append(log_group)
        
        return '\n'.join(output)
    
    def _generate_lambda_role(self, func: Dict) -> str:
        """Generate IAM role for Lambda function."""
        pascal_name = self._to_pascal_case(func["name"])
        
        # Build policy statements
        statements = []
        
        # Add S3 permissions if Glue bucket exists
        if self.has_glue:
            statements.append("""              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:ListBucket
                Resource:
                  - !Sub arn:aws:s3:::${GlueDataBucket}
                  - !Sub arn:aws:s3:::${GlueDataBucket}/*""")
        
        # Add Step Functions permissions
        if self.has_step_functions:
            statements.append("""              - Effect: Allow
                Action:
                  - states:StartExecution
                  - states:DescribeExecution
                Resource: '*'""")
        
        # Add Secrets Manager permissions
        if self.has_secrets:
            statements.append("""              - Effect: Allow
                Action:
                  - secretsmanager:GetSecretValue
                Resource: !Ref ApplicationSecret""")
        
        # Add DynamoDB permissions
        if self.has_dynamodb:
            statements.append("""              - Effect: Allow
                Action:
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                  - dynamodb:DeleteItem
                  - dynamodb:Query
                  - dynamodb:Scan
                Resource: '*'""")
        
        # Add SQS permissions
        if self.has_sqs:
            statements.append("""              - Effect: Allow
                Action:
                  - sqs:SendMessage
                  - sqs:ReceiveMessage
                  - sqs:DeleteMessage
                  - sqs:GetQueueAttributes
                Resource: '*'""")
        
        # Add extra permissions
        for perm in func.get("extra_permissions", []):
            stmt = f"""              - Effect: {perm.get('effect', 'Allow')}
                Action:
{self._format_list(perm['actions'], 18)}
                Resource: {perm['resource']}"""
            statements.append(stmt)
        
        policy_statements = '\n'.join(statements) if statements else "              - Effect: Allow\n                Action: logs:*\n                Resource: '*'"
        
        return resources.IAM_LAMBDA_ROLE.format(
            role_name=f"{pascal_name}Role",
            role_suffix=f"{func['name']}-lambda",
            policy_name=f"{pascal_name}Policy",
            policy_statements=policy_statements
        )
    
    def _generate_api_gateway_resources(self) -> str:
        """Generate API Gateway resources."""
        if not self.has_api_gateway:
            return ""
        
        auth_config = resources.API_GATEWAY_AUTH if self.has_authorizer else ""
        
        output = resources.API_GATEWAY.format(auth_config=auth_config)
        
        if self.has_authorizer:
            output += resources.AUTHORIZER_FUNCTION
        
        return output
    
    def _generate_s3_resources(self) -> str:
        """Generate S3 bucket resources."""
        output = []
        
        for bucket in self.s3_buckets:
            lifecycle = ""
            if bucket.get("lifecycle_days"):
                lifecycle = f"""      LifecycleConfiguration:
        Rules:
          - Id: TransitionToGlacier
            Status: Enabled
            Transitions:
              - StorageClass: GLACIER
                TransitionInDays: {bucket['lifecycle_days']}"""
            
            bucket_template = resources.S3_BUCKET.format(
                bucket_name=bucket["name"],
                bucket_suffix=bucket["suffix"],
                versioning="Enabled" if bucket["versioning"] else "Suspended",
                lifecycle_rules=lifecycle
            )
            output.append(bucket_template)
        
        return '\n'.join(output)
    
    def _generate_glue_resources(self) -> str:
        """Generate Glue job resources."""
        if not self.has_glue:
            return ""
        
        output = [resources.IAM_GLUE_ROLE]
        
        # Generate script uploader
        scripts_dict = {}
        for job in self.glue_jobs:
            scripts_dict[job["script_name"]] = self._generate_glue_script_content(job)
        
        uploader = resources.GLUE_SCRIPT_UPLOADER.format(
            glue_scripts=json.dumps(scripts_dict).replace('"', "'")
        )
        output.append(uploader)
        
        # Generate Glue jobs
        for job in self.glue_jobs:
            pascal_name = self._to_pascal_case(job["name"])
            
            extra_args = ""
            if job["extra_args"]:
                for key, value in job["extra_args"].items():
                    extra_args += f"        '--{key}': {value}\n"
            
            job_template = resources.GLUE_JOB.format(
                job_name=f"{pascal_name}GlueJob",
                job_suffix=job["name"],
                description=job["description"],
                worker_type=job["worker_type"],
                num_workers=job["num_workers"],
                timeout=job["timeout"],
                script_name=job["script_name"],
                extra_args=extra_args
            )
            output.append(job_template)
        
        return '\n'.join(output)
    
    def _generate_glue_script_content(self, job: Dict) -> str:
        """Generate a basic Glue script template."""
        return f'''import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, [
    "JOB_NAME", "INPUT_PATH", "OUTPUT_PATH",
    "ENVIRONMENT", "APPLICATION_NAME", "AWS_REGION_NAME", "GLUE_BUCKET"
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# TODO: Add your ETL logic here
# Example:
# input_df = spark.read.csv(args["INPUT_PATH"], header=True)
# output_df = input_df.transform(...)
# output_df.write.parquet(args["OUTPUT_PATH"])

job.commit()
'''
    
    def _generate_step_functions_resources(self) -> str:
        """Generate Step Functions resources."""
        if not self.has_step_functions:
            return ""
        
        output = []
        
        # Generate Step Functions role
        permissions = []
        
        if self.has_glue:
            permissions.append("""              - Effect: Allow
                Action:
                  - glue:StartJobRun
                  - glue:GetJobRun
                  - glue:GetJobRuns
                  - glue:BatchStopJobRun
                Resource: '*'""")
        
        if self.lambda_functions:
            permissions.append("""              - Effect: Allow
                Action:
                  - lambda:InvokeFunction
                Resource: '*'""")
        
        if self.has_sns:
            permissions.append("""              - Effect: Allow
                Action:
                  - sns:Publish
                Resource: !Sub arn:aws:sns:${AWS::Region}:${AWS::AccountId}:${ApplicationName}-*""")
        
        permissions.append("""              - Effect: Allow
                Action:
                  - logs:CreateLogDelivery
                  - logs:GetLogDelivery
                  - logs:UpdateLogDelivery
                  - logs:DeleteLogDelivery
                  - logs:ListLogDeliveries
                  - logs:PutResourcePolicy
                  - logs:DescribeResourcePolicies
                  - logs:DescribeLogGroups
                Resource: '*'""")
        
        role = resources.IAM_STEPFUNCTIONS_ROLE.format(
            stepfn_permissions='\n'.join(permissions)
        )
        output.append(role)
        
        # Generate state machines
        for sf in self.step_functions:
            pascal_name = self._to_pascal_case(sf["name"])
            
            if sf["custom_definition"]:
                definition = sf["custom_definition"]
            else:
                definition = self._generate_state_machine_definition(sf)
            
            # Indent definition properly
            definition_lines = definition.split('\n')
            indented_definition = '\n'.join('        ' + line for line in definition_lines)
            
            sm_template = resources.STEP_FUNCTION.format(
                state_machine_name=f"{pascal_name}StateMachine",
                state_machine_suffix=sf["name"],
                definition=indented_definition
            )
            output.append(sm_template)
            
            # Add log group
            log_group = resources.STEP_FUNCTION_LOG_GROUP.format(
                state_machine_suffix=sf["name"]
            )
            output.append(log_group)
        
        return '\n'.join(output)
    
    def _generate_state_machine_definition(self, sf: Dict) -> str:
        """Generate a state machine definition based on configured jobs/functions."""
        states = {}
        state_order = []
        
        # Add Glue job states
        for job_name in sf.get("glue_jobs", []):
            pascal_name = self._to_pascal_case(job_name)
            state_name = f"Run{pascal_name}"
            state_order.append(state_name)
            states[state_name] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::glue:startJobRun.sync",
                "Parameters": {
                    "JobName.$": f"States.Format('${{ApplicationName}}-{job_name}-${{EnvironmentName}}')",
                    "Arguments": {
                        "--INPUT_PATH.$": "$.inputPath",
                        "--OUTPUT_PATH.$": "$.outputPath"
                    }
                }
            }
        
        # Add Lambda invocation states
        for func_name in sf.get("lambda_functions", []):
            pascal_name = self._to_pascal_case(func_name)
            state_name = f"Invoke{pascal_name}"
            state_order.append(state_name)
            states[state_name] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName.$": f"States.Format('${{ApplicationName}}-{func_name}-${{EnvironmentName}}')",
                    "Payload.$": "$"
                },
                "ResultPath": f"$.{func_name}Result"
            }
        
        # Add success state
        state_order.append("JobSucceeded")
        states["JobSucceeded"] = {
            "Type": "Pass",
            "End": True
        }
        
        # Link states together
        for i, state_name in enumerate(state_order[:-1]):
            states[state_name]["Next"] = state_order[i + 1]
            
            # Add error handling with SNS notification
            if sf.get("with_sns_notification") and state_name.startswith("Run"):
                states[state_name]["Catch"] = [{
                    "ErrorEquals": ["States.ALL"],
                    "ResultPath": "$.error",
                    "Next": "NotifyFailure"
                }]
        
        # Add failure notification state
        if sf.get("with_sns_notification"):
            states["NotifyFailure"] = {
                "Type": "Task",
                "Resource": "arn:aws:states:::sns:publish",
                "Parameters": {
                    "TopicArn": "${JobFailureTopicArn}",
                    "Subject": "Step Function Execution Failed",
                    "Message.$": "States.Format('Execution failed: {}', $.error)"
                },
                "Next": "JobFailed"
            }
            states["JobFailed"] = {
                "Type": "Fail",
                "Error": "JobExecutionFailed",
                "Cause": "One or more jobs failed during execution"
            }
        
        definition = {
            "Comment": f"State machine for {sf['name']}",
            "StartAt": state_order[0] if state_order else "JobSucceeded",
            "States": states
        }
        
        return json.dumps(definition, indent=2)
    
    def _generate_sns_resources(self) -> str:
        """Generate SNS topic resources."""
        if not self.has_sns:
            return ""
        
        output = []
        
        for topic in self.sns_topics:
            topic_template = resources.SNS_TOPIC.format(
                topic_name=f"{topic['name']}Topic",
                topic_suffix=topic["suffix"],
                display_name=topic["display_name"]
            )
            output.append(topic_template)
            
            # Add subscriptions
            for i in range(1, topic["email_count"] + 1):
                sub = resources.SNS_SUBSCRIPTION.format(
                    subscription_name=f"{topic['name']}Subscription{i}",
                    condition_name=f"NotificationEmail{i}",
                    topic_ref=f"{topic['name']}Topic",
                    email_param=f"NotificationEmail{i}"
                )
                output.append(sub)
        
        return '\n'.join(output)
    
    def _generate_dynamodb_resources(self) -> str:
        """Generate DynamoDB table resources."""
        if not self.has_dynamodb:
            return ""
        
        output = []
        
        for table in self.dynamodb_tables:
            # Build attribute definitions
            attrs = [f"        - AttributeName: {table['partition_key']}\n          AttributeType: {table['partition_key_type']}"]
            if table["sort_key"]:
                attrs.append(f"        - AttributeName: {table['sort_key']}\n          AttributeType: {table['sort_key_type']}")
            
            # Build key schema
            keys = [f"        - AttributeName: {table['partition_key']}\n          KeyType: HASH"]
            if table["sort_key"]:
                keys.append(f"        - AttributeName: {table['sort_key']}\n          KeyType: RANGE")
            
            # Build GSI config
            gsi_config = ""
            if table["gsi"]:
                gsi_config = "      GlobalSecondaryIndexes:\n"
                for gsi in table["gsi"]:
                    gsi_config += f"        - IndexName: {gsi['name']}\n"
                    gsi_config += "          KeySchema:\n"
                    gsi_config += f"            - AttributeName: {gsi['partition_key']}\n              KeyType: HASH\n"
                    if gsi.get("sort_key"):
                        gsi_config += f"            - AttributeName: {gsi['sort_key']}\n              KeyType: RANGE\n"
                    gsi_config += "          Projection:\n            ProjectionType: ALL\n"
            
            table_template = resources.DYNAMODB_TABLE.format(
                table_name=f"{table['name']}Table",
                table_suffix=table["suffix"],
                billing_mode=table["billing_mode"],
                attribute_definitions='\n'.join(attrs),
                key_schema='\n'.join(keys),
                gsi_config=gsi_config
            )
            output.append(table_template)
        
        return '\n'.join(output)
    
    def _generate_sqs_resources(self) -> str:
        """Generate SQS queue resources."""
        if not self.has_sqs:
            return ""
        
        output = []
        
        for queue in self.sqs_queues:
            # Generate DLQ first if needed
            if queue["with_dlq"]:
                dlq = resources.SQS_DLQ.format(
                    queue_name=f"{queue['name']}Queue",
                    queue_suffix=queue["suffix"]
                )
                output.append(dlq)
                
                dlq_config = f"""      RedrivePolicy:
        deadLetterTargetArn: !GetAtt {queue['name']}QueueDLQ.Arn
        maxReceiveCount: 3"""
            else:
                dlq_config = ""
            
            queue_template = resources.SQS_QUEUE.format(
                queue_name=f"{queue['name']}Queue",
                queue_suffix=queue["suffix"],
                visibility_timeout=queue["visibility_timeout"],
                retention_period=queue["retention_period"],
                wait_time=20,
                dlq_config=dlq_config
            )
            output.append(queue_template)
        
        return '\n'.join(output)
    
    def _generate_secrets_resources(self) -> str:
        """Generate Secrets Manager resources."""
        if not self.has_secrets:
            return ""
        return resources.SECRETS_MANAGER
    
    def _generate_outputs_section(self) -> str:
        """Generate the Outputs section of the template."""
        if not self.outputs:
            return ""
        
        lines = ["Outputs:"]
        
        for output in self.outputs:
            lines.append(f"  {output['name']}:")
            lines.append(f"    Description: {output['description']}")
            lines.append(f"    Value: {output['value']}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_list(self, items: List[str], indent: int) -> str:
        """Format a list with proper indentation."""
        return '\n'.join(f"{' ' * indent}- {item}" for item in items)
    
    def generate(self, output_path: str = "template.yml") -> str:
        """
        Generate the complete CloudFormation template.
        
        Args:
            output_path: Path to save the generated template
            
        Returns:
            The generated template as a string
        """
        template_parts = [
            "AWSTemplateFormatVersion: '2010-09-09'",
            "Transform: AWS::Serverless-2016-10-31",
            f"Description: CloudFormation template for {self.project_name}",
            "",
            f"# Generated by CFN Generator v1.0.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            self._generate_parameters_section(),
            self._generate_conditions_section(),
            "Resources:",
            self._generate_s3_resources(),
            self._generate_secrets_resources(),
            self._generate_lambda_resources(),
            self._generate_api_gateway_resources(),
            self._generate_glue_resources(),
            self._generate_step_functions_resources(),
            self._generate_sns_resources(),
            self._generate_dynamodb_resources(),
            self._generate_sqs_resources(),
            "",
            self._generate_outputs_section()
        ]
        
        # Filter out empty parts and join
        template = '\n'.join(part for part in template_parts if part)
        
        # Clean up multiple blank lines
        while '\n\n\n' in template:
            template = template.replace('\n\n\n', '\n\n')
        
        # Save to file
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(template)
        
        return template
    
    def generate_env_config(self, env_name: str, output_path: str = None) -> Dict:
        """
        Generate environment configuration file (e.g., dev.json).
        
        Args:
            env_name: Environment name (dev, staging, prod)
            output_path: Path to save the config file
            
        Returns:
            Configuration dictionary
        """
        config = {
            "Parameters": {},
            "Tags": {
                "Environment": env_name,
                "Application": self.project_name,
                "ManagedBy": "CloudFormation"
            }
        }
        
        for name, param in self.parameters.items():
            if env_name == "dev":
                config["Parameters"][name] = param.get("default", "")
            elif env_name == "staging":
                if name == "LogRetentionDays":
                    config["Parameters"][name] = "30"
                else:
                    config["Parameters"][name] = param.get("default", "")
            elif env_name == "prod":
                if name == "LogRetentionDays":
                    config["Parameters"][name] = "90"
                else:
                    config["Parameters"][name] = param.get("default", "")
        
        config["Parameters"]["EnvironmentName"] = env_name
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(config, f, indent=2)
        
        return config
    
    def generate_buildspec(self, output_path: str = "buildspec.yml") -> str:
        """
        Generate buildspec.yml for CodeBuild.
        
        Args:
            output_path: Path to save the buildspec file
            
        Returns:
            Buildspec content as string
        """
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
        
        with open(output_path, 'w') as f:
            f.write(buildspec)
        
        return buildspec
    
    def to_dict(self) -> Dict:
        """Export configuration as dictionary for saving/loading."""
        return {
            "project_name": self.project_name,
            "parameters": self.parameters,
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
    
    @classmethod
    def from_dict(cls, config: Dict) -> 'CloudFormationGenerator':
        """Create generator from configuration dictionary."""
        gen = cls()
        gen.project_name = config.get("project_name", "serverless-app")
        gen.parameters = config.get("parameters", {})
        gen.lambda_functions = config.get("lambda_functions", [])
        gen.glue_jobs = config.get("glue_jobs", [])
        gen.step_functions = config.get("step_functions", [])
        gen.sns_topics = config.get("sns_topics", [])
        gen.s3_buckets = config.get("s3_buckets", [])
        gen.dynamodb_tables = config.get("dynamodb_tables", [])
        gen.sqs_queues = config.get("sqs_queues", [])
        gen.has_api_gateway = config.get("has_api_gateway", False)
        gen.has_authorizer = config.get("has_authorizer", False)
        gen.has_secrets = config.get("has_secrets", False)
        gen.has_glue = len(gen.glue_jobs) > 0
        gen.has_step_functions = len(gen.step_functions) > 0
        gen.has_sns = len(gen.sns_topics) > 0
        gen.has_dynamodb = len(gen.dynamodb_tables) > 0
        gen.has_sqs = len(gen.sqs_queues) > 0
        return gen
    
    @classmethod
    def from_json(cls, json_path: str) -> 'CloudFormationGenerator':
        """Load generator configuration from JSON file."""
        with open(json_path, 'r') as f:
            config = json.load(f)
        return cls.from_dict(config)
    
    def to_json(self, json_path: str):
        """Save generator configuration to JSON file."""
        with open(json_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
