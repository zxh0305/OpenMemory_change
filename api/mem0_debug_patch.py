"""
Debug patch for mem0 library to log LLM responses.
"""

import os

def apply_debug_patch():
    """Apply debug logging patch to mem0 library"""
    mem0_main_path = "/usr/local/lib/python3.12/site-packages/mem0/memory/main.py"
    
    if not os.path.exists(mem0_main_path):
        print(f"Error: {mem0_main_path} not found")
        return False
    
    # Read the file
    with open(mem0_main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add debug logging after response generation
    old_code = '''        try:
            response = remove_code_blocks(response)
            if not response.strip():'''
    
    new_code = '''        try:
            logger.info(f"[DEBUG] Raw LLM response: {response[:500]}")
            response = remove_code_blocks(response)
            logger.info(f"[DEBUG] After remove_code_blocks: {response[:500]}")
            if not response.strip():'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back
        with open(mem0_main_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Debug patch applied successfully!")
        return True
    else:
        print("⚠️  Could not find the code section to patch.")
        return False

if __name__ == "__main__":
    import sys
    success = apply_debug_patch()
    sys.exit(0 if success else 1)