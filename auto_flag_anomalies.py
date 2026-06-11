#!/usr/bin/env python3
"""
太极概念引擎 · 异常标记脚本 v1.0
扫描字典，标记三类异常: [待审查] / [矛盾] / [多义]

用法：
    python auto_flag_anomalies.py                                  # 扫描 concept_dict.json
    python auto_flag_anomalies.py new_concepts.json                # 扫描指定文件
    python auto_flag_anomalies.py --threshold 0.5                  # 自定义置信度阈值
"""

import json, os, sys, math, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
VALID_GUA = set('乾☰兑☱离☲震☳巽☴坎☵艮☶坤☷')

GUA_WX = {'乾☰':'金','兑☱':'金','离☲':'火','震☳':'木','巽☴':'木','坎☵':'水','艮☶':'土','坤☷':'土'}
WX_GUA = {'金':{'乾☰','兑☱'},'木':{'震☳','巽☴'},'水':{'坎☵'},'火':{'离☲'},'土':{'艮☶','坤☷'}}

SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}

def bare_wx(wx):
    wx = str(wx).split('(')[0]
    for e in ['阳金','阴金','阳木','阴木','阳土','阴土','阳水','阴水']:
        if wx in e or e in wx: return e.replace('阳','').replace('阴','')
    for e in ['金','木','水','火','土']:
        if e in wx: return e
    return wx

def flag_anomalies(dict_path, threshold=0.6):
    with open(dict_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    concepts = data.get('concepts', data)
    
    anomalies = []
    
    for ch, c in concepts.items():
        gua = c.get('卦象','')
        wx = c.get('五行','')
        attr = c.get('属性',{})
        confidence = c.get('auto_confidence', 1.0)
        
        # 1. [待审查] — 卦象匹配度低
        if confidence < threshold and c.get('auto_classified'):
            anomalies.append({
                '字': ch, '标记': '[待审查]', '卦象': gua,
                '原因': f'自动定型置信度{confidence:.0%} < 阈值{threshold:.0%}',
                '建议': f'人工判定{ch}的八卦属性'
            })
        
        # 2. [待审查] — 部首无法映射 (已通过auto_classified+低置信度覆盖)
        
        # 3. [待审查] — 生克与同类不一致
        bare = bare_wx(wx)
        
        # 4. [矛盾] — 卦象与五行冲突
        expected_wx = GUA_WX.get(gua, '?')
        if expected_wx != '?' and expected_wx != bare:
            anomalies.append({
                '字': ch, '标记': '[矛盾]', '卦象': gua, '五行': wx,
                '原因': f'卦象{gua}应属{expected_wx}，但五行标注为{bare}',
                '建议': f'修正五行属性或卦象'
            })
        
    # 5. [矛盾] — 生克不对称 (采样检测)
    if '我生' in c and c['我生']:
        sheng_val = c['我生']
        expected = SHENG.get(bare)
        if expected and sheng_val != expected and bare and bare != '不定':
            anomalies.append({
                '字': ch, '标记': '[矛盾]',
                '原因': f'我生={sheng_val}，五行{bare}的标准我生应为{expected}',
                '建议': f'修正我生字段为{expected}'
            })
        
        # 6. [矛盾] — 属性越界
        for dim, val in attr.items():
            if val is not None and (val < 0 or val > 1):
                anomalies.append({
                    '字': ch, '标记': '[矛盾]',
                    '原因': f'{dim}={val}越界(应为0-1)',
                    '建议': f'修正{dim}值到[0,1]范围'
                })
        
        # 7. [多义] — 语境多义概念
        if 'context_variants' in c:
            variants = [v['卦象'] for v in c['context_variants']]
            anomalies.append({
                '字': ch, '标记': '[多义]', '卦象': gua,
                '原因': f'语境变体: {variants}',
                '建议': '当前主键保持，不同语境路由到不同变体'
            })
    
    out = {'异常条目': anomalies, 'total_anomalies': len(anomalies), '字典路径': dict_path, '阈值': threshold}
    
    out_path = os.path.join(SCRIPT_DIR, 'anomalies.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    
    # Task 18: 串联异常到漂移追踪日志
    append_to_drift_log(anomalies)
    
    print(f'═══ 异常标记报告 ═══')
    print(f'异常条目: {len(anomalies)}')
    for t in ['[矛盾]','[待审查]','[多义]']:
        count = len([a for a in anomalies if a['标记']==t])
        if count: print(f'  {t}: {count}')
    print(f'\n📋 输出: anomalies.json')
    
    return anomalies


def append_to_drift_log(anomalies):
    """Task 18: 将异常数据同步写入漂移追踪日志 drift_tracking.md"""
    if not anomalies: return

    drift_path = os.path.join(SCRIPT_DIR, 'drift_tracking.md')

    entry = f'\n### 异常标记 {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
    entry += f'- 异常总数: {len(anomalies)}\n'
    for tag in ['[矛盾]', '[待审查]', '[多义]']:
        count = len([a for a in anomalies if a.get('标记') == tag])
        if count:
            entry += f'  - {tag}: {count}\n'
    entry += '\n'

    with open(drift_path, 'a', encoding='utf-8') as f:
        f.write(entry)

    print(f'  🔗 串联日志: {len(anomalies)} 条异常 → drift_tracking.md')


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('--') else DEFAULT_DICT
    th = 0.6
    if '--threshold' in sys.argv:
        ti = sys.argv.index('--threshold')
        th = float(sys.argv[ti+1])
    flag_anomalies(path, th)
