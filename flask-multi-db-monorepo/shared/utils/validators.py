def validate_email(email):
    import re
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def validate_non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())

def validate_positive_integer(value):
    return isinstance(value, int) and value > 0

def validate_price(value):
    return isinstance(value, (int, float)) and value >= 0

def validate_tags(tags):
    return isinstance(tags, list) and all(isinstance(tag, str) for tag in tags)