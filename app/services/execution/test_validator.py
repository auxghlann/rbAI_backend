"""
Test validation utilities for automatic function testing.
Extracts function names from code and generates test wrappers.
"""

import re
from typing import Optional, List, Tuple


def extract_function_name(code: str) -> Optional[str]:
    """
    Extract the main function name from user code.
    Looks for function definitions and returns the first one found.
    
    Args:
        code: User's Python code
        
    Returns:
        Function name or None if no function found
    """
    # Match function definitions: def function_name(params):
    pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    match = re.search(pattern, code)
    
    if match:
        return match.group(1)
    return None


def parse_test_input(input_str: str) -> List[str]:
    """
    Parse test input string into function arguments.
    
    Examples:
        "5, 3" -> ["5", "3"]
        "10, 20" -> ["10", "20"]
        "-5, 3" -> ["-5", "3"]
        
    Args:
        input_str: Comma-separated input values
        
    Returns:
        List of argument strings
    """
    if not input_str.strip():
        return []
    
    # Split by comma and strip whitespace
    args = [arg.strip() for arg in input_str.split(',')]
    return args


def generate_test_wrapper(user_code: str, function_name: str, test_args: List[str]) -> str:
    """
    Generate code that wraps user code and calls the function with test arguments.
    
    Args:
        user_code: User's function definition
        function_name: Name of the function to test
        test_args: List of argument values as strings
        
    Returns:
        Complete Python code that executes the test
    """
    # Build function call with arguments
    args_str = ', '.join(test_args)
    
    wrapper = f'''# User's code
{user_code}

# Automated test execution
if __name__ == '__main__':
    try:
        result = {function_name}({args_str})
        print(result)
    except Exception as e:
        print(f"Error: {{e}}", file=__import__('sys').stderr)
        raise
'''
    
    return wrapper


def create_test_code(user_code: str, test_input: str) -> Tuple[str, Optional[str]]:
    """
    Create executable test code from user code and test input.
    
    Args:
        user_code: User's Python code with function definition
        test_input: Test case input (e.g., "5, 3")
        
    Returns:
        Tuple of (executable_code, error_message)
        If error_message is not None, code generation failed
    """
    # Extract function name
    func_name = extract_function_name(user_code)
    
    if not func_name:
        return "", "No function definition found in code"
    
    # Parse test input into arguments
    test_args = parse_test_input(test_input)
    
    # Generate wrapper code
    test_code = generate_test_wrapper(user_code, func_name, test_args)
    
    return test_code, None
