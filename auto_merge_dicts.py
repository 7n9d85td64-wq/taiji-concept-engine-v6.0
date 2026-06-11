#!/usr/bin/env python3
"""
太极概念引擎 · 字典合并脚本 v1.0
多批推演结果合并→去重→备份→校验→入库

用法：
    python auto_merge_dicts.py new_concepts.json                          # 合并到默认字典
    python auto_merge_dicts.py new.json --base concept_dict.json           # 指定基础字典
    python auto_merge_dicts.py new.json --skip-validate                    # 跳过校验
"""

import json, os, sys, shutil, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DICT = os.path.join(SCRIPT_DIR, 'concept_dict.json')

def merge(new_path, base_path=BASE_DICT, skip_validate=False):
    # 1. 加载
    with open(new_path, 'r', encoding='utf-8') as f:
        new_data = json.load(f)
    with open(base_path, 'r', encoding='utf-8') as f:
        base_data = json.load(f)
    
    new_concepts = new_data.get('concepts', new_data)
    base_concepts = base_data.get('concepts', {})
    
    # 2. 备份
    ts = time.strftime('%Y%m%d_%H%M%S')
    backup_path = base_path.replace('.json', f'_backup_{ts}.json')
    shutil.copy2(base_path, backup_path)
    
    # 3. 合并统计
    added = 0
    replaced = 0
    kept_old = 0
    skipped_conflict = 0
    
    for ch, entry in new_concepts.items():
        if ch not in base_concepts:
            base_concepts[ch] = entry
            added += 1
        else:
            # 新条目有异常标记 → 保留旧版
            if entry.get('auto_confidence', 1.0) < 0.5:
                kept_old += 1
                continue
            # 无异常 → 以新代旧
            base_concepts[ch] = entry
            replaced += 1
    
    # 4. 更新总数
    base_data['concepts'] = base_concepts
    base_data['total_concepts'] = len(base_concepts)
    base_data['updated'] = ts
    
    # 增量版本号
    old_name = base_data.get('dict_name', '')
    if 'v' in old_name:
        parts = old_name.split('v')
        if len(parts) > 1:
            try:
                ver = float(parts[-1].split()[0])
                base_data['dict_name'] = parts[0] + f'v{ver+0.1:.1f}'
            except:
                base_data['dict_name'] = old_name + ' (merged)'
    
    # 5. 校验
    if not skip_validate:
        # 临时写入校验
        tmp_path = base_path.replace('.json', '_tmp.json')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2)
        
        from auto_validate_concepts import validate
        passed = validate(tmp_path)
        os.remove(tmp_path)
        
        if not passed:
            print('❌ 校验未通过，不写入基础字典。请修正异常后重试。')
            print(f'📦 备份: {backup_path}')
            return False
    
    # 6. 写入
    with open(base_path, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, ensure_ascii=False, indent=2)
    
    # 7. 合并报告
    report = []
    report.append(f'## 合并报告 ({time.strftime("%Y-%m-%d %H:%M")})')
    report.append(f'')
    report.append(f'| 项目 | 数量 |')
    report.append(f'|------|------|')
    report.append(f'| 新增 | {added} |')
    report.append(f'| 替换(以新代旧) | {replaced} |')
    report.append(f'| 保留旧版(新条目置信度过低) | {kept_old} |')
    report.append(f'| 合并后总计 | {len(base_concepts)} |')
    report.append(f'')
    report.append(f'📦 备份: {os.path.basename(backup_path)}')
    report.append(f'📋 字典: {os.path.basename(base_path)}')
    
    report_path = os.path.join(SCRIPT_DIR, 'merge_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print('\n'.join(report))
    print(f'\n📋 报告: merge_report.md')
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python auto_merge_dicts.py new_concepts.json [--base dict.json] [--skip-validate]')
        sys.exit(1)
    
    new_path = sys.argv[1]
    base_path = BASE_DICT
    
    if '--base' in sys.argv:
        bi = sys.argv.index('--base')
        base_path = sys.argv[bi+1]
    
    skip = '--skip-validate' in sys.argv
    
    merge(new_path, base_path, skip)
