# CFN Generator - AWS CloudFormation Template Generator

A Python library and CLI tool to interactively generate CloudFormation/SAM templates based on developer requirements.

## Features

- **Interactive CLI**: Step-by-step wizard to configure your serverless resources
- **Multiple Resource Types**: Support for Lambda, API Gateway, Glue, Step Functions, S3, DynamoDB, SQS, SNS, and more
- **Template Generation**: Generates production-ready SAM/CloudFormation templates
- **Environment Configs**: Auto-generates dev.json, staging.json, prod.json
- **Code Stubs**: Creates Lambda function and authorizer boilerplate code
- **Reusable Configs**: Save and load configurations for consistent template generation

## Installation

```bash
# Install from source
cd cfn-generator
pip install -e .

# Or install directly
pip install cfn-generator
```

## Quick Start

### Interactive Mode (Recommended)

```bash
cfn-generate
```

This launches an interactive wizard that guides you through:
1. Project configuration
2. Resource selection
3. Resource-specific settings
4. Template generation

### Quick Mode

Generate a template with common defaults:

```bash
cfn-generate --quick -o ./my-project
```

### From Configuration File

```bash
cfn-generate --config my-config.json -o ./output
```

## Usage Examples

### Example 1: API + Lambda + DynamoDB

```bash
$ cfn-generate

>>> Project Configuration
Enter project/application name [serverless-app]: user-service

>>> Select Resources to Include
[1] API Gateway
[2] Lambda Functions
[7] DynamoDB Tables

Enter choices: 1,2,7

# Follow the prompts to configure each resource...
```

### Example 2: ETL Pipeline (Glue + Step Functions)

```bash
$ cfn-generate

>>> Select Resources to Include
[3] S3 Buckets
[4] Glue Jobs
[5] Step Functions
[6] SNS Topics

Enter choices: 3,4,5,6

# Configure your ETL pipeline...
```

### Example 3: Programmatic Usage

```python
from cfn_generator import CloudFormationGenerator

# Create generator
gen = CloudFormationGenerator()
gen.set_project_name("my-service")

# Add resources
gen.add_api_gateway(with_authorizer=True)
gen.add_lambda_function(
    name="api",
    handler="app.handler",
    code_uri="lambda/api/",
    api_events=[{"path": "/users", "method": "GET"}]
)
gen.add_dynamodb_table(
    name="Users",
    suffix="users",
    partition_key="userId",
    partition_key_type="S"
)

# Generate template
gen.generate("output/template.yml")
gen.generate_env_config("dev", "output/dev.json")
```

## Supported Resources

| Resource | Description |
|----------|-------------|
| **API Gateway** | REST API with optional Client-ID authorization |
| **Lambda Functions** | Serverless compute with IAM roles and CloudWatch logs |
| **S3 Buckets** | Object storage with versioning and lifecycle rules |
| **Glue Jobs** | ETL/data processing with auto-generated scripts |
| **Step Functions** | Workflow orchestration with error handling |
| **SNS Topics** | Notification service with email subscriptions |
| **DynamoDB Tables** | NoSQL database with GSI support |
| **SQS Queues** | Message queues with dead-letter queues |
| **Secrets Manager** | Secure secrets storage |

## Output Files

The generator creates the following files:

```
output/
├── serverless-app-template.yml    # Main CloudFormation/SAM template
├── buildspec.yml                  # CodeBuild configuration
├── dev.json                       # Development environment config
├── staging.json                   # Staging environment config
├── prod.json                      # Production environment config
├── generator-config.json          # Saved configuration (reusable)
└── lambda/
    ├── api/
    │   └── app.py                 # Lambda function stub
    └── authorizer/
        └── authorizer.py          # Authorizer function stub
```

## CLI Options

```
usage: cfn-generate [-h] [--config FILE] [--output DIR] [--quick] [--version]

AWS CloudFormation Template Generator for Serverless Applications

optional arguments:
  -h, --help            show this help message and exit
  --config FILE, -c FILE
                        Load configuration from JSON file
  --output DIR, -o DIR  Output directory (default: ./output)
  --quick, -q           Quick mode with common defaults
  --version, -v         show program's version number and exit
```

## Configuration File Format

You can save and reuse configurations:

```json
{
  "project_name": "my-service",
  "lambda_functions": [
    {
      "name": "api",
      "handler": "app.handler",
      "code_uri": "lambda/api/",
      "timeout": 30,
      "memory_size": 256,
      "api_events": [
        {"path": "/users", "method": "GET"},
        {"path": "/users", "method": "POST"}
      ]
    }
  ],
  "glue_jobs": [
    {
      "name": "etl-processor",
      "script_name": "etl_processor.py",
      "worker_type": "G.1X",
      "num_workers": 2,
      "timeout": 60
    }
  ],
  "has_api_gateway": true,
  "has_authorizer": true
}
```

## Best Practices

1. **Start with Quick Mode**: Use `--quick` to generate a base template, then customize
2. **Save Configurations**: Keep `generator-config.json` in version control
3. **Review Generated Code**: Always review and customize the generated Lambda stubs
4. **Environment Configs**: Update notification emails and Client IDs per environment
5. **Validate Templates**: Run `sam validate` before deploying

## Integration with CI/CD

The generated `buildspec.yml` is compatible with AWS CodeBuild and CodePipeline:

```bash
# Deploy the generated template
sam build --template serverless-app-template.yml
sam deploy --guided
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/your-org/cfn-generator/issues)
- Documentation: [Full documentation](https://github.com/your-org/cfn-generator/wiki)
