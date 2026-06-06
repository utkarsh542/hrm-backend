"""Centralized logger, global sensitive data masking filter, and CustomMaskingLogger subclass."""
import logging
import sys
import re

# Regex to match email addresses
EMAIL_REGEX = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b')

# Regex to detect key-value lines containing sensitive fields
KEY_VALUE_REGEX = re.compile(
    r'\b(password|pass|temp_pass|secret|secret key|secret_key|key|token|api_key|pan_number|pan number|aadhar_number|aadhar number|aadhar|bank_account|bank account|bank_name|bank name|ifsc_code|ifsc code|ctc|username|username \(email\)|username / email|temporary password|security code|pin)\b'
    r'\s*[:=]\s*'
    r'([^\n\r]+)',
    re.IGNORECASE
)

# Explicit default values/patterns (e.g. Welcome@123, admin123, etc.)
DEFAULT_VALS_REGEX = re.compile(r'\b(Welcome@\d+|admin\d+|hr\d+|employee\d+|manager\d+)\b', re.IGNORECASE)

def mask_email(email: str) -> str:
    """Mask email address to protect privacy (e.g. user@domain.com -> u***@domain.com)."""
    if not email or "@" not in email:
        return email
    parts = email.split("@")
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[0] + "*" * (len(name) - 1)
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"

def mask_sensitive_info(msg: str) -> str:
    """Identify and mask all sensitive credentials, emails, or personal details in a message."""
    if not isinstance(msg, str):
        return msg
        
    # 1. Mask email patterns
    def email_repl(match):
        return mask_email(match.group(0))
    msg = EMAIL_REGEX.sub(email_repl, msg)
    
    # 2. Mask key-value patterns (e.g., "Password: Welcome@123")
    def key_value_repl(match):
        key = match.group(1)
        val = match.group(2)
        masked_val = "*" * max(len(val.strip()), 8)
        return f"{key}: {masked_val}"
        
    msg = KEY_VALUE_REGEX.sub(key_value_repl, msg)
    
    # 3. Mask explicit default credentials (Welcome@123 etc.)
    msg = DEFAULT_VALS_REGEX.sub("********", msg)
    
    return msg

class SensitiveDataFilter(logging.Filter):
    """Custom logging filter that automatically masks sensitive information in all log records."""
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_info(record.msg)
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(mask_sensitive_info(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        return True

class CustomMaskingLogger(logging.Logger):
    """Custom Logger class that explicitly masks sensitive details and forces structured info/warning/error methods."""
    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        # Add the filter automatically
        if not any(isinstance(f, SensitiveDataFilter) for f in self.filters):
            self.addFilter(SensitiveDataFilter())

    def info(self, msg, *args, **kwargs):
        if 'stacklevel' not in kwargs:
            kwargs['stacklevel'] = 2
        masked_msg = mask_sensitive_info(str(msg))
        super().info(masked_msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        if 'stacklevel' not in kwargs:
            kwargs['stacklevel'] = 2
        masked_msg = mask_sensitive_info(str(msg))
        super().warning(masked_msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if 'stacklevel' not in kwargs:
            kwargs['stacklevel'] = 2
        masked_msg = mask_sensitive_info(str(msg))
        super().error(masked_msg, *args, **kwargs)

# Register CustomMaskingLogger as the default class for getLogger
logging.setLoggerClass(CustomMaskingLogger)

# Detailed log formatter string for application logs (timestamp, log level, file name, line number, and masked message)
LOG_FORMAT_APP = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

# Simplified log formatter string for third-party system/uvicorn logs (avoys printing internal dependency files)
LOG_FORMAT_SIMPLE = "%(asctime)s - %(levelname)s - %(message)s"

def get_logger(name: str = "app") -> logging.Logger:
    """Get a configured CustomMaskingLogger instance with standard stream formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Configure custom stream handler if no handlers are set
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT_APP, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        
    return logger

def configure_global_logging():
    """Register the SensitiveDataFilter and standard formatters on all loggers."""
    loggers_to_filter = ["uvicorn", "uvicorn.error", "uvicorn.access", "app", "fastapi"]
    for logger_name in loggers_to_filter:
        logger = logging.getLogger(logger_name)
        
        # Inject our masking filter
        if not any(isinstance(f, SensitiveDataFilter) for f in logger.filters):
            logger.addFilter(SensitiveDataFilter())
            
        # Select appropriate format: detailed for our code, simple for system loggers
        fmt_str = LOG_FORMAT_APP if logger_name == "app" else LOG_FORMAT_SIMPLE
        
        # Apply formatter to existing handlers
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S"))

# Default app logger instance
logger = get_logger("app")
configure_global_logging()
