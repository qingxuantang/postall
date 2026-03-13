#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="postall-agent",
    version="0.1.0",
    description="AI-friendly CLI for PostAll content generation and publishing",
    author="Mark Zhou",
    author_email="mark@example.com",
    url="https://github.com/hukongyi/postall",
    py_modules=["cli"],
    install_requires=[
        "anthropic>=0.18.0",
        "google-generativeai>=0.3.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "postall-agent=cli:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
