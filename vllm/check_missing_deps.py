import re

# Packages from requirements.txt
requirements = {
    'vllm', 'fastapi', 'uvicorn', 'pydantic', 'transformers', 'torch', 
    'huggingface-hub', 'websockets', 'httpx', 'peft', 'bitsandbytes', 
    'accelerate', 'datasets', 'trl', 'sentencepiece', 'protobuf', 
    'python-multipart', 'langchain', 'langchain-openai', 'langchain-core',
    'inflect', 'kanjize', 'numpy', 'phonemizer', 'sudachidict-full',
    'sudachipy', 'torchaudio', 'soundfile', 'boto3'
}

# Packages found in imports
imports = {
    'aioboto3', 'aiofiles', 'aiohttp', 'boto3', 'botocore', 'datasets',
    'dotenv', 'fastapi', 'httpx', 'huggingface_hub', 'inflect', 'kanjize',
    'langchain', 'langchain_core', 'langchain_openai', 'mamba_ssm', 'openai',
    'peft', 'phonemizer', 'pydantic', 'safetensors', 'sentence_transformers',
    'sudachipy', 'torch', 'torchaudio', 'tqdm', 'transformers', 'uvicorn', 'vllm'
}

# Normalize package names
def normalize_package(pkg):
    return pkg.replace('-', '_').lower()

requirements_normalized = {normalize_package(pkg) for pkg in requirements}
imports_normalized = {normalize_package(pkg) for pkg in imports}

# Find missing packages
missing = imports_normalized - requirements_normalized

print("Missing from requirements.txt:")
for pkg in sorted(missing):
    print(f"  - {pkg}")
