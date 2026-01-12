#!/usr/bin/env python3
"""
Command-line interface for CloudFormation template generation.

This module provides an interactive CLI that guides developers through
creating customized CloudFormation templates based on their requirements.
"""

import argparse
import json
import os
import sys
from typing import List, Dict, Optional, Tuple

from .generator import CloudFormationGenerator


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}>>> {text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*50}{Colors.END}")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.YELLOW}ℹ {text}{Colors.END}")


def prompt(text: str, default: str = None) -> str:
    """Prompt user for input with optional default value."""
    if default:
        result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default}{Colors.END}]: ").strip()
        return result if result else default
    return input(f"{Colors.BOLD}{text}{Colors.END}: ").strip()


def prompt_yes_no(text: str, default: bool = True) -> bool:
    """Prompt user for yes/no input."""
    default_str = "Y/n" if default else "y/N"
    result = input(f"{Colors.BOLD}{text}{Colors.END} [{Colors.CYAN}{default_str}{Colors.END}]: ").strip().lower()
    if not result:
        return default
    return result in ('y', 'yes', 'true', '1')


def prompt_choice(text: str, choices: List[str], default: int = 0) -> int:
    """Prompt user to choose from a list of options."""
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
        print_error(f"Invalid choice. Please enter a number between 1 and {len(choices)}")


def prompt_multi_choice(text: str, choices: List[str]) -> List[int]:
    """Prompt user to select multiple options."""
    print(f"\n{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.YELLOW}(Enter numbers separated by commas, or 'all' for all options){Colors.END}")
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
        print_error("Invalid input. Please enter numbers separated by commas.")


def display_resource_menu() -> List[str]:
    """Display the main resource selection menu."""
    resources = [
        ("API Gateway", "REST API with optional Client-ID authorization"),
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
    print("Select the AWS resources you need in your template:\n")
    
    choices = [f"{name} - {desc}" for name, desc in resources]
    selected = prompt_multi_choice("Available resources:", choices)
    
    resource_names = [resources[i][0] for i in selected]
    return resource_names


def configure_project(gen: CloudFormationGenerator):
    """Configure basic project settings."""
    print_section("Project Configuration")
    
    project_name = prompt("Enter project/application name", "serverless-app")
    gen.set_project_name(project_name)
    
    print_success(f"Project name set to: {project_name}")


def configure_api_gateway(gen: CloudFormationGenerator):
    """Configure API Gateway settings."""
    print_section("API Gateway Configuration")
    
    with_auth = prompt_yes_no("Include Client-ID header authorization?", True)
    gen.add_api_gateway(with_authorizer=with_auth)
    
    if with_auth:
        client_ids = prompt("Enter default Client IDs (comma-separated)", "client-app-1,client-app-2")
        gen.parameters["ValidClientIds"]["default"] = client_ids
    
    print_success("API Gateway configured")


def configure_lambda_functions(gen: CloudFormationGenerator) -> List[str]:
    """Configure Lambda function settings."""
    print_section("Lambda Functions Configuration")
    
    functions = []
    
    while True:
        print(f"\n{Colors.BOLD}Lambda Function #{len(functions) + 1}{Colors.END}")
        
        name = prompt("Function name (e.g., 'api', 'processor')")
        if not name:
            if functions:
                break
            print_error("At least one function name is required")
            continue
        
        handler = prompt("Handler path", f"{name}.handler")
        code_uri = prompt("Code URI (directory path)", f"lambda/{name}/")
        timeout = int(prompt("Timeout (seconds)", "30"))
        memory = int(prompt("Memory size (MB)", "256"))
        
        # API events
        api_events = []
        if gen.has_api_gateway:
            if prompt_yes_no("Add API Gateway endpoints?", True):
                while True:
                    path = prompt("Endpoint path (e.g., '/users', or empty to finish)")
                    if not path:
                        break
                    method = prompt("HTTP method", "GET").upper()
                    api_events.append({"path": path, "method": method})
        
        gen.add_lambda_function(
            name=name,
            handler=handler,
            code_uri=code_uri,
            timeout=timeout,
            memory_size=memory,
            api_events=api_events
        )
        functions.append(name)
        print_success(f"Lambda function '{name}' configured")
        
        if not prompt_yes_no("Add another Lambda function?", False):
            break
    
    return functions


def configure_s3_buckets(gen: CloudFormationGenerator):
    """Configure S3 bucket settings."""
    print_section("S3 Bucket Configuration")
    
    while True:
        print(f"\n{Colors.BOLD}S3 Bucket #{len(gen.s3_buckets) + 1}{Colors.END}")
        
        name = prompt("Bucket logical name (e.g., 'DataBucket')")
        if not name:
            if gen.s3_buckets:
                break
            print_error("At least one bucket name is required")
            continue
        
        suffix = prompt("Bucket name suffix", "data")
        versioning = prompt_yes_no("Enable versioning?", False)
        
        lifecycle = None
        if prompt_yes_no("Add lifecycle rule for Glacier transition?", False):
            lifecycle = int(prompt("Days before transition to Glacier", "90"))
        
        gen.add_s3_bucket(name, suffix, versioning, lifecycle)
        print_success(f"S3 bucket '{name}' configured")
        
        if not prompt_yes_no("Add another S3 bucket?", False):
            break


def configure_glue_jobs(gen: CloudFormationGenerator) -> List[str]:
    """Configure Glue job settings."""
    print_section("Glue Jobs Configuration")
    
    jobs = []
    
    while True:
        print(f"\n{Colors.BOLD}Glue Job #{len(jobs) + 1}{Colors.END}")
        
        name = prompt("Job name (e.g., 'csv-processor')")
        if not name:
            if jobs:
                break
            print_error("At least one job name is required")
            continue
        
        script_name = prompt("Script filename", f"{name.replace('-', '_')}.py")
        description = prompt("Job description", f"Glue ETL job for {name}")
        
        worker_choices = ["G.025X (2 vCPU, 4GB)", "G.1X (4 vCPU, 16GB)", "G.2X (8 vCPU, 32GB)"]
        worker_idx = prompt_choice("Worker type:", worker_choices, 1)
        worker_types = ["G.025X", "G.1X", "G.2X"]
        worker_type = worker_types[worker_idx]
        
        num_workers = int(prompt("Number of workers", "2"))
        timeout = int(prompt("Timeout (minutes)", "60"))
        
        gen.add_glue_job(
            name=name,
            script_name=script_name,
            description=description,
            worker_type=worker_type,
            num_workers=num_workers,
            timeout=timeout
        )
        jobs.append(name)
        print_success(f"Glue job '{name}' configured")
        
        if not prompt_yes_no("Add another Glue job?", False):
            break
    
    return jobs


def configure_step_functions(gen: CloudFormationGenerator, glue_jobs: List[str], 
                            lambda_functions: List[str]):
    """Configure Step Functions settings."""
    print_section("Step Functions Configuration")
    
    while True:
        print(f"\n{Colors.BOLD}State Machine #{len(gen.step_functions) + 1}{Colors.END}")
        
        name = prompt("State machine name (e.g., 'orchestrator')")
        if not name:
            if gen.step_functions:
                break
            print_error("At least one state machine name is required")
            continue
        
        # Select Glue jobs to orchestrate
        selected_glue = []
        if glue_jobs:
            print("\nSelect Glue jobs to include in this state machine:")
            indices = prompt_multi_choice("Available Glue jobs:", glue_jobs)
            selected_glue = [glue_jobs[i] for i in indices]
        
        # Select Lambda functions to invoke
        selected_lambda = []
        if lambda_functions:
            print("\nSelect Lambda functions to include in this state machine:")
            indices = prompt_multi_choice("Available Lambda functions:", lambda_functions)
            selected_lambda = [lambda_functions[i] for i in indices]
        
        with_sns = prompt_yes_no("Send SNS notification on failure?", True)
        
        gen.add_step_function(
            name=name,
            glue_jobs=selected_glue,
            lambda_functions=selected_lambda,
            with_sns_notification=with_sns
        )
        print_success(f"Step Function '{name}' configured")
        
        if not prompt_yes_no("Add another Step Function?", False):
            break


def configure_sns_topics(gen: CloudFormationGenerator):
    """Configure SNS topic settings."""
    print_section("SNS Topics Configuration")
    
    while True:
        print(f"\n{Colors.BOLD}SNS Topic #{len(gen.sns_topics) + 1}{Colors.END}")
        
        name = prompt("Topic logical name (e.g., 'Alerts')")
        if not name:
            if gen.sns_topics:
                break
            print_error("At least one topic name is required")
            continue
        
        suffix = prompt("Topic name suffix", name.lower())
        display_name = prompt("Display name", f"{name} Notifications")
        email_count = int(prompt("Number of email subscription parameters", "3"))
        
        gen.add_sns_topic(name, suffix, display_name, email_count)
        print_success(f"SNS topic '{name}' configured")
        
        if not prompt_yes_no("Add another SNS topic?", False):
            break


def configure_dynamodb_tables(gen: CloudFormationGenerator):
    """Configure DynamoDB table settings."""
    print_section("DynamoDB Tables Configuration")
    
    while True:
        print(f"\n{Colors.BOLD}DynamoDB Table #{len(gen.dynamodb_tables) + 1}{Colors.END}")
        
        name = prompt("Table logical name (e.g., 'Users')")
        if not name:
            if gen.dynamodb_tables:
                break
            print_error("At least one table name is required")
            continue
        
        suffix = prompt("Table name suffix", name.lower())
        pk = prompt("Partition key name", "id")
        pk_type = prompt("Partition key type (S/N/B)", "S").upper()
        
        sk = None
        sk_type = "S"
        if prompt_yes_no("Add sort key?", False):
            sk = prompt("Sort key name")
            sk_type = prompt("Sort key type (S/N/B)", "S").upper()
        
        billing_choices = ["PAY_PER_REQUEST (On-demand)", "PROVISIONED"]
        billing_idx = prompt_choice("Billing mode:", billing_choices, 0)
        billing = "PAY_PER_REQUEST" if billing_idx == 0 else "PROVISIONED"
        
        gen.add_dynamodb_table(name, suffix, pk, pk_type, sk, sk_type, billing)
        print_success(f"DynamoDB table '{name}' configured")
        
        if not prompt_yes_no("Add another DynamoDB table?", False):
            break


def configure_sqs_queues(gen: CloudFormationGenerator):
    """Configure SQS queue settings."""
    print_section("SQS Queues Configuration")
    
    while True:
        print(f"\n{Colors.BOLD}SQS Queue #{len(gen.sqs_queues) + 1}{Colors.END}")
        
        name = prompt("Queue logical name (e.g., 'Tasks')")
        if not name:
            if gen.sqs_queues:
                break
            print_error("At least one queue name is required")
            continue
        
        suffix = prompt("Queue name suffix", name.lower())
        visibility = int(prompt("Visibility timeout (seconds)", "30"))
        retention = int(prompt("Message retention (seconds)", "345600"))
        with_dlq = prompt_yes_no("Create dead-letter queue?", True)
        
        gen.add_sqs_queue(name, suffix, visibility, retention, with_dlq)
        print_success(f"SQS queue '{name}' configured")
        
        if not prompt_yes_no("Add another SQS queue?", False):
            break


def generate_output_files(gen: CloudFormationGenerator, output_dir: str):
    """Generate all output files."""
    print_section("Generating Files")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate main template
    template_path = os.path.join(output_dir, "serverless-app-template.yml")
    gen.generate(template_path)
    print_success(f"Generated: {template_path}")
    
    # Generate environment configs
    for env in ["dev", "staging", "prod"]:
        config_path = os.path.join(output_dir, f"{env}.json")
        gen.generate_env_config(env, config_path)
        print_success(f"Generated: {config_path}")
    
    # Generate buildspec
    buildspec_path = os.path.join(output_dir, "buildspec.yml")
    gen.generate_buildspec(buildspec_path)
    print_success(f"Generated: {buildspec_path}")
    
    # Save configuration
    config_path = os.path.join(output_dir, "generator-config.json")
    gen.to_json(config_path)
    print_success(f"Generated: {config_path}")
    
    # Generate Lambda function stubs
    for func in gen.lambda_functions:
        func_dir = os.path.join(output_dir, func["code_uri"].rstrip('/'))
        os.makedirs(func_dir, exist_ok=True)
        
        handler_file = func["handler"].split('.')[0] + ".py"
        handler_path = os.path.join(func_dir, handler_file)
        
        if not os.path.exists(handler_path):
            with open(handler_path, 'w') as f:
                f.write(generate_lambda_stub(func["name"]))
            print_success(f"Generated: {handler_path}")
    
    # Generate authorizer stub if needed
    if gen.has_authorizer:
        auth_dir = os.path.join(output_dir, "lambda", "authorizer")
        os.makedirs(auth_dir, exist_ok=True)
        auth_path = os.path.join(auth_dir, "authorizer.py")
        
        if not os.path.exists(auth_path):
            with open(auth_path, 'w') as f:
                f.write(generate_authorizer_stub())
            print_success(f"Generated: {auth_path}")


def generate_lambda_stub(name: str) -> str:
    """Generate a Lambda function stub."""
    return f'''"""
Lambda function: {name}
"""
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
APPLICATION_NAME = os.environ.get('APPLICATION_NAME', 'serverless-app')


def handler(event, context):
    """
    Main Lambda handler function.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        API Gateway response object
    """
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
            'headers': {{
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }},
            'body': json.dumps({{
                'error': str(e)
            }})
        }}
'''


def generate_authorizer_stub() -> str:
    """Generate an authorizer function stub."""
    return '''"""
API Gateway Client-ID Header Authorizer
"""
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get valid client IDs from environment
VALID_CLIENT_IDS = os.environ.get('VALID_CLIENT_IDS', '').split(',')


def handler(event, context):
    """
    Authorizer handler that validates Client-ID header.
    
    Args:
        event: Authorizer event containing headers and methodArn
        context: Lambda context
        
    Returns:
        IAM policy document allowing or denying access
    """
    logger.info(f"Authorizer event: {event}")
    
    # Extract Client-ID from headers (case-insensitive)
    headers = event.get('headers', {})
    client_id = headers.get('Client-ID') or headers.get('client-id') or headers.get('CLIENT-ID')
    
    method_arn = event.get('methodArn', '')
    
    # Extract base ARN for caching across all methods
    arn_parts = method_arn.split('/')
    base_arn = '/'.join(arn_parts[:2]) if len(arn_parts) >= 2 else method_arn
    resource_arn = f"{base_arn}/*"
    
    if client_id and client_id.strip() in [cid.strip() for cid in VALID_CLIENT_IDS]:
        logger.info(f"Authorized client: {client_id}")
        return generate_policy(client_id, 'Allow', resource_arn)
    else:
        logger.warning(f"Unauthorized client: {client_id}")
        return generate_policy(client_id or 'unknown', 'Deny', resource_arn)


def generate_policy(principal_id: str, effect: str, resource: str) -> dict:
    """
    Generate an IAM policy document.
    
    Args:
        principal_id: The principal (client ID)
        effect: Allow or Deny
        resource: The resource ARN
        
    Returns:
        IAM policy document
    """
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        },
        'context': {
            'clientId': principal_id
        }
    }
'''


def display_summary(gen: CloudFormationGenerator):
    """Display configuration summary."""
    print_section("Configuration Summary")
    
    print(f"  Project Name: {Colors.CYAN}{gen.project_name}{Colors.END}")
    print(f"  Lambda Functions: {Colors.CYAN}{len(gen.lambda_functions)}{Colors.END}")
    print(f"  API Gateway: {Colors.CYAN}{'Yes' if gen.has_api_gateway else 'No'}{Colors.END}")
    if gen.has_api_gateway:
        print(f"    - Authorizer: {Colors.CYAN}{'Yes' if gen.has_authorizer else 'No'}{Colors.END}")
    print(f"  S3 Buckets: {Colors.CYAN}{len(gen.s3_buckets)}{Colors.END}")
    print(f"  Glue Jobs: {Colors.CYAN}{len(gen.glue_jobs)}{Colors.END}")
    print(f"  Step Functions: {Colors.CYAN}{len(gen.step_functions)}{Colors.END}")
    print(f"  SNS Topics: {Colors.CYAN}{len(gen.sns_topics)}{Colors.END}")
    print(f"  DynamoDB Tables: {Colors.CYAN}{len(gen.dynamodb_tables)}{Colors.END}")
    print(f"  SQS Queues: {Colors.CYAN}{len(gen.sqs_queues)}{Colors.END}")
    print(f"  Secrets Manager: {Colors.CYAN}{'Yes' if gen.has_secrets else 'No'}{Colors.END}")


def interactive_mode():
    """Run the interactive template generator."""
    print_header("AWS CloudFormation Template Generator")
    print("This tool will help you create a customized CloudFormation/SAM template")
    print("for your serverless application.\n")
    
    gen = CloudFormationGenerator()
    
    # Configure project
    configure_project(gen)
    
    # Select resources
    resources = display_resource_menu()
    
    # Track configured resources for cross-referencing
    lambda_functions = []
    glue_jobs = []
    
    # Configure each selected resource
    if "API Gateway" in resources:
        configure_api_gateway(gen)
    
    if "Lambda Functions" in resources:
        lambda_functions = configure_lambda_functions(gen)
    
    if "S3 Buckets" in resources:
        configure_s3_buckets(gen)
    
    if "Glue Jobs" in resources:
        glue_jobs = configure_glue_jobs(gen)
    
    if "Step Functions" in resources:
        configure_step_functions(gen, glue_jobs, lambda_functions)
    
    if "SNS Topics" in resources:
        configure_sns_topics(gen)
    
    if "DynamoDB Tables" in resources:
        configure_dynamodb_tables(gen)
    
    if "SQS Queues" in resources:
        configure_sqs_queues(gen)
    
    if "Secrets Manager" in resources:
        gen.add_secrets_manager()
        print_success("Secrets Manager configured")
    
    # Display summary
    display_summary(gen)
    
    # Confirm and generate
    if prompt_yes_no("\nGenerate template with this configuration?", True):
        output_dir = prompt("Output directory", "./output")
        generate_output_files(gen, output_dir)
        
        print_header("Generation Complete!")
        print(f"Files have been generated in: {Colors.CYAN}{output_dir}{Colors.END}")
        print("\nNext steps:")
        print("  1. Review the generated template")
        print("  2. Customize Lambda function code")
        print("  3. Update environment configs (dev.json, staging.json, prod.json)")
        print("  4. Deploy using SAM CLI or CI/CD pipeline")
    else:
        print_info("Generation cancelled")


def from_config_mode(config_path: str, output_dir: str):
    """Generate template from configuration file."""
    print_header("Generating from Configuration")
    
    try:
        gen = CloudFormationGenerator.from_json(config_path)
        print_success(f"Loaded configuration from: {config_path}")
        
        display_summary(gen)
        generate_output_files(gen, output_dir)
        
        print_header("Generation Complete!")
        print(f"Files have been generated in: {Colors.CYAN}{output_dir}{Colors.END}")
        
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)


def quick_mode(output_dir: str):
    """Generate a quick template with common defaults."""
    print_header("Quick Template Generation")
    
    project_name = prompt("Enter project name", "serverless-app")
    
    gen = CloudFormationGenerator()
    gen.set_project_name(project_name)
    
    # Add common resources with defaults
    gen.add_api_gateway(with_authorizer=True)
    gen.add_lambda_function("api", handler="app.handler", code_uri="lambda/api/",
                           api_events=[{"path": "/health", "method": "GET"}])
    gen.add_s3_bucket("DataBucket", "data")
    gen.add_glue_job("etl-processor", "etl_processor.py")
    gen.add_step_function("orchestrator", glue_jobs=["etl-processor"])
    gen.add_secrets_manager()
    
    display_summary(gen)
    generate_output_files(gen, output_dir)
    
    print_header("Generation Complete!")
    print(f"Files have been generated in: {Colors.CYAN}{output_dir}{Colors.END}")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="AWS CloudFormation Template Generator for Serverless Applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cfn-generate                           # Interactive mode
  cfn-generate --quick -o ./my-project   # Quick mode with defaults
  cfn-generate --config config.json      # Generate from config file
  cfn-generate --help                    # Show this help message

For more information, visit: https://github.com/your-org/cfn-generator
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        metavar='FILE',
        help='Load configuration from JSON file'
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
        version='CFN Generator 1.0.0'
    )
    
    args = parser.parse_args()
    
    try:
        if args.config:
            from_config_mode(args.config, args.output)
        elif args.quick:
            quick_mode(args.output)
        else:
            interactive_mode()
    except KeyboardInterrupt:
        print("\n")
        print_info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
