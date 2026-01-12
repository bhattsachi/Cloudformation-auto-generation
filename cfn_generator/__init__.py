"""
CFN Generator - AWS CloudFormation Template Generator for Serverless Applications

A Python library and CLI tool to interactively generate CloudFormation/SAM templates
based on developer requirements.

Usage:
    cfn-generate                    # Interactive mode
    cfn-generate --config config.json  # From config file
    cfn-generate --quick            # Quick mode with defaults
"""

__version__ = "1.0.0"
__author__ = "DevOps Team"

from .generator import CloudFormationGenerator
from .cli import main

__all__ = ["CloudFormationGenerator", "main"]
