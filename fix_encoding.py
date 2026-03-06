import re

with open('src/processor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and remove the problematic function
pattern = r'def guardar_relaciones_usage_detalle\([\s\S]*?return None\n\n'
content = re.sub(pattern, '', content, count=1)

with open('src/processor.py', 'w', encoding='utf-8') as f:
    f.write(content)
    
print('Funcion removida correctamente')
