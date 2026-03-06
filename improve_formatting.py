#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para mejorar logs y reportes"""

import re

# Mejorar report.py
with open('src/report.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar logging en validar_relaciones_usage_de_servicecodes
old_section = '''    logger.info("Resumen de validacion de relaciones usage:")
    logger.info(f"  Servicecodes procesados: {servicecodes_procesados}")
    logger.info(f"  Relaciones usage encontradas: {sum(len(rels) for rels in relaciones_usage_por_end2.values())}")
    logger.info(f"  Relaciones validadas (para eliminar): {relaciones_validadas}")
    logger.info(f"  Relaciones rechazadas: {relaciones_rechazadas}")'''

new_section = '''    logger.info("[RESUMEN VALIDACION USAGE]")
    logger.info(f"  Servicecodes procesados:      {servicecodes_procesados:>6}")
    logger.info(f"  Relaciones validadas:         {relaciones_validadas:>6}")
    logger.info(f"  Relaciones rechazadas:        {relaciones_rechazadas:>6}")
    logger.info(f"  Totales a eliminar:           {len(relaciones_a_eliminar):>6}")'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open('src/report.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("[OK] report.py actualizado")

# Mejorar ucmdb_operations.py
with open('src/ucmdb_operations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Actualizar headers de eliminación
old_header = 'logger.info("=" * 80)\n    logger.info("PASO 6B: ELIMINAR RELACIONES USAGE DE SERVICECODES EN UCMDB")\n    logger.info("=" * 80)'
new_header = 'logger.info("\\n" + "=" * 80)\n    logger.info("PASO 6B: ELIMINAR RELACIONES USAGE DE SERVICECODES EN UCMDB")\n    logger.info("=" * 80)'

if old_header in content:
    content = content.replace(old_header, new_header)
    with open('src/ucmdb_operations.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("[OK] ucmdb_operations.py actualizado")

print("Mejoras aplicadas correctamente")
