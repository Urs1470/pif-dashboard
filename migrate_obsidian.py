#!/usr/bin/env python3
"""
Migration script for Obsidian vault to PIF Dashboard database.
Parses Markdown files with YAML frontmatter and imports them into SQLite.
"""

import os
import re
import sys
import yaml
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_db


def slug_from_filename(filename):
    """Generate project ID from filename."""
    name = os.path.splitext(filename)[0]
    name = name.replace(' ', '_')
    name = re.sub(r'[^\w\-]', '', name)
    return name


def parse_frontmatter(content):
    """Extract YAML frontmatter from markdown content."""
    if content.startswith('---'):
        parts = content[3:].split('---', 1)
        if len(parts) == 2:
            try:
                return yaml.safe_load(parts[0]) or {}, parts[1]
            except:
                return {}, parts[1]
    return {}, content


def extract_section(content, section_name):
    """Extract a section from markdown content."""
    pattern = rf'(?:^|\n)#+\s*{re.escape(section_name)}.*?(?=\n#|\n##|\Z)'
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(0) if match else ''


def parse_checklist(content):
    """Parse checklist items from markdown."""
    items = []
    pattern = r'- \[([ xX])\]\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, content)
    for i, (checked, title) in enumerate(matches):
        items.append({
            'completed': 1 if checked.lower() == 'x' else 0,
            'title': title.strip(),
            'ordine': i
        })
    return items


def parse_tasks(content):
    """Parse task list items from markdown."""
    tasks = []
    priority_map = {
        '⏫': 'urgent',
        '🔺': 'urgent',
        '🔼': 'normal',
        '⬇️': 'minor',
        '⏬': 'minor'
    }
    
    todo_section = extract_section(content, 'TODO') or extract_section(content, 'LISTA TASK')
    
    pattern = r'- \[([ xX])\]\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, todo_section or content)
    
    for checked, title in matches:
        title = title.strip()
        priority = 'normal'
        for emoji, prio in priority_map.items():
            if emoji in title:
                priority = prio
                break
        
        date_match = re.search(r'📅\s*(\d{4}-\d{2}-\d{2})', title)
        due_date = date_match.group(1) if date_match else ''
        
        clean_title = re.sub(r'[\U00010000-\U0010ffff]', '', title).strip()
        
        status = 'done' if checked.lower() == 'x' else 'to_do'
        
        tasks.append({
            'titlu': clean_title,
            'status': status,
            'prioritate': priority,
            'data_scadenta': due_date,
            'data_finalizare': datetime.now().isoformat() if status == 'done' else ''
        })
    
    return tasks


def parse_jurnal(content):
    """Parse journal entries from markdown."""
    entries = []
    
    jurnal_section = extract_section(content, 'JURNAL DE LUCRU')
    if not jurnal_section:
        return entries
    
    pattern = r'(?:\*{0,2})(\d{4}-\d{2}-\d{2})(?:\*{0,2})\s*:?\s*(.*?)(?=(?:\*{0,2})\d{4}-\d{2}-\d{2}(?:\*{0,2})\s*:|\Z)'
    matches = re.findall(pattern, jurnal_section, re.DOTALL)
    
    for date, content_text in matches:
        content_text = content_text.strip()
        if content_text:
            entries.append({
                'data': date,
                'continut': content_text.replace('\n', ' ').strip()
            })
    
    return entries


def map_producator(echipament):
    """Map equipment name to manufacturer."""
    if not echipament:
        return 'Altul'
    
    echipament_lower = echipament.lower()
    
    if 'abb' in echipament_lower or 'acs' in echipament_lower:
        return 'ABB'
    if 'siemens' in echipament_lower or 'g120' in echipament_lower or 's120' in echipament_lower:
        return 'Siemens'
    if 'danfoss' in echipament_lower or 'vlt' in echipament_lower or 'fc30' in echipament_lower:
        return 'Danfoss'
    
    return 'Altul'


def map_status(status):
    """Map vault status to dashboard status."""
    if not status:
        return 'in_lucru'
    
    status_lower = status.lower()
    if 'finalizat' in status_lower or 'done' in status_lower:
        return 'finalizat'
    if 'blocat' in status_lower or 'blocked' in status_lower:
        return 'blocat'
    
    return 'in_lucru'


def determine_tip(tags, filename):
    """Determine project type from tags and filename."""
    if not tags:
        return 'PIF'
    
    tags_lower = [t.lower() for t in tags]
    
    if 'service' in tags_lower or 'interventie' in tags_lower:
        return 'Service'
    
    return 'PIF'


def parse_admin_section(content):
    """Parse administrative details section."""
    details = {}
    
    admin_section = extract_section(content, '1. Detalii Administrative')
    if not admin_section:
        return details
    
    pm_match = re.search(r'\*\*PM:\*\*\s*(.+?)(?:\n|$)', admin_section)
    if pm_match:
        details['pm'] = pm_match.group(1).strip()
    
    folder_match = re.search(r'\*\*Folder Server[^:]*:\*\*\s*[`\"]?(.+?)[`\"]?(?:\n|$)', admin_section)
    if folder_match:
        details['folder_server'] = folder_match.group(1).strip().strip('`"')
    
    cod_match = re.search(r'\*\*Cod proiect:\*\*\s*(.+?)(?:\n|$)', admin_section)
    if cod_match:
        details['cod_proiect'] = cod_match.group(1).strip()
    
    return details


def parse_service_sections(content):
    """Parse service before/after sections."""
    result = {
        'service_before': '',
        'service_after': ''
    }
    
    problema_section = extract_section(content, '1. Problema') or extract_section(content, 'Problema')
    constatari_section = extract_section(content, '2. Constatări') or extract_section(content, 'Constatari')
    
    before_parts = []
    if problema_section:
        clean = re.sub(r'^#.*$', '', problema_section, flags=re.MULTILINE).strip()
        before_parts.append(clean)
    if constatari_section:
        clean = re.sub(r'^#.*$', '', constatari_section, flags=re.MULTILINE).strip()
        before_parts.append(clean)
    
    result['service_before'] = '\n'.join(before_parts).strip()
    
    actiuni_section = extract_section(content, '3. Acțiuni Corective') or extract_section(content, 'Actiuni')
    rezultat_section = extract_section(content, '4. Rezultat') or extract_section(content, 'Rezultat')
    
    after_parts = []
    if actiuni_section:
        clean = re.sub(r'^#.*$', '', actiuni_section, flags=re.MULTILINE).strip()
        after_parts.append(clean)
    if rezultat_section:
        clean = re.sub(r'^#.*$', '', rezultat_section, flags=re.MULTILINE).strip()
        after_parts.append(clean)
    
    result['service_after'] = '\n'.join(after_parts).strip()
    
    return result


def process_file(filepath, existing_ids):
    """Process a single markdown file and return project data."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    filename = os.path.basename(filepath)
    frontmatter, body = parse_frontmatter(content)
    
    project_id = slug_from_filename(filename)
    
    if project_id in existing_ids:
        return None, 'skipped', 'Already exists'
    
    tags = frontmatter.get('tags', []) or []
    tip = determine_tip(tags, filename)
    
    nume_match = re.search(r'^#\s*(?:PIF|Service):\s*(.+)$', body, re.MULTILINE)
    nume = nume_match.group(1).strip() if nume_match else filename.replace('.md', '')
    
    echipament = frontmatter.get('echipament_principal', '')
    
    project_data = {
        'id': project_id,
        'tip': tip,
        'nume': nume,
        'client': frontmatter.get('client', ''),
        'locatie': frontmatter.get('locatie', ''),
        'echipament_principal': echipament,
        'producator': map_producator(echipament),
        'cod_proiect': frontmatter.get('cod_proiect', ''),
        'pm': frontmatter.get('pm', ''),
        'folder_server': frontmatter.get('folder_server', ''),
        'data_incepere': frontmatter.get('data_incepere', ''),
        'deadline': frontmatter.get('deadline', ''),
        'data_crearii': frontmatter.get('data_crearii', ''),
        'status': map_status(frontmatter.get('status', '')),
        'observatii': '',
        'nr_comanda': '',
        'nr_contract': '',
        'service_before': '',
        'service_after': '',
        'confirmat_client': 0,
        'client_nume_confirmare': ''
    }
    
    admin = parse_admin_section(body)
    project_data.update(admin)
    
    if tip == 'Service':
        service = parse_service_sections(body)
        project_data['service_before'] = service['service_before']
        project_data['service_after'] = service['service_after']
    
    checklist = []
    if tip == 'PIF':
        checklist_section = extract_section(body, 'PRE-PIF CHECKLIST') or extract_section(body, '3. PRE-PIF')
        if checklist_section:
            checklist = parse_checklist(checklist_section)
    
    tasks = parse_tasks(body)
    jurnal = parse_jurnal(body)
    
    return {
        'project': project_data,
        'checklist': checklist,
        'tasks': tasks,
        'jurnal': jurnal
    }, 'ok', ''


def import_to_database(data):
    """Import parsed data into database."""
    import uuid
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    p = data['project']
    
    cursor.execute('''
        INSERT INTO proiecte (
            id, tip, nume, client, locatie, echipament_principal, producator,
            cod_proiect, pm, folder_server, data_incepere, deadline, data_crearii,
            status, observatii, nr_comanda, nr_contract, service_before, service_after,
            confirmat_client, client_nume_confirmare, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        p['id'], p['tip'], p['nume'], p['client'], p['locatie'], p['echipament_principal'],
        p['producator'], p['cod_proiect'], p['pm'], p['folder_server'], p['data_incepere'],
        p['deadline'], p['data_crearii'], p['status'], p['observatii'], p['nr_comanda'],
        p['nr_contract'], p.get('service_before', ''), p.get('service_after', ''),
        p['confirmat_client'], p['client_nume_confirmare'], now, now
    ))
    
    for i, item in enumerate(data.get('checklist', [])):
        item_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO checklist_pif (id, proiect_id, titlu, completed, ordine)
            VALUES (?, ?, ?, ?, ?)
        ''', (item_id, p['id'], item['title'], item['completed'], i))
    
    for i, task in enumerate(data.get('tasks', [])):
        task_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta, data_finalizare, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, p['id'], task['titlu'], task['status'], task['prioritate'],
              task.get('data_scadenta', ''), task.get('data_finalizare', ''), now))
    
    for i, entry in enumerate(data.get('jurnal', [])):
        entry_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (entry_id, p['id'], entry['data'], entry['continut'], now))
    
    conn.commit()
    conn.close()


def migrate_vault(vault_path):
    """Migrate all markdown files from vault path."""
    if not os.path.exists(vault_path):
        print(f"Error: Vault path does not exist: {vault_path}")
        return
    
    init_db()
    
    # Get existing project IDs
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM proiecte')
    existing_ids = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    files_processed = 0
    projects_imported = 0
    tasks_imported = 0
    errors = []
    skipped = []
    
    md_files = []
    for root, dirs, files in os.walk(vault_path):
        for f in files:
            if f.endswith('.md') and not f.startswith('.'):
                md_files.append(os.path.join(root, f))
    
    print(f"Found {len(md_files)} markdown files")
    
    for filepath in md_files:
        files_processed += 1
        try:
            data, status, message = process_file(filepath, existing_ids)
            
            if status == 'skipped':
                skipped.append((filepath, message))
                continue
            
            if status == 'ok' and data:
                import_to_database(data)
                existing_ids.add(data['project']['id'])
                projects_imported += 1
                tasks_imported += len(data.get('tasks', []))
                print(f"Imported: {os.path.basename(filepath)}")
        
        except Exception as e:
            errors.append((filepath, str(e)))
            print(f"Error processing {filepath}: {e}")
    
    return {
        'files_processed': files_processed,
        'projects_imported': projects_imported,
        'tasks_imported': tasks_imported,
        'skipped': skipped,
        'errors': errors
    }


def main():
    parser = argparse.ArgumentParser(description='Migrate Obsidian vault to PIF Dashboard')
    parser.add_argument('--vault', '-v', required=True, help='Path to Obsidian vault')
    args = parser.parse_args()
    
    print(f"Migrating from: {args.vault}")
    
    result = migrate_vault(args.vault)
    
    print("\n" + "=" * 50)
    print("MIGRATION SUMMARY")
    print("=" * 50)
    print(f"Files processed: {result['files_processed']}")
    print(f"Projects imported: {result['projects_imported']}")
    print(f"Tasks imported: {result['tasks_imported']}")
    print(f"Skipped (already exist): {len(result['skipped'])}")
    print(f"Errors: {len(result['errors'])}")
    
    if result['errors']:
        print("\nErrors:")
        for filepath, error in result['errors']:
            print(f"  - {os.path.basename(filepath)}: {error}")


if __name__ == '__main__':
    main()
