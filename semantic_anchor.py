#!/usr/bin/env python3
"""
v5.4 动态三层权重引擎 — 生克场耦合 + 锚点池进化 + 公式计权

三层架构（根基论框架）:
- 宏观层(权重w_m): 锚点概念 — 一次定义，持续验证
- 中观层(权重w_s): 共现耦合 + 生克场 — 每次文本交互生效
- 微观层(权重w_i): 漂移演化 — 需要锚点存在才有效（当前未启用）

权重公式（每轮动态计算）:
  w_m = anchor_count / total_concepts   (锚点占比)
  w_s = meso_classified / total_metas   (中观定型率)  
  w_i = 1 - w_m - w_s                   (剩余给微观)
  有效权重 = w / Σw (归一化)
"""

import json, math, sys, os, time
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
WINDOW = 8

# 五行生克基础
SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}
SHENG_BY = {v:k for k,v in SHENG.items()}  # {水:金, 火:木, ...}
KE_BY   = {v:k for k,v in KE.items()}      # {木:金, 土:木, ...}

GUA_WX = {
    '乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木',
    '巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土'
}

def bare_wx(wx):
    """抽出五行本元"""
    if not wx or wx in ('不定','?'): return None
    for b in ['金','木','水','火','土']:
        if b in wx: return b
    return wx

def shengke_bonus(wx_a, wx_b):
    """计算两个五行之间的关系加成
    返回: (bonus_a, bonus_b) 各自的加成系数
    """
    ba = bare_wx(wx_a)
    bb = bare_wx(wx_b)
    if not ba or not bb: return (0, 0)
    
    # 生: A生B → A得到+0.15(被需要), B得到+0.10(受益)
    if SHENG.get(ba) == bb:
        return (0.15, 0.10)
    # 被生: B生A → A得到+0.10, B得到+0.15
    if SHENG.get(bb) == ba:
        return (0.10, 0.15)
    # 克: A克B → A得到+0.12(主导), B得到-0.05(被压制)
    if KE.get(ba) == bb:
        return (0.12, -0.05)
    # 被克: B克A → A得到-0.05, B得到+0.12
    if KE.get(bb) == ba:
        return (-0.05, 0.12)
    # 同五行: 轻微加成
    if ba == bb:
        return (0.05, 0.05)
    return (0, 0)

def process_text(d, text_path, expand_anchors=True):
    """处理单个文本，返回统计数据"""
    
    with open(text_path, encoding='utf-8') as f:
        text = f.read()
    chars = list(text.replace('\n','').replace('\r','').replace(' ',''))
    
    # 索引
    anchors = {}
    meta_ids = set()
    all_chars = set()
    for ch, c in d['concepts'].items():
        all_chars.add(ch)
        if c.get('classify_state') == 'anchor':
            anchors[ch] = c
        elif c['卦象'] == '元':
            meta_ids.add(ch)
    
    char_positions = defaultdict(list)
    for i, ch in enumerate(chars):
        if ch in all_chars:
            char_positions[ch].append(i)
    
    print(f'  锚点: {len(anchors)} | 元态: {len(meta_ids)}')
    
    # ==== 生克场耦合计算 ====
    classified = 0
    no_anchor = 0
    classified_by_gua = Counter()
    classified_details = []
    
    for meta_ch in meta_ids:
        positions = char_positions.get(meta_ch, [])
        if not positions:
            no_anchor += 1
            continue
        
        # 按卦象累积耦合（含生克场）
        gua_coupling = defaultdict(float)
        
        for pos in positions:
            start = max(0, pos - WINDOW)
            end = min(len(chars), pos + WINDOW + 1)
            
            # 收集窗口内所有锚点及其信息
            window_anchors = []
            for wi in range(start, end):
                if wi == pos: continue
                n = chars[wi]
                if n in anchors:
                    dist = abs(wi - pos)
                    proximity = math.exp(-dist * dist / (2 * WINDOW * WINDOW))
                    window_anchors.append((n, anchors[n]['卦象'], anchors[n]['五行'], proximity))
            
            if not window_anchors:
                continue
            
            # 基础耦合 + 生克场加成
            for i, (na, gua_a, wx_a, prox_a) in enumerate(window_anchors):
                base_couple = prox_a
                shengke_boost = 0.0
                
                # 与窗口内其他锚点的生克交互
                for j, (nb, gua_b, wx_b, prox_b) in enumerate(window_anchors):
                    if i >= j: continue
                    bonus_a, bonus_b = shengke_bonus(wx_a, wx_b)
                    # 生克加成按双方邻近度加权
                    avg_prox = (prox_a + prox_b) / 2
                    shengke_boost += bonus_a * avg_prox
                
                # 总耦合 = 邻近度 + 生克场
                total_couple = base_couple * (1.0 + shengke_boost)
                gua_coupling[gua_a] += total_couple
        
        if not gua_coupling:
            no_anchor += 1
            continue
        
        # 最强卦象
        strongest_gua = max(gua_coupling, key=gua_coupling.get)
        strongest_strength = gua_coupling[strongest_gua]
        total = sum(gua_coupling.values())
        confidence = strongest_strength / total
        
        # 直接定卦
        mc = d['concepts'][meta_ch]
        coupling_dist = {g: round(v, 2) for g, v in sorted(gua_coupling.items(), key=lambda x: -x[1])[:3]}
        
        mc['卦象'] = strongest_gua
        mc['五行'] = GUA_WX[strongest_gua]
        mc['classify_state'] = 'drift_corrected'
        mc['auto_confidence'] = round(confidence, 2)
        mc['anchor_coupling'] = coupling_dist
        mc['drift_state'] = 'shifted'
        
        # 生克
        b = bare_wx(GUA_WX[strongest_gua])
        mc['我生'] = SHENG.get(b, '?')
        mc['我克'] = KE.get(b, '?')
        mc['生我'] = [k for k,v in SHENG.items() if v==b]
        mc['克我'] = [k for k,v in KE.items() if v==b]
        
        classified += 1
        classified_by_gua[strongest_gua] += 1
        classified_details.append((meta_ch, strongest_gua, confidence))
    
    # ==== 锚点池扩展 ====
    new_anchors = 0
    if expand_anchors:
        for meta_ch, strongest_gua, confidence in classified_details:
            if confidence > 0.55:  # 高置信阈值
                mc = d['concepts'][meta_ch]
                mc['classify_state'] = 'anchor'
                mc['_promoted_from'] = 'drift_corrected'
                mc['_promoted_at'] = text_path
                new_anchors += 1
    
    return {
        'text': text_path,
        'classified': classified,
        'no_anchor': no_anchor,
        'new_anchors': new_anchors,
        'by_gua': dict(classified_by_gua),
        'details': classified_details
    }

def calculate_weights(d):
    """公式计算三层有效权重"""
    total = len(d['concepts'])
    anchor_count = sum(1 for c in d['concepts'].values() if c.get('classify_state') == 'anchor')
    dc_count = sum(1 for c in d['concepts'].values() if c.get('classify_state') == 'drift_corrected')
    meta_count = sum(1 for c in d['concepts'].values() if c['卦象'] == '元')
    
    w_macro = anchor_count / total
    w_meso = dc_count / total
    w_micro = 1 - w_macro - w_meso  # 剩余
    
    # 归一化（排除微观，当前等于0）
    norm = w_macro + w_meso + w_micro
    if norm > 0:
        w_macro /= norm
        w_meso /= norm
        w_micro /= norm
    
    return {
        'macro': round(w_macro, 4),
        'meso': round(w_meso, 4),
        'micro': round(w_micro, 4),
        'anchor_count': anchor_count,
        'dc_count': dc_count,
        'meta_count': meta_count,
        'total': total
    }

def main():
    # 读取文本列表
    if len(sys.argv) > 1:
        text_files = sys.argv[1:]
    else:
        text_files = ['daodejing.txt', 'lunyu.txt']
    
    with open(DICT_PATH, encoding='utf-8') as f:
        d = json.load(f)
    
    print(f'═══ v5.4 动态三层权重引擎 ═══')
    print(f'文本: {text_files}')
    
    # 初始权重
    w0 = calculate_weights(d)
    print(f'\n初始权重: 宏观={w0["macro"]} 中观={w0["meso"]} 微观={w0["micro"]}')
    print(f'锚点:{w0["anchor_count"]}  drift_corrected:{w0["dc_count"]}  元:{w0["meta_count"]}')
    
    all_results = []
    for i, tf in enumerate(text_files):
        print(f'\n--- {tf} ---')
        result = process_text(d, tf, expand_anchors=True)  # 每轮都扩展锚点
        all_results.append(result)
        
        cc = Counter(v['卦象'] for v in d['concepts'].values())
        print(f'  定型: {result["classified"]} | 无锚点: {result["no_anchor"]} | 新锚点: {result["new_anchors"]}')
        
        # 本轮后权重
        w = calculate_weights(d)
        print(f'  权重: 宏观={w["macro"]} 中观={w["meso"]} 微观={w["micro"]}')
    
    # 最终权重
    wf = calculate_weights(d)
    
    # 保存
    d['_engine'] = 'v5.4_dynamic_weights'
    d['_processed_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    d['_weights'] = {
        'initial': f"宏观={w0['macro']} 中观={w0['meso']} 微观={w0['micro']}",
        'final': f"宏观={wf['macro']} 中观={wf['meso']} 微观={wf['micro']}",
        'anchor_evolution': f"{w0['anchor_count']}→{wf['anchor_count']} (+{wf['anchor_count']-w0['anchor_count']})"
    }
    
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    
    # ==== 最终分布 ====
    cc = Counter(v['卦象'] for v in d['concepts'].values())
    print(f'\n═══ 最终分布 ═══')
    for gua in ['乾☰','兑☱','离☲','震☳','巽☴','坎☵','艮☶','坤☷','元']:
        n = cc.get(gua, 0)
        bar = '█'*(n//10)
        print(f'  {gua} {n:4d} {bar}')
    print(f'  总计 {len(d["concepts"])}')
    
    print(f'\n═══ 三层最终权重 ═══')
    print(f'  宏观(锚点定义)    : {wf["macro"]:.4f}  ({wf["anchor_count"]}概念)')
    print(f'  中观(生克耦合)    : {wf["meso"]:.4f}  ({wf["dc_count"]}概念)')
    print(f'  微观(漂移演化)    : {wf["micro"]:.4f}  ({wf["meta_count"]}概念待定)')
    print(f'  归一化            : {wf["macro"]+wf["meso"]+wf["micro"]:.4f}')

if __name__ == '__main__':
    main()
