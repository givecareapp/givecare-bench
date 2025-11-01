#!/usr/bin/env python3
"""
Post Tool Use Hook - Tracks file edits for the stop hook
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def load_edit_log():
    """Load existing edit log"""
    log_path = Path(__file__).parent / ".edit-log.json"
    if not log_path.exists():
        return []

    try:
        with open(log_path) as f:
            return json.load(f)
    except Exception:
        return []

def save_edit_log(log):
    """Save edit log"""
    log_path = Path(__file__).parent / ".edit-log.json"
    try:
        with open(log_path, 'w') as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print(f"Error saving edit log: {e}", file=sys.stderr)

def main():
    # Read input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get('toolName', '')
    tool_input = input_data.get('toolInput', {})

    # Only track Edit, Write, and MultiEdit tools
    if tool_name not in ['Edit', 'Write', 'MultiEdit']:
        sys.exit(0)

    # Load existing log
    edit_log = load_edit_log()

    # Extract file paths based on tool type
    if tool_name == 'MultiEdit' and 'edits' in tool_input:
        # MultiEdit has array of edits
        for edit in tool_input['edits']:
            if 'file_path' in edit:
                edit_log.append({
                    'file': edit['file_path'],
                    'timestamp': datetime.now().isoformat(),
                    'tool': tool_name
                })
    elif 'file_path' in tool_input:
        # Edit or Write
        edit_log.append({
            'file': tool_input['file_path'],
            'timestamp': datetime.now().isoformat(),
            'tool': tool_name
        })
    elif 'notebook_path' in tool_input:
        # NotebookEdit
        edit_log.append({
            'file': tool_input['notebook_path'],
            'timestamp': datetime.now().isoformat(),
            'tool': tool_name
        })

    # Save updated log
    save_edit_log(edit_log)
    sys.exit(0)

if __name__ == '__main__':
    main()
