"""
Resource definitions for CloudFormation template generation.
Each resource type has its template snippet and required parameters.
"""

# IAM Role Templates
IAM_LAMBDA_ROLE = """
  {role_name}:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${{ApplicationName}}-{role_suffix}-${{EnvironmentName}}
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
        - PolicyName: {policy_name}
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
{policy_statements}
"""

IAM_GLUE_ROLE = """
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
                Resource: '*'
"""

IAM_STEPFUNCTIONS_ROLE = """
  StepFunctionsRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${ApplicationName}-stepfn-role-${EnvironmentName}
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
{stepfn_permissions}
"""

# Lambda Function Template
LAMBDA_FUNCTION = """
  {function_name}:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub ${{ApplicationName}}-{function_suffix}-${{EnvironmentName}}
      Handler: {handler}
      Runtime: python3.9
      CodeUri: {code_uri}
      Role: !GetAtt {role_name}.Arn
      Timeout: {timeout}
      MemorySize: {memory_size}
      Environment:
        Variables:
          ENVIRONMENT: !Ref EnvironmentName
          APPLICATION_NAME: !Ref ApplicationName
          AWS_REGION_NAME: !Ref AWS::Region
{extra_env_vars}
{events}
"""

LAMBDA_LOG_GROUP = """
  {function_name}LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/lambda/${{ApplicationName}}-{function_suffix}-${{EnvironmentName}}
      RetentionInDays: !Ref LogRetentionDays
"""

# API Gateway Template
API_GATEWAY = """
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      Name: !Sub ${ApplicationName}-api-${EnvironmentName}
      StageName: !Ref EnvironmentName
      TracingEnabled: true
      Cors:
        AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
        AllowHeaders: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,Client-ID'"
        AllowOrigin: "'*'"
{auth_config}
"""

API_GATEWAY_AUTH = """
      Auth:
        DefaultAuthorizer: ClientIdAuthorizer
        Authorizers:
          ClientIdAuthorizer:
            FunctionArn: !GetAtt ClientIdAuthorizerFunction.Arn
            Identity:
              Headers:
                - Client-ID
              ReauthorizeEvery: 300
"""

AUTHORIZER_FUNCTION = """
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
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiGateway}/*
"""

# S3 Bucket Template
S3_BUCKET = """
  {bucket_name}:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${{ApplicationName}}-{bucket_suffix}-${{AWS::AccountId}}-${{AWS::Region}}
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
        Status: {versioning}
{lifecycle_rules}
"""

# Glue Job Template
GLUE_JOB = """
  {job_name}:
    Type: AWS::Glue::Job
    DependsOn: GlueScriptUploader
    Properties:
      Name: !Sub ${{ApplicationName}}-{job_suffix}-${{EnvironmentName}}
      Description: {description}
      Role: !GetAtt GlueJobRole.Arn
      GlueVersion: '4.0'
      WorkerType: {worker_type}
      NumberOfWorkers: {num_workers}
      Timeout: {timeout}
      Command:
        Name: glueetl
        ScriptLocation: !Sub s3://${{GlueDataBucket}}/scripts/{script_name}
        PythonVersion: '3'
      DefaultArguments:
        '--job-language': python
        '--enable-metrics': 'true'
        '--enable-continuous-cloudwatch-log': 'true'
        '--ENVIRONMENT': !Ref EnvironmentName
        '--APPLICATION_NAME': !Ref ApplicationName
        '--AWS_REGION_NAME': !Ref AWS::Region
        '--GLUE_BUCKET': !Ref GlueDataBucket
{extra_args}
"""

GLUE_SCRIPT_UPLOADER = """
  GlueScriptUploaderFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub ${ApplicationName}-glue-uploader-${EnvironmentName}
      Runtime: python3.9
      Handler: index.handler
      Timeout: 60
      Role: !GetAtt GlueScriptUploaderRole.Arn
      Environment:
        Variables:
          BUCKET_NAME: !Ref GlueDataBucket
      Code:
        ZipFile: |
          import boto3
          import cfnresponse
          import os
          
          GLUE_SCRIPTS = {glue_scripts}
          
          def handler(event, context):
              try:
                  bucket = os.environ['BUCKET_NAME']
                  s3 = boto3.client('s3')
                  
                  if event['RequestType'] in ['Create', 'Update']:
                      for script_name, script_content in GLUE_SCRIPTS.items():
                          s3.put_object(
                              Bucket=bucket,
                              Key=f'scripts/{{script_name}}',
                              Body=script_content.encode('utf-8')
                          )
                  
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {{}})
              except Exception as e:
                  print(f"Error: {{e}}")
                  cfnresponse.send(event, context, cfnresponse.FAILED, {{'Error': str(e)}})

  GlueScriptUploaderRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub ${ApplicationName}-glue-uploader-role-${EnvironmentName}
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
        - PolicyName: S3WriteAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:PutObject
                  - s3:DeleteObject
                Resource: !Sub arn:aws:s3:::${GlueDataBucket}/*

  GlueScriptUploader:
    Type: Custom::GlueScriptUploader
    Properties:
      ServiceToken: !GetAtt GlueScriptUploaderFunction.Arn
"""

# Step Functions Template
STEP_FUNCTION = """
  {state_machine_name}:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      StateMachineName: !Sub ${{ApplicationName}}-{state_machine_suffix}-${{EnvironmentName}}
      RoleArn: !GetAtt StepFunctionsRole.Arn
      TracingConfiguration:
        Enabled: true
      DefinitionString: !Sub |
{definition}
"""

STEP_FUNCTION_LOG_GROUP = """
  StepFunctionsLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/stepfunctions/${ApplicationName}-{state_machine_suffix}-${EnvironmentName}
      RetentionInDays: !Ref LogRetentionDays
"""

# SNS Topic Template
SNS_TOPIC = """
  {topic_name}:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub ${{ApplicationName}}-{topic_suffix}-${{EnvironmentName}}
      DisplayName: {display_name}
"""

SNS_SUBSCRIPTION = """
  {subscription_name}:
    Type: AWS::SNS::Subscription
    Condition: Has{condition_name}
    Properties:
      TopicArn: !Ref {topic_ref}
      Protocol: email
      Endpoint: !Ref {email_param}
"""

# Secrets Manager Template
SECRETS_MANAGER = """
  ApplicationSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: !Sub ${ApplicationName}-secrets-${EnvironmentName}
      Description: Application secrets
      GenerateSecretString:
        SecretStringTemplate: '{}'
        GenerateStringKey: api_key
        PasswordLength: 32
        ExcludeCharacters: '"@/\\'
"""

# DynamoDB Table Template
DYNAMODB_TABLE = """
  {table_name}:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${{ApplicationName}}-{table_suffix}-${{EnvironmentName}}
      BillingMode: {billing_mode}
      AttributeDefinitions:
{attribute_definitions}
      KeySchema:
{key_schema}
{gsi_config}
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
"""

# SQS Queue Template
SQS_QUEUE = """
  {queue_name}:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{queue_suffix}-${{EnvironmentName}}
      VisibilityTimeout: {visibility_timeout}
      MessageRetentionPeriod: {retention_period}
      ReceiveMessageWaitTimeSeconds: {wait_time}
{dlq_config}
"""

SQS_DLQ = """
  {queue_name}DLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${{ApplicationName}}-{queue_suffix}-dlq-${{EnvironmentName}}
      MessageRetentionPeriod: 1209600
"""

# EventBridge Rule Template
EVENTBRIDGE_RULE = """
  {rule_name}:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub ${{ApplicationName}}-{rule_suffix}-${{EnvironmentName}}
      Description: {description}
      State: ENABLED
      ScheduleExpression: {schedule}
      Targets:
        - Id: {target_id}
          Arn: {target_arn}
          RoleArn: {role_arn}
"""
