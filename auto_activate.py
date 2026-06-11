#!/usr/bin/env python3
"""
元态自动激活引擎 — 8卦引力场 + 激活通道 + 报告
用法: python auto_activate.py
"""
import json, math, os, sys, time
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
EPS = 1e-8

def norm(v): return math.sqrt(sum(x*x for x in v))
def cos_sim(a,b):
    return sum(a[i]*b[i] for i in range(8))/(norm(a)*norm(b)+EPS)

def main():
    with open(DICT_PATH, encoding='utf-8') as f:
        d = json.load(f)
    
    trigrams = d['trigrams']
    
    # 1. 扫描所有元态
    meta_cons = {ch: c for ch, c in d['concepts'].items() if c['卦象'] == '元'}
    print(f'═══ 元态自动激活 ═══')
    print(f'元态概念: {len(meta_cons)}')
    
    if not meta_cons:
        print('无元态，全部已定型')
        return
    
    # 2. 自动标记 needs_activation + 激活参数
    for ch, c in meta_cons.items():
        c['needs_activation'] = True
        c['activation_params'] = {
            'drift_coef': 2.0,
            'rounds': 20,
            'threshold': 0.003,
            'activated_at': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
    print(f'已标记 needs_activation: {len(meta_cons)}')
    
    # 3. 8卦引力场计算 — 对每个元态，基于其属性向量计算8卦引力
    print(f'\n═══ 8卦引力场分析 ═══')
    
    gravity_results = {}
    for ch, c in meta_cons.items():
        current_vec = list(c['属性'].values())
        baseline = list(c.get('baseline_vector', {}).values()) if c.get('baseline_vector') else current_vec
        
        # 漂移量
        drift = math.sqrt(sum((current_vec[i]-baseline[i])**2 for i in range(8)))
        ic = c.get('interaction_count', 0)
        
        # 计算8卦引力
        gravities = {}
        for gua, gvec in trigrams.items():
            gv = [gvec[dim] for dim in DIMS]
            sim = cos_sim(current_vec, gv)
            # 引力 = 相似度 × 交互密度 × 漂移权重
            grav = sim * (1.0 + math.log(ic+1)*0.1) * (1.0 + drift*10)
            gravities[gua] = round(grav, 4)
        
        # 排序
        ranked = sorted(gravities.items(), key=lambda x: -x[1])
        top_gua, top_grav = ranked[0]
        second_gua, second_grav = ranked[1]
        
        # 差距
        gap = top_grav - second_grav
        
        gravity_results[ch] = {
            'current_gua': '元',
            'drift_delta': drift,
            'interaction_count': ic,
            'gravities': dict(ranked[:4]),
            'top_gua': top_gua,
            'top_gravity': top_grav,
            'gap_to_second': gap,
        }
    
    # 4. 分类：定型成功 / 漂移中 / 需审查
    confirmed = []   # gap > 0.05 AND drift > 0.01
    drifting = []    # drift > 0.001 but not confirmed
    review = []      # gap < 0.02 or drift < 0.001
    
    for ch, gr in gravity_results.items():
        if gr['gap_to_second'] > 0.05 and gr['drift_delta'] > 0.01:
            confirmed.append((ch, gr))
        elif gr['drift_delta'] > 0.001:
            drifting.append((ch, gr))
        else:
            review.append((ch, gr))
    
    print(f'定型成功: {len(confirmed)} | 漂移中: {len(drifting)} | 需审查: {len(review)}')
    
    # 5. 定型成功 → 写入卦象
    reclassed = 0
    for ch, gr in confirmed:
        c = d['concepts'][ch]
        new_gua = gr['top_gua']
        c['卦象'] = new_gua
        c['五行'] = {
            '乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木',
            '巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土'
        }[new_gua]
        # 属性设为该卦标准向量
        gv = trigrams[new_gua]
        c['属性'] = {dim: round(gv[dim], 4) for dim in DIMS}
        c['classify_state'] = 'drift_corrected'
        c['auto_confidence'] = round(gr['top_gravity'], 2)
        c['drift_state'] = 'shifted'
        c.pop('needs_activation', None)
        c.pop('activation_params', None)
        
        # 更新生克
        bare = {'金':'金','木':'木','水':'水','火':'火','土':'土'}.get(
            {'乾☰':'金','兑☱':'金','离☲':'火','震☳':'木','巽☴':'木','坎☵':'水','艮☶':'土','坤☷':'土'}[new_gua]
        )
        SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
        KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}
        c['我生'] = SHENG.get(bare, '?')
        c['我克'] = KE.get(bare, '?')
        c['生我'] = [k for k,v in SHENG.items() if v==bare]
        c['克我'] = [k for k,v in KE.items() if v==bare]
        reclassed += 1
    
    # 6. 保存
    d['_last_activation'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    
    # 7. 激活报告
    report_lines = []
    report_lines.append(f'# 元态激活报告\n')
    report_lines.append(f'生成时间: {d["_last_activation"]}')
    report_lines.append(f'总元态: {len(meta_cons)}')
    report_lines.append(f'定型成功: {len(confirmed)} | 漂移中: {len(drifting)} | 需审查: {len(review)}')
    report_lines.append('')
    
    if confirmed:
        report_lines.append('## 定型成功')
    for ch, gr in confirmed:
        c = d['concepts'][ch]
        g_name = c['卦象']
        dd = gr['drift_delta']
        gap = gr['gap_to_second']
        ic = gr['interaction_count']
        report_lines.append(f'- {ch}: 元→{g_name} Δ={dd:.4f} 引力差={gap:.3f} ic={ic}')
    
    if drifting:
        report_lines.append('')
        report_lines.append('## 漂移中（数据不够，等更多文本）')
    for ch, gr in drifting[:20]:
        dd = gr['drift_delta']
        tg = gr['top_gua']
        tgv = gr['top_gravity']
        gap = gr['gap_to_second']
        ic = gr['interaction_count']
        report_lines.append(f'- {ch}: Δ={dd:.4f} →{tg}({tgv:.3f}) gap={gap:.3f} ic={ic}')
        if len(drifting) > 20:
            report_lines.append(f'- ... 还有 {len(drifting)-20} 个')
    
    if review:
        report_lines.append('')
        report_lines.append('## 需审查（漂移方向不稳定或交互不足）')
    for ch, gr in review[:15]:
        dd = gr['drift_delta']
        ic = gr['interaction_count']
        report_lines.append(f'- {ch}: Δ={dd:.4f} ic={ic}')
        if len(review) > 15:
            report_lines.append(f'- ... 还有 {len(review)-15} 个')
    
    # 分布统计
    report_lines.append('')
    report_lines.append('## 分布变化')
    gc = {}
    for vv in d['concepts'].values():
        gua = vv['卦象']
        gc[gua] = gc.get(gua, 0) + 1
    for gua in ['乾☰','兑☱','离☲','震☳','巽☴','坎☵','艮☶','坤☷','元']:
        n = gc.get(gua, 0)
        bar = '█' * (n // 10)
        report_lines.append(f'  {gua} {n:4d} {bar}')
    report_lines.append(f'  总计 {len(d["concepts"])}')
    
    report_path = os.path.join(SCRIPT_DIR, 'activation_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    # 打印摘要
    from collections import Counter
    cc = Counter(v['卦象'] for v in d['concepts'].values())
    print(f'\n═══ 最终分布 ═══')
    for gua in ['乾☰','兑☱','离☲','震☳','巽☴','坎☵','艮☶','坤☷','元']:
        n = cc.get(gua, 0)
        bar = '█'*(n//10)
        print(f'  {gua:4s} {n:4d} {bar}')
    total = len(d['concepts'])
    print(f'  总计 {total}')
    print(f'\n报告: activation_report.md')
    
    return reclassed

if __name__ == '__main__':
    main()
