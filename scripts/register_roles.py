#!/usr/bin/env python3
"""批量注册.md角色文件到registry"""

import json
import re
import os
from pathlib import Path
from datetime import datetime

REGISTRY_PATH = '/home/rayliu/.openclaw/skills/sindris/scripts/roles_registry.json'
ROLES_DIR = Path('/home/rayliu/.openclaw/skills/sindris/roles')

def extract_frontmatter(content):
    """从markdown提取YAML frontmatter"""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            import yaml
            return yaml.safe_load(match.group(1))
        except:
            pass
    return {}

def infer_category(path):
    """从路径推断category"""
    parts = str(path).split(os.sep)
    if 'engineering' in parts:
        return 'engineering'
    elif 'testing' in parts:
        return 'testing'
    elif 'ai-factory' in parts:
        return 'product'
    elif 'strategy' in parts:
        return 'strategy'
    elif 'specialized' in parts:
        return 'specialized'
    return 'general'

def generate_registry_entry(md_path, fm):
    """从文件生成registry条目"""
    stem = md_path.stem
    if stem.startswith('sindri-'):
        stem = stem[7:]
    
    role_id = stem.replace('-', '_')
    category = infer_category(md_path)
    
    # 从frontmatter提取信息
    name = fm.get('name', fm.get('role', stem.replace('-', ' ').title()))
    emoji = fm.get('emoji', fm.get('icon', '📋'))
    description = fm.get('description', f'{name} - {category} role')
    vibe = fm.get('vibe', 'Professional agent')
    trigger = fm.get('trigger', fm.get('trigger_keywords', []))
    if isinstance(trigger, str):
        trigger = [trigger]
    
    return {
        "id": role_id,
        "name": name,
        "category": category,
        "description": description,
        "emoji": emoji,
        "vibe": vibe,
        "trigger_keywords": trigger if trigger else [role_id.replace('_', ' ')]
    }

def main():
    # 加载registry
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)
    
    registered_ids = {r['id'] for r in registry['roles']}
    
    # 扫描所有.md文件
    all_md_files = list(ROLES_DIR.rglob('*.md'))
    
    new_entries = []
    for md in all_md_files:
        stem = md.stem
        if stem.startswith('sindri-'):
            stem = stem[7:]
        role_id = stem.replace('-', '_')
        
        if role_id in registered_ids:
            continue
        
        # 读取文件
        with open(md) as f:
            content = f.read()
        
        fm = extract_frontmatter(content)
        entry = generate_registry_entry(md, fm)
        new_entries.append(entry)
        print(f"生成: {entry['id']} ({entry['category']})")
    
    print(f"\n共 {len(new_entries)} 个新角色")
    
    # 添加到registry
    registry['roles'].extend(new_entries)
    registry['total'] = len(registry['roles'])
    registry['updated_at'] = datetime.now().isoformat()
    
    # 保存
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    
    print(f"已更新 registry，共 {registry['total']} 个角色")

if __name__ == '__main__':
    main()