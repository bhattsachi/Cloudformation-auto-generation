# CFN Generator - AWS CloudFormation Template Generator

A standalone Python script to interactively generate CloudFormation/SAM templates for serverless applications. **No installation required.**

## Quick Start

```bash
# Download and run
python cfn_generate.py              # Interactive mode
python cfn_generate.py --quick      # Quick mode with defaults
python cfn_generate.py -o ./myapp   # Specify output directory
python cfn_generate.py --version    # Show version
python cfn_generate.py --help       # Show help
```

## Features

- **No Installation Required** - Single Python file, just run it
- **Interactive CLI** - Step-by-step wizard guides you through resource selection
- **Quick Mode** - Generate a complete template with common defaults in seconds
- **Multiple Resources** - Support for Lambda, API Gateway, Glue, Step Functions, and more
- **Production Ready** - Generates best-practice CloudFormation/SAM templates

## Supported Resources

| Resource | Description |
|----------|-------------|
| **API Gateway** | REST API with Client-ID header authorization |
| **Lambda Functions** | Serverless compute with IAM roles and CloudWatch logs |
| **S3 Buckets** | Object storage with encryption and versioning |
| **Glue Jobs** | ETL/data processing with configurable workers |
| **Step Functions** | Workflow orchestration with error handling |
| **SNS Topics** | Notification service with email subscriptions |
| **DynamoDB Tables** | NoSQL database with on-demand billing |
| **SQS Queues** | Message queues with dead-letter queues |
| **Secrets Manager** | Secure secrets storage |

## Usage Examples

### Interactive Mode (Recommended)

```bash
python cfn_generate.py
```

The wizard will guide you through:
1. Project name configuration
2. Resource selection (choose what you need)
3. Resource-specific settings
4. Template generation

### Quick Mode

```bash
python cfn_generate.py --quick -o ./my-pipeline
```

Generates a complete template with:
- API Gateway + Client-ID Authorizer
- Lambda function (api)
- S3 bucket
- Glue job
- Step Functions orchestrator
- Secrets Manager

### Generated Files

```
output/
├── serverless-app-template.yml    # Main CloudFormation/SAM template
├── buildspec.yml                  # CodeBuild configuration
├── dev.json                       # Development environment config
├── staging.json                   # Staging environment config
├── prod.json                      # Production environment config
├── generator-config.json          # Saved configuration (reusable)
├── lambda/
│   ├── api/
│   │   └── app.py                 # Lambda function stub
│   └── authorizer/
│       └── authorizer.py          # Authorizer function stub
└── glue/
    └── etl_processor.py           # Glue ETL script stub
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory (default: ./output) |
| `-q, --quick` | Quick mode with common defaults |
| `-v, --version` | Show version |
| `-h, --help` | Show help |

## Requirements

- Python 3.6+
- No external dependencies

## Integration with CI/CD

The generated `buildspec.yml` is ready for AWS CodePipeline:

```bash
# Deploy with SAM
cd output
sam build --template serverless-app-template.yml
sam deploy --guided
```

## Example Session

```
============================================================
           AWS CloudFormation Template Generator            
============================================================

>>> Project Configuration
Enter project/application name [serverless-app]: fhir-pipeline
✓ Project name: fhir-pipeline

>>> Select Resources to Include
(Enter numbers separated by commas, or 'all' for all options)
  [1] API Gateway - REST API with Client-ID authorization
  [2] Lambda Functions - Serverless compute functions
  [3] S3 Buckets - Object storage buckets
  [4] Glue Jobs - ETL/data processing jobs
  [5] Step Functions - Workflow orchestration
  [6] SNS Topics - Notification service
  [7] DynamoDB Tables - NoSQL database tables
  [8] SQS Queues - Message queues
  [9] Secrets Manager - Secure secrets storage

Enter choices: 3,4,5,6

>>> S3 Buckets Configuration
Bucket logical name (empty to finish): DataBucket
Bucket name suffix [data]: fhir-data
Enable versioning? [y/N]: n
✓ S3 bucket 'DataBucket' added

>>> Glue Jobs Configuration
Job name (empty to finish): fhir-processor
Script filename [fhir_processor.py]: 
Worker type:
  [1] G.025X (2 vCPU, 4GB - smallest)
  * [2] G.1X (4 vCPU, 16GB - standard)
  [3] G.2X (8 vCPU, 32GB - large)
Enter choice: 2
✓ Glue job 'fhir-processor' added

>>> Configuration Summary
  Project Name:      fhir-pipeline
  Lambda Functions:  0
  API Gateway:       No
  S3 Buckets:        2
  Glue Jobs:         1
  Step Functions:    1
  SNS Topics:        1

Generate template with this configuration? [Y/n]: y

>>> Generating Files
✓ serverless-app-template.yml
✓ dev.json
✓ staging.json
✓ prod.json
✓ buildspec.yml
✓ generator-config.json
✓ glue/fhir_processor.py

============================================================
                    Generation Complete!                    
============================================================
Files generated in: ./output
```

## License

MIT

## Author

DevOps Team
