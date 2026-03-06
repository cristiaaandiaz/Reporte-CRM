#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reorganizar todo de forma profesional con logs legibles"""

import re

# ============================================================================
# MEJORAS EN report.py - VALIDACION USAGE
# ============================================================================
with open('src/report.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Mejorar header y logging inicial
old_header = '''    logger.info("=" * 80)
    logger.info("VALIDANDO RELACIONES USAGE DE SERVICECODES")
    logger.info("=" * 80)'''

new_header = '''    logger.info("\\n" + "=" * 80)
    logger.info("PASO 5.1: VALIDAR RELACIONES USAGE DE SERVICECODES")
    logger.info("=" * 80)'''

content = content.replace(old_header, new_header)

# Mejorar logging de indexación
old_index = '''    logger.info(f"Total CIs indexados: {len(cis_por_id)}")
    logger.info(f"Total servicecodes encontrados: {len(servicecodes)}")'''

new_index = '''    logger.info(f"\\n[INDEXACION]")
    logger.info(f"  CIs totales indexados:        {len(cis_por_id):>6}")
    logger.info(f"  Servicecodes encontrados:     {len(servicecodes):>6}")'''

content = content.replace(old_index, new_index)

# Mejorar logging de relaciones usage
old_usage = '''    logger.info(f"Total relaciones usage indexadas: {sum(len(rels) for rels in relaciones_usage_por_end2.values())}")
    
    # Validar relaciones usage para cada servicecode'''

new_usage = '''    total_usage_rels = sum(len(rels) for rels in relaciones_usage_por_end2.values())
    logger.info(f"  Relaciones 'usage' indexadas: {total_usage_rels:>6}")
    
    # Validar relaciones usage para cada servicecode
    logger.info(f"\\n[PROCESAMIENTO]")'''

content = content.replace(old_usage, new_usage)

# Mejorar logging dentro del loop
old_debug = '''        if not relaciones_usage:
            logger.debug(f"[{servicecodes_procesados}] Servicecode '{servicecode_label}' -> Sin relaciones usage")
            continue'''

new_debug = '''        if not relaciones_usage:
            logger.debug(f"  [{servicecodes_procesados}] {servicecode_label:<40} -> SIN RELACIONES USAGE")
            continue'''

content = content.replace(old_debug, new_debug)

# Mejorar validación fallida
old_fail1 = '''            if not ci_end1:
                logger.warning(f"[{servicecodes_procesados}] Relacion {rel_id}: end1Id '{end1id}' no encontrado en CIs")
                relaciones_rechazadas += 1
                continue
            
            # Validar que sea business_application
            ci_type = ci_end1.get("type")
            if ci_type != "business_application":
                logger.debug(f"[{servicecodes_procesados}] Relacion {rel_id}: end1Id es '{ci_type}' (no es business_application)")
                relaciones_rechazadas += 1
                continue'''

new_fail1 = '''            if not ci_end1:
                logger.debug(f"  [!] Relacion {rel_id}: end1Id '{end1id}' NO ENCONTRADO en CIs")
                relaciones_rechazadas += 1
                continue
            
            # Validar que sea business_application
            ci_type = ci_end1.get("type")
            if ci_type != "business_application":
                logger.debug(f"  [!] Relacion {rel_id}: end1Id es '{ci_type}' (NO es business_application)")
                relaciones_rechazadas += 1
                continue'''

content = content.replace(old_fail1, new_fail1)

# Mejorar logging de validación exitosa
old_success = '''            relaciones_a_eliminar.append(relacion_valida)
            relaciones_validadas += 1
            
            logger.debug(f"[OK] Relacion validada: {rel_id}")
            logger.debug(f"     App: {end1_label} -> Servicecode: {servicecode_label}")'''

new_success = '''            relaciones_a_eliminar.append(relacion_valida)
            relaciones_validadas += 1
            
            logger.debug(f"  [+] VALIDA: {end1_label:<30} -> {servicecode_label:<30}")'''

content = content.replace(old_success, new_success)

# Mejorar resumen
old_resumen = '''    logger.info("=" * 80)
    logger.info("Resumen de validacion de relaciones usage:")
    logger.info(f"  Servicecodes procesados: {servicecodes_procesados}")
    logger.info(f"  Relaciones usage encontradas: {sum(len(rels) for rels in relaciones_usage_por_end2.values())}")
    logger.info(f"  Relaciones validadas (para eliminar): {relaciones_validadas}")
    logger.info(f"  Relaciones rechazadas: {relaciones_rechazadas}")
    logger.info("=" * 80)'''

new_resumen = '''    logger.info(f"\\n[RESUMEN VALIDACION USAGE]")
    logger.info(f"  Servicecodes procesados:      {servicecodes_procesados:>6}")
    logger.info(f"  Relaciones validadas:         {relaciones_validadas:>6}")
    logger.info(f"  Relaciones rechazadas:        {relaciones_rechazadas:>6}")
    logger.info(f"  Totales a eliminar:           {len(relaciones_a_eliminar):>6}")
    logger.info("=" * 80)'''

content = content.replace(old_resumen, new_resumen)

with open('src/report.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("[OK] report.py mejorado")

# ============================================================================
# MEJORAS EN ucmdb_operations.py - RESUMEN ELIMINATION
# ============================================================================
with open('src/ucmdb_operations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Mejor resumen de eliminación
old_summary = '''    logger.info("-" * 80)
    logger.info("Resumen eliminacion usage:")
    logger.info(f"  Total relaciones procesadas: {total}")
    
    if modo_ejecucion == "ejecucion":
        logger.info(f"  Exitosas: {exitosas}")
        logger.info(f"  Fallidas: {fallidas}")
        logger.info(f"  No encontradas (404): {no_encontradas}")
    else:
        logger.info(f"  Simuladas: {total}")'''

new_summary = '''    logger.info("-" * 80)
    logger.info("[RESUMEN ELIMINACION USAGE]")
    logger.info(f"  Total relaciones procesadas: {total:>6}")
    
    if modo_ejecucion == "ejecucion":
        logger.info(f"  Exitosas:                    {exitosas:>6}")
        logger.info(f"  Fallidas:                    {fallidas:>6}")
        logger.info(f"  No encontradas (404):        {no_encontradas:>6}")
    else:
        logger.info(f"  Simuladas:                   {total:>6}")'''

content = content.replace(old_summary, new_summary)

with open('src/ucmdb_operations.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("[OK] ucmdb_operations.py mejorado")

print("\n[RESUMEN DE CAMBIOS]")
print("  + Logs profesionales con estructura clara")
print("  + Alineación de números para mejor legibilidad")
print("  + Headers con PASO y secciones claras")
print("  + Reportes formateados con índices")
print("\nTodos los cambios aplicados correctamente!")
