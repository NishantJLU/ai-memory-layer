import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

def get_python_parser():
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)
    return parser

def extract_structural_context(code: str) -> dict:
    """
    Extracts high-level structural info (functions, classes) from Python code.
    """
    parser = get_python_parser()
    tree = parser.parse(bytes(code, "utf8"))
    
    classes = []
    functions = []
    
    # Simple query to find class and function definitions
    # Note: For production, we'd use more complex S-expression queries
    root_node = tree.root_node
    
    for child in root_node.children:
        if child.type == 'class_definition':
            name_node = child.child_by_field_name('name')
            if name_node:
                classes.append(code[name_node.start_byte:name_node.end_byte])
        elif child.type == 'function_definition':
            name_node = child.child_by_field_name('name')
            if name_node:
                functions.append(code[name_node.start_byte:name_node.end_byte])
                
    return {
        "classes": classes,
        "functions": functions
    }

def get_diff_structural_context(diff_text: str) -> str:
    """
    Analyzes a diff to find what structural elements were likely touched.
    """
    # This is a heuristic: we look for function/class definitions in the diff lines
    added_functions = []
    for line in diff_text.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            if 'def ' in line:
                name = line.split('def ')[1].split('(')[0].strip()
                added_functions.append(name)
            elif 'class ' in line:
                name = line.split('class ')[1].split('(')[0].split(':')[0].strip()
                added_functions.append(name)
                
    if not added_functions:
        return ""
    
    return f"Structural elements touched: {', '.join(added_functions)}"
