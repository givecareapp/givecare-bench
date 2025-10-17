"""
Setup configuration for LongitudinalBench.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="longitudinalbench",
    version="0.1.0",
    author="GiveCare Team",
    author_email="[email protected]",
    description="Open-source benchmark for evaluating AI safety in long-term care relationships",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/givecare/longitudinalbench",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "longitudinalbench=src.runner:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["scenarios/*.json"],
    },
)
