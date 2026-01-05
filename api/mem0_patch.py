"""
Patch for mem0 library to fix LLM response parsing issues.
This script modifies the mem0 library's main.py to handle various LLM response formats.
"""

import os
import sys

def apply_patch():
    """Apply patch to mem0 library"""
    mem0_main_path = "/usr/local/lib/python3.12/site-packages/mem0/memory/main.py"
    
    if not os.path.exists(mem0_main_path):
        print(f"Error: {mem0_main_path} not found")
        return False
    
    # Read the file
    with open(mem0_main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the problematic section
    old_code = '''        try:
            response = remove_code_blocks(response)
            if not response.strip():
                new_retrieved_facts = []
            else:
                try:
                    # First try direct JSON parsing
                    new_retrieved_facts = json.loads(response)["facts"]
                except json.JSONDecodeError:
                    # Try extracting JSON from response using built-in function
                    extracted_json = extract_json(response)
                    new_retrieved_facts = json.loads(extracted_json)["facts"]
        except Exception as e:
            logger.error(f"Error in new_retrieved_facts: {e}")
            new_retrieved_facts = []'''
    
    new_code = '''        try:
            response = remove_code_blocks(response)
            if not response.strip():
                new_retrieved_facts = []
            else:
                try:
                    # First try direct JSON parsing
                    parsed = json.loads(response)
                    # Handle case where response is double-encoded
                    if isinstance(parsed, str):
                        parsed = json.loads(parsed)
                    # Extract facts - ensure we get a list of strings
                    if isinstance(parsed, dict) and "facts" in parsed:
                        facts = parsed["facts"]
                        # Ensure facts is a list of strings
                        if isinstance(facts, list):
                            new_retrieved_facts = [str(f) if not isinstance(f, str) else f for f in facts]
                        else:
                            new_retrieved_facts = []
                    elif isinstance(parsed, list):
                        # If parsed is a list, convert each element to string
                        new_retrieved_facts = [str(item) if not isinstance(item, str) else item for item in parsed]
                    else:
                        new_retrieved_facts = []
                except json.JSONDecodeError:
                    # Try extracting JSON from response using built-in function
                    try:
                        extracted_json = extract_json(response)
                        parsed = json.loads(extracted_json)
                        if isinstance(parsed, str):
                            parsed = json.loads(parsed)
                        if isinstance(parsed, dict) and "facts" in parsed:
                            facts = parsed["facts"]
                            if isinstance(facts, list):
                                new_retrieved_facts = [str(f) if not isinstance(f, str) else f for f in facts]
                            else:
                                new_retrieved_facts = []
                        elif isinstance(parsed, list):
                            new_retrieved_facts = [str(item) if not isinstance(item, str) else item for item in parsed]
                        else:
                            new_retrieved_facts = []
                    except:
                        new_retrieved_facts = []
        except Exception as e:
            logger.error(f"Error in new_retrieved_facts: {e}")
            new_retrieved_facts = []'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back
        with open(mem0_main_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Patch applied successfully!")
        return True
    else:
        print("⚠️  Could not find the code section to patch. The file may have been updated.")
        return False

if __name__ == "__main__":
    success = apply_patch()
    sys.exit(0 if success else 1)