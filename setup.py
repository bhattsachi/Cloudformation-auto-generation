#!/usr/bin/env python3
"""
Setup script for CFN Generator package.
"""

from setuptools import setup, find_packages

setup(
    name="cfn-generator",
    version="1.0.0",
    author="DevOps Team",
    author_email="devops@example.com",
    description="AWS CloudFormation Template Generator for Serverless Applications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/cfn-generator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "cfn-generate=cfn_generator.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
