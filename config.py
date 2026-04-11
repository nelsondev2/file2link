# Enhanced Security Settings for config.py

# Rate limiting configuration
RATE_LIMIT_MSGS_PER_MIN = 30

# Queue limits configuration
QUEUE_LIMIT_MAX = 1000

# Markdown character escaping configuration
MARKDOWN_CHARACTER_ESCAPING = True

# Log level configuration
LOG_LEVEL = 'INFO'  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Validation function for production-ready bot

def validate_bot_settings(settings):
    """Validate the bot settings for production readiness."""
    if settings['rate_limit'] > 30:
        raise ValueError('Rate limit exceeds maximum of 30 messages per minute.')
    if settings['queue_limit'] > 1000:
        raise ValueError('Queue limit exceeds maximum of 1000 messages.')
    return True

# Initialize settings
bot_settings = {
    'rate_limit': RATE_LIMIT_MSGS_PER_MIN,
    'queue_limit': QUEUE_LIMIT_MAX
}
validate_bot_settings(bot_settings)
