#!/usr/bin/env python3
"""
太极概念引擎 · 自动校验脚本 v1.0
扫描概念字典，检查规范性、对称性、合法性、完整性、重复性

用法：
    python auto_validate_concepts.py                         # 校验 concept_dict.json
    python auto_validate_concepts.py new_concepts.json       # 校验指定文件
    python auto_validate_concepts.py --incremental           # 只校验新增条目(需 --base)
"""

import json, os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
VALID_GUA_NAMES = {'乾','兑','离','震','巽','坎','艮','坤'}

SHENG_STANDARD = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE_STANDARD   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}

def bare_wx(wx):
    wx = str(wx).split('(')[0]
    for e in ['阳金','阴金','阳木','阴木','阳土','阴土']:
        if wx in e or e in wx:
            return e.replace('阳','').replace('阴','')
    if '金' in wx: return '金'
    if '木' in wx: return '木'
    if '水' in wx: return '水'
    if '火' in wx: return '火'
    if '土' in wx: return '土'
    return wx

def validate(dict_path, incremental=False, base_dict=None):
    with open(dict_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    concepts = data.get('concepts', data)  # 兼容两种格式
    if isinstance(concepts, list): concepts = {c.get('name',c.get('字','?')):c for c in concepts}
    
    errors = {'format':[], 'symmetry':[], 'legality':[], 'completeness':[], 'duplicates':[]}
    total = len(concepts)
    
    # 1. 格式规范性
    for ch, c in concepts.items():
        # 必填字段
        for field in ['卦象','五行','属性']:
            if field not in c:
                errors['format'].append(f'{ch}: 缺少必填字段 {field}')
                continue
        
        gua = c.get('卦象','')
        if gua[:1] not in VALID_GUA_NAMES if gua else True:
            errors['format'].append(f'{ch}: 卦象 {gua} 不在8个标准卦象中')
        
        attr = c.get('属性',{})
        if len(attr) != 8:
            errors['format'].append(f'{ch}: 属性维度={len(attr)}，应为8')
        else:
            for dim, val in attr.items():
                if val is None or val < 0 or val > 1:
                    errors['format'].append(f'{ch}.{dim}={val} 越界(应为0-1)')
    
    # 2. 生克对称性
    for ch, c in concepts.items():
        if '我生' not in c or '我克' not in c: continue
        wx = bare_wx(c.get('五行',''))
        sheng_val = c.get('我生','')
        ke_val = c.get('我克','')
        
        # 检查：A我生=B五行 → B生列表中应包含A五行
        for other_ch, other in concepts.items():
            if other_ch == ch: continue
            owx = bare_wx(other.get('五行',''))
            if sheng_val and sheng_val == owx:
                shengwo = [bare_wx(s) for s in other.get('生我',[])]
                if wx not in shengwo:
                    errors['symmetry'].append(f'{ch}({wx})→生{other_ch}({owx})，但{other_ch}.生我不含{wx}')
        
            if ke_val and ke_val == owx:
                kewo = [bare_wx(k) for k in other.get('克我',[])]
                if wx not in kewo:
                    errors['symmetry'].append(f'{ch}({wx})→克{other_ch}({owx})，但{other_ch}.克我不含{wx}')
    
    # 3. 生克合法性 [修复V8: 跳过五行=不定的概念，避免假阳性]
    for ch, c in concepts.items():
        wx = bare_wx(c.get('五行',''))
        if not wx or wx == '不定':
            continue  # Task 20: 元态概念五行不定，跳过生克校验
        if '我生' in c and c['我生']:
            sheng_val = c['我生']
            expected = SHENG_STANDARD.get(wx)
            if expected and sheng_val != '?' and sheng_val != expected:
                errors['legality'].append(f'{ch}: 我生={sheng_val}，标准应为{expected}')
        if '我克' in c and c['我克']:
            ke_val = c['我克']
            expected = KE_STANDARD.get(wx)
            if expected and ke_val != '?' and ke_val != expected:
                errors['legality'].append(f'{ch}: 我克={ke_val}，标准应为{expected}')
    
    # 4. 属性完整性
    for ch, c in concepts.items():
        attr = c.get('属性',{})
        if len(attr) != 8:
            errors['completeness'].append(f'{ch}: 属性{len(attr)}维≠8')
        else:
            for dim in DIMS:
                if dim not in attr:
                    errors['completeness'].append(f'{ch}: 缺少{dim}')
    
    # 5. 重复条目
    seen = {}
    for ch in concepts:
        if ch in seen:
            errors['duplicates'].append(f'{ch}: 重复条目 (首次在第{seen[ch]}位)')
        else:
            seen[ch] = len(seen)+1
    
    # 生成报告
    report = []
    report.append(f'## 校验报告 ({time.strftime("%Y-%m-%d %H:%M")})')
    report.append(f'')
    report.append(f'字典: {os.path.basename(dict_path)}')
    report.append(f'总条目: {total}')
    report.append(f'')
    
    all_pass = True
    for name, label in [('format','格式规范性'),('symmetry','生克对称性'),('legality','生克合法性'),('completeness','属性完整性'),('duplicates','重复条目')]:
        e = errors[name]
        if e:
            all_pass = False
            report.append(f'### {label}')
            report.append(f'❌ 失败: {len(e)} 条')
            for item in e[:10]:
                report.append(f'  - {item}')
            if len(e) > 10: report.append(f'  - ...还有 {len(e)-10} 条')
        else:
            report.append(f'### {label}')
            report.append(f'✅ 通过')
        report.append(f'')
    
    if all_pass:
        report.append('✅ 全部校验通过')

    # Task 15: 串联争议工作流——将校验异常发送到 human_review.json
    if not all_pass:
        send_to_review(errors)

    report_path = os.path.join(SCRIPT_DIR, 'validate_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print('\n'.join(report))
    print(f'\n📋 报告: validate_report.md')
    return all_pass


def send_to_review(errors):
    """Task 15: 将校验异常串联到争议工作流 human_review.json"""
    review_path = os.path.join(SCRIPT_DIR, 'human_review.json')

    # 加载已有争议清单（如果存在）
    existing = []
    if os.path.exists(review_path):
        with open(review_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing = data.get('disputes', [])

    # 将校验异常转为争议条目
    new_disputes = []
    for category, items in errors.items():
        if not items: continue
        for item in items[:20]:  # 每种最多20条，避免过多
            new_disputes.append({
                'concept': item.split(':')[0] if ':' in item else item,
                'source': f'validate_{category}',
                'reason': item,
                'review_action': f'校验发现{category}问题，请人工审查'
            })

    if not new_disputes:
        return

    # 合并写入
    all_disputes = existing + new_disputes
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'auto_validate_concepts.py',
            'total_disputes': len(all_disputes),
            'new_from_validate': len(new_disputes),
            'disputes': all_disputes
        }, f, ensure_ascii=False, indent=2)

    print(f'  🔗 串联争议: {len(new_disputes)} 条校验异常 → human_review.json')

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('--') else DEFAULT_DICT
    incremental = '--incremental' in sys.argv
    validate(path, incremental)
