import os

def walk(dir):
    results = []
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith('.tsx') or file.endswith('.ts'):
                results.append(os.path.join(root, file))
    return results

files = walk('src')
for file in files:
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original = content
        
        # Replace colors
        content = content.replace('#0052ff', '#7c3aed')
        content = content.replace('#578bfa', '#8b5cf6')
        content = content.replace('#0a0b0d', '#18181b')
        content = content.replace('#282b31', '#000000')
        content = content.replace('#eef0f3', '#f4f4f5')
        content = content.replace('#0667d0', '#6d28d9')
        content = content.replace('#5b616e', '#52525b')
        
        # Replace heroicons outline with solid
        content = content.replace('@heroicons/react/24/outline', '@heroicons/react/24/solid')
        
        if content != original:
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {file}")
    except Exception as e:
        print(f"Failed to process {file}: {e}")
