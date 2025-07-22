"""
Centralized error messages for consistency
All error messages should be in English for consistency.
"""

# API Key and Authentication Errors
API_KEY_NOT_SET = "API key not configured. Please set the required environment variable."
INVALID_API_KEY = "Invalid API key provided."
AUTHENTICATION_FAILED = "Authentication failed. Please check your credentials."

# File Operation Errors
FILE_NOT_FOUND = "File not found: {filepath}"
FILE_READ_ERROR = "Failed to read file: {filepath}. Error: {error}"
FILE_WRITE_ERROR = "Failed to write file: {filepath}. Error: {error}"
INVALID_FILE_PATH = "Invalid file path provided: {filepath}"
FILE_DELETE_ERROR = "Failed to delete file: {filepath}. Error: {error}"

# Model and Adapter Errors
MODEL_NOT_LOADED = "Model not loaded. Please initialize the engine first."
ADAPTER_NOT_FOUND = "Adapter not found: {adapter_id}"
ADAPTER_LOAD_FAILED = "Failed to load adapter: {adapter_id}. Error: {error}"
MAX_ADAPTERS_REACHED = "Maximum number of adapters ({max_adapters}) already loaded."
INVALID_MODEL_CONFIG = "Invalid model configuration: {error}"

# Generation Errors
GENERATION_FAILED = "Text generation failed: {error}"
INVALID_GENERATION_PARAMS = "Invalid generation parameters: {error}"
TOKEN_LIMIT_EXCEEDED = "Token limit exceeded. Maximum allowed: {max_tokens}"

# Fine-tuning Errors
FINETUNING_TASK_NOT_FOUND = "Fine-tuning task not found: {task_id}"
FINETUNING_FAILED = "Fine-tuning failed: {error}"
FINETUNING_IN_PROGRESS = "Another fine-tuning task is already in progress."
INSUFFICIENT_GPU_MEMORY = "Insufficient GPU memory for fine-tuning. Available: {available}MB, Required: {required}MB"

# TTS Errors
TTS_GENERATION_FAILED = "TTS generation failed: {error}"
TTS_TASK_NOT_FOUND = "TTS task not found: {task_id}"
VOICE_FILE_INVALID = "Invalid voice file format. Supported formats: {formats}"
TTS_MODEL_NOT_LOADED = "TTS model not loaded. Please initialize first."

# S3 Errors
S3_UPLOAD_FAILED = "Failed to upload to S3: {error}"
S3_DOWNLOAD_FAILED = "Failed to download from S3: {error}"
S3_CREDENTIALS_MISSING = "AWS credentials not configured."
S3_BUCKET_NOT_FOUND = "S3 bucket not found: {bucket}"

# General Errors
INTERNAL_SERVER_ERROR = "Internal server error occurred: {error}"
INVALID_REQUEST = "Invalid request: {error}"
RESOURCE_NOT_FOUND = "Resource not found: {resource}"
OPERATION_TIMEOUT = "Operation timed out after {timeout} seconds."
SERVICE_UNAVAILABLE = "Service temporarily unavailable. Please try again later."

# Validation Errors
INVALID_INPUT = "Invalid input: {field} - {error}"
MISSING_REQUIRED_FIELD = "Missing required field: {field}"
INVALID_DATA_FORMAT = "Invalid data format: {error}"

# GPU/Hardware Errors
GPU_NOT_AVAILABLE = "GPU not available. CPU mode is not supported."
GPU_MEMORY_ERROR = "GPU memory error: {error}"
CUDA_ERROR = "CUDA error occurred: {error}"


def format_error_message(template: str, **kwargs) -> str:
    """
    Format error message with provided parameters
    
    Args:
        template: Error message template
        **kwargs: Parameters to format the template
        
    Returns:
        Formatted error message
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        return f"{template} (formatting error: missing {e})"
    except Exception:
        return template


# Error response helper
def create_error_response(error_template: str, status_code: int = 500, **kwargs) -> dict:
    """
    Create standardized error response
    
    Args:
        error_template: Error message template
        status_code: HTTP status code
        **kwargs: Parameters for error message formatting
        
    Returns:
        Error response dictionary
    """
    return {
        "error": format_error_message(error_template, **kwargs),
        "status_code": status_code,
        "success": False
    }