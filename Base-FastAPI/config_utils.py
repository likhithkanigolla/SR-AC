import json
import re

def load_config(config_path):
    with open(config_path, 'r') as f:
        content = f.read()
        # Remove comments
        content = re.sub(r'#.*', '', content)
        # Fix multi-line string values (join lines inside quotes)
        content = re.sub(r'"([^"]*)\n\s*([^"]*)"', lambda m: '"' + m.group(1) + m.group(2) + '"', content)
        # Remove trailing commas before }} or ]]
        content = re.sub(r',\s*([}\]])', r'\1', content)
        # Remove any remaining newlines in quoted strings
        content = re.sub(r'"([^\"]*)\n([^\"]*)"', lambda m: '"' + m.group(1) + m.group(2) + '"', content)
        return json.loads(content)

def get_node_info(config, node_key):
    return config['nodes'].get(node_key, None)
