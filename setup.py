from setuptools import setup, find_packages

setup(
    name="pyfix-rl",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["gymnasium>=0.26.0"],
    python_requires=">=3.11",
)
