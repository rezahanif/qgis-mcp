#!/usr/bin/env python3
"""Convert Field(default=X, description="...") to Annotated[type, Field(description="...")] = X.

Processes each line independently. For multi-parameter lines (multiple Field() on one line),
we process them right-to-left so earlier replacements don't shift positions.
"""
import re

def find_field_call(line, start=0):
    """Find a Field() call starting from position start. Returns (field_content, start_pos, end_pos) or None."""
    pos = line.find('= Field(', start)
    if pos == -1:
        return None
    
    paren_start = pos + len('= Field(')
    depth = 0
    j = paren_start
    while j < len(line):
        if line[j] == '(':
            depth += 1
        elif line[j] == ')':
            if depth == 0:
                break
            depth -= 1
        elif line[j] == '"':
            j += 1
            while j < len(line):
                if line[j] == '\\':
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
        j += 1
    
    field_content = line[paren_start:j]  # content inside Field()
    return field_content, pos, j + 1  # pos = "= Field(", j+1 = after closing ")"


def find_param_before(line, field_start):
    """Find the 'name: type' pattern immediately before '= Field(' at position field_start."""
    # Look backward from field_start for "name: type = "
    # The '= ' is part of '= Field(', so before_field ends right before '='
    before = line[:field_start]
    
    # Find the last "name: type = " — but '=' is NOT in before, it's part of '= Field('
    # So find "name: type " at the end of before (with trailing space or comma-space)
    # The pattern before each '= Field(' is: ...other_params..., name: type 
    # We need to find: word: complex_type followed by optional whitespace
    
    # Match from end: optional whitespace, then "type", then ":", then "name"
    m = re.search(r'(\w+):\s*([\w\[\]| ,]+?)\s*$', before)
    if not m:
        return None
    
    name = m.group(1)
    typ = m.group(2).strip()
    # The matched span starts at m.start()
    return name, typ, m.start()


def convert_line(line):
    """Convert all Field(...) on a single line."""
    # Collect all Field positions right-to-left
    fields = []
    pos = 0
    while True:
        result = find_field_call(line, pos)
        if result is None:
            break
        content, start, end = result
        fields.append((content, start, end))
        pos = end
    
    if not fields:
        return line, False
    
    # Process right-to-left so positions don't shift
    for content, start, end in reversed(fields):
        # Extract description
        desc_match = re.search(r'description="((?:[^"\\]|\\.)*)"', content)
        if not desc_match:
            continue
        description = desc_match.group(1)
        
        # Extract default
        default_match = re.search(r'default=(.+?),\s*description=', content)
        default_value = default_match.group(1).strip() if default_match else None
        
        # Find param name and type before "= Field("
        param_info = find_param_before(line, start)
        if not param_info:
            continue
        param_name, param_type, param_start = param_info
        
        # Build replacement
        replacement = f'{param_name}: Annotated[{param_type}, Field(description="{description}")]'
        if default_value is not None:
            replacement += f' = {default_value}'
        
        # Replace from param_start to end
        line = line[:param_start] + replacement + line[end:]
    
    return line, True


def main():
    path = 'qgis_mcp/server.py'
    with open(path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    total_converted = 0
    
    for line in lines:
        if '= Field(' in line:
            new_line, changed = convert_line(line.rstrip('\n'))
            if changed:
                total_converted += 1
            new_lines.append(new_line + '\n')
        else:
            new_lines.append(line)
    
    content = ''.join(new_lines)
    if 'from typing import Annotated' not in content:
        content = content.replace(
            'from typing import Any',
            'from typing import Annotated, Any'
        )
    
    with open(path, 'w') as f:
        f.write(content)
    
    print(f"Converted {total_converted} lines")


if __name__ == '__main__':
    main()
