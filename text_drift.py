#!/usr/bin/env python3
"""
v6.0 合规漂移引擎 — 公理合规修复版
===

【修复V1】禁止跨卦分类：概念目标卦象由 auto_concept_engine.py 的 RADICAL_WX + SEMANTIC_LOOKUP
          唯一确定，text_drift 只在卦内微调属性值，不可换卦。
【修复V2】SEMANTIC_LOOKUP 220条已有 auto_concept_engine.py 的 deduce() 函数提供推导链
          （部首→五行→阴阳→卦象），不在 text_drift.py 中重复。
【修复V3】争议标记：置信度<0.6 的概念标记 dispute_state='needs_review'，输出 human_review.json。
【修复V4】锚点只读：classify_state='anchor' 的概念不参与漂移。
【修复V5】公理基数：MICRO_BASE=0.01, MESO_BASE=0.10 已硬编码（v5.5已完成）。
【修复V6】生克耦合：shengke_bonus(anchor_wx, concept_wx) 替代 shengke_bonus(anchor_wx, anchor_wx)。

核心原则：
  概念必须先有哲学的锚（rule-derived trigram），再谈计算的漂（vector fine-tuning）。
  锚点卦象由规则确定 → text_drift 负责卦内属性微调 → 禁止跨卦分类。

分层说明：
  已定卦概念（radical/semantic/drift_corrected）：
    漂移方向 = 向本卦标准向量微调（不换卦）
    元态概念（meta）：
    追踪漂移但不强制定卦，输出到 human_review.json 交人工判定

完整漂移方程（每维度）：
  Δc = 0.01 × δ_adapt × y(C) × ∇Entropy(c)        [微观层·自扩散]
     + 0.10 × η × Σ(shengke_bonus × proximity × (anchor_vec - c))  [中观层·锚点引力]
     + 0     × (本卦标准向量 - c) × 卦内约束           [卦内微调]
"""

import json, math, sys, os, time
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
EPS = 1e-8
WINDOW = 8  # 锚点窗口半径

# ═══════════════════════════════════════════
# 公理基数（不可修改）[修复V5]
# ═══════════════════════════════════════════
MICRO_BASE = 0.01   # 微观层：熵梯度自扩散步长
MESO_BASE  = 0.10   # 中观层：生克场合力系数
MACRO_BASE = 1.0    # 宏观层：锚点引力权重（隐含）

# ═══════════════════════════════════════════
# 五行生克 [修复V6: 修正了生克计算调用]
# ═══════════════════════════════════════════
SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}
GUA_WX = {
    '乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木',
    '巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土'
}

def bare_wx(wx):
    """提取裸五行（去阴阳前缀）"""
    if not wx or wx in ('不定','?'): return None
    for b in ['金','木','水','火','土']:
        if b in wx: return b
    return None

def cos_sim(a, b):
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return sum(a[i]*b[i] for i in range(8))/(na*nb+EPS) if na*nb > EPS else 0

def shengke_bonus(wx_a, wx_b):
    """
    两五行间的生克加成系数 [修复V6]
    用法: shengke_bonus(anchor_wx, concept_wx)
    """
    ba, bb = bare_wx(wx_a), bare_wx(wx_b)
    if not ba or not bb: return 0.0      # 任一方五行不定 → 无加成
    if SHENG.get(ba) == bb: return 1.5   # A生B → 增强协同
    if SHENG.get(bb) == ba: return 1.3   # B生A → 增强协同
    if KE.get(ba) == bb: return 0.8      # A克B → 略减弱
    if KE.get(bb) == ba: return 0.8      # B克A → 略减弱
    if ba == bb: return 1.1              # 同五行 → 略增强
    return 1.0


def main():
    text_path = sys.argv[1] if len(sys.argv) > 1 else 'daodejing.txt'
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    with open(DICT_PATH, encoding='utf-8') as f:
        d = json.load(f)
    with open(text_path, encoding='utf-8') as f:
        text = f.read()
    chars = list(text.replace('\n','').replace('\r','').replace(' ',''))

    print(f'═══ v6.0 合规漂移引擎 ═══')
    print(f'文本: {text_path} | 轮次: {rounds}')
    print(f'公理基数: 微观={MICRO_BASE} 中观={MESO_BASE} 宏观={MACRO_BASE}')
    print(f'方程: Δc = {MICRO_BASE}×δ_adapt×y×∇E + {MESO_BASE}×η×ΣΦ（卦内约束）')
    print(f'修复: V1(禁止跨卦) V3(争议标记) V4(锚点只读) V5(基数) V6(生克)')

    # ═══════════════════════════════════════
    # 索引：三层概念分类
    # ═══════════════════════════════════════
    anchors = {}          # classify_state='anchor' → 只读不漂 [修复V4]
    classified = {}       # classify_state in (radical, semantic, drift_corrected) → 卦内微调
    meta_ids = set()      # 卦象='元' → 追踪漂移，不强制定卦 [修复V1+V6]
    all_chars = set()

    for ch, c in d['concepts'].items():
        all_chars.add(ch)
        cs = c.get('classify_state', '')
        if cs == 'anchor':
            anchors[ch] = c       # [修复V4] 锚点不参与漂移
        elif c['卦象'] == '元':
            meta_ids.add(ch)      # [修复V6] 元态→争议标记
        elif cs in ('radical', 'semantic', 'drift_corrected'):
            classified[ch] = c    # [修复V1] 已定卦→卦内微调
        elif cs == 'meta':
            meta_ids.add(ch)      # 兼容旧 classify_state='meta'

    print(f'锚点(只读): {len(anchors)} | 已定卦(卦内微调): {len(classified)} | 元态(争议): {len(meta_ids)}')

    # 概念位置索引
    char_positions = defaultdict(list)
    for i, ch in enumerate(chars):
        if ch in all_chars:
            char_positions[ch].append(i)

    # ═══════════════════════════════════════
    # 漂移对象：已定卦 + 元态（锚点排除）
    # ═══════════════════════════════════════
    driftable = {}  # {ch: concept_dict_entry}
    driftable.update({ch: d['concepts'][ch] for ch in classified})
    driftable.update({ch: d['concepts'][ch] for ch in meta_ids})
    # 锚点不进入 driftable [修复V4]

    # ═══════════════════════════════════════
    # 多轮漂移
    # ═══════════════════════════════════════
    for rnd in range(rounds):
        print(f'\n--- 第{rnd+1}轮 ---')
        interactions = 0

        for dr_ch, dc in driftable.items():
            positions = char_positions.get(dr_ch, [])
            if not positions: continue

            dc_vec = list(dc['属性'].values())
            y_val = dc.get('阴阳振幅', 0.5)
            classify_state = dc.get('classify_state', '')

            # 确定该概念的目标卦象（规则确定，不可换卦）[修复V1]
            if classify_state in ('radical', 'semantic', 'drift_corrected'):
                target_gua = dc['卦象']  # 规则确定的卦象，不可变
                target_vec = [d['trigrams'][target_gua][dim] for dim in DIMS]
            else:
                # 元态 → 无极原点 Φ₀ = (0,0,0,0,0,0,0,0)，仅作理论标记
                target_gua = None
                target_vec = [0.5]*8  # 中性，避免强制漂移方向

            # 汇总全部位置的锚点耦合（同卦优先）
            gua_coupling = defaultdict(float)

            for pos in positions:
                start = max(0, pos - WINDOW)
                end = min(len(chars), pos + WINDOW + 1)

                window_anchors = []
                for wi in range(start, end):
                    if wi == pos: continue
                    n = chars[wi]
                    if n in anchors:
                        dist = abs(wi - pos)
                        proximity = math.exp(-dist / WINDOW)
                        window_anchors.append((n, anchors[n], proximity))

                if not window_anchors: continue

                # 本位置最强锚点 [修复V6: shengke_bonus(anchor_wx, concept_wx)]
                best_coupling = 0.0
                best_gua = None
                for na, ac, prox in window_anchors:
                    gua = ac['卦象']
                    anchor_wx = ac['五行']
                    concept_wx = dc['五行'] if dc.get('五行', '不定') not in ('不定', '?') else GUA_WX.get(dc.get('卦象', ''), '不定')

                    # [修复V6] 修正：anchor_wx vs concept_wx，而非 anchor_wx vs anchor_wx
                    sk_bonus = shengke_bonus(anchor_wx, concept_wx)

                    # 交叉加成：该锚点与窗口内其他锚点的生克关系
                    cross_boost = 1.0
                    for nb, bc, prox_b in window_anchors:
                        if na == nb: continue
                        cross_boost *= (1.0 + 0.05 * shengke_bonus(anchor_wx, bc['五行']))
                    cross_boost = min(cross_boost, 1.5)

                    coupling = prox * sk_bonus * cross_boost
                    if coupling > best_coupling:
                        best_coupling = coupling
                        best_gua = gua

                if best_gua:
                    gua_coupling[best_gua] += best_coupling

            if not gua_coupling: continue

            # 本轮引力方向
            dominant_gua = max(gua_coupling, key=gua_coupling.get)
            dominant_vec = [d['trigrams'][dominant_gua][dim] for dim in DIMS]

            # ==== 完整漂移（卦内约束） ====  [修复V1]
            for dim_i in range(8):
                val = dc_vec[dim_i]

                # 微观层(0.01): 熵梯度自扩散
                sign = 1.0 if val > 0.5 else -1.0
                entropy_grad = -sign * (1.0 + math.log(abs(val - 0.5) + EPS))
                delta_adapt = max(abs(val - 0.5), 0.01)
                micro_drift = MICRO_BASE * delta_adapt * y_val * entropy_grad

                # 中观层(0.10): 锚点引力（向主导卦象方向）
                meso_drift_anchor = MESO_BASE * (dominant_vec[dim_i] - val)

                # [修复V1] 卦内约束：已定卦概念额外向本卦标准向量微调
                intra_gua_drift = 0.0
                if target_gua and classify_state in ('radical', 'semantic', 'drift_corrected'):
                    # 卦内微调：0.05系数（远小于中观层0.10，确保锚点引力为主）
                    intra_gua_drift = 0.05 * (target_vec[dim_i] - val)

                total_drift = micro_drift + meso_drift_anchor + intra_gua_drift
                dc_vec[dim_i] = round(max(0.0, min(1.0, val + total_drift)), 4)
                interactions += 1

            # 写回
            for dim_i, dim_name in enumerate(DIMS):
                dc['属性'][dim_name] = dc_vec[dim_i]

            dc['interaction_count'] = dc.get('interaction_count', 0) + 1
            dc['_dominant_gua'] = dominant_gua

            # 本概念本轮漂移量
            bl = list(dc.get('baseline_vector', {}).values())
            if len(bl) == 8:
                dc['drift_delta'] = round(math.sqrt(sum((dc_vec[i]-bl[i])**2 for i in range(8))), 4)

        print(f'  交互次数: {interactions}')

    # ═══════════════════════════════════════
    # 定型判定（禁止跨卦 + 争议标记） [修复V1+V3+V6]
    # ═══════════════════════════════════════
    print(f'\n═══ 定型判定（合规版） ═══')
    disputes = []  # [修复V3] 争议清单
    fine_tuned = 0  # 卦内微调完成
    unchanged = 0   # 无显著变化

    for dr_ch, dc in driftable.items():
        classify_state = dc.get('classify_state', '')
        cv = list(dc['属性'].values())
        bl = list(dc.get('baseline_vector', {}).values()) if dc.get('baseline_vector') else cv
        drift = math.sqrt(sum((cv[i]-bl[i])**2 for i in range(8)))
        dc['drift_delta'] = round(drift, 4)
        ic = dc.get('interaction_count', 0)

        if classify_state in ('radical', 'semantic', 'drift_corrected'):
            # [修复V1] 已定卦概念：卦内微调，不换卦
            # 计算与当前卦象标准向量的余弦相似度作为置信度
            current_gua = dc['卦象']
            gv = [d['trigrams'][current_gua][dim] for dim in DIMS]
            confidence = cos_sim(cv, gv)

            dc['auto_confidence'] = round(confidence, 3)

            if drift > 0.001:
                dc['drift_state'] = 'fine_tuned'
                fine_tuned += 1
            else:
                dc['drift_state'] = 'stable'
                unchanged += 1

            # [修复V3] 置信度 < 0.6 → 争议标记
            if confidence < 0.6:
                dc['dispute_state'] = 'needs_review'
                disputes.append({
                    'concept': dr_ch,
                    'assigned_gua': current_gua,
                    'confidence': round(confidence, 3),
                    'drift_delta': round(drift, 4),
                    'reason': f'卦内微调后与{current_gua}标准向量余弦相似度={confidence:.3f}<0.6',
                    'review_action': '请人工确认此概念的卦象归属是否正确'
                })

        elif dc['卦象'] == '元' or classify_state == 'meta':
            # [修复V6] 元态概念：不强制定卦，追踪漂移后标记争议
            if drift > 0.001:
                # 有漂移但不定卦——交由人工判定
                dc['dispute_state'] = 'needs_review'
                dc['drift_state'] = 'shifting_meta'

                # 找最接近的卦象（仅作参考，不写入卦象）
                best_gua = None
                best_sim = 0
                for gua, gvec in d['trigrams'].items():
                    gv = [gvec[dim] for dim in DIMS]
                    sim = cos_sim(cv, gv)
                    if sim > best_sim:
                        best_sim = sim
                        best_gua = gua

                disputes.append({
                    'concept': dr_ch,
                    'assigned_gua': '元',
                    'closest_gua': best_gua,
                    'closest_sim': round(best_sim, 3),
                    'drift_delta': round(drift, 4),
                    'reason': f'元态概念经过{ic}轮漂移，最接近{best_gua}(余弦={best_sim:.3f})，但无部首/语义查表依据',
                    'review_action': '请人工判定此概念的最终卦象归属'
                })
            else:
                dc['drift_state'] = 'stable_meta'
                dc['dispute_state'] = 'needs_review'  # 无漂移也标记——说明锚点不足，需人工判定
                # 无极原点 Φ₀ 标记 [修复V6]
                dc['_wuji_origin'] = True
                dc['auto_confidence'] = 0.0
                disputes.append({
                    'concept': dr_ch,
                    'assigned_gua': '元',
                    'closest_gua': '未知',
                    'closest_sim': 0.0,
                    'drift_delta': 0.0,
                    'reason': f'元态概念无锚点牵引，漂移量为0，无极原点Φ₀状态',
                    'review_action': '请人工判定此概念的最终卦象归属（当前无任何锚点参考）'
                })
                unchanged += 1

    print(f'  卦内微调: {fine_tuned} | 无变化: {unchanged}')
    print(f'  ⚠️ 争议标记: {len(disputes)} 条 → human_review.json')

    # ═══════════════════════════════════════
    # 导出争议清单 [修复V3]
    # ═══════════════════════════════════════
    review_path = os.path.join(SCRIPT_DIR, 'human_review.json')
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total_disputes': len(disputes),
            'disputes': disputes
        }, f, ensure_ascii=False, indent=2)
    print(f'  📋 争议清单已输出: {review_path}')

    # ═══════════════════════════════════════
    # 无极原点 Φ₀ 理论标记 [修复V6]
    # ═══════════════════════════════════════
    for meta_ch in meta_ids:
        mc = d['concepts'][meta_ch]
        if mc.get('卦象') == '元':
            mc['_wuji_origin'] = True  # 无极原点标记

    # 保存字典
    d['_drift_processed'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    d['_drift_version'] = 'v6.0'
    d['_drift_equation'] = f'Δc={MICRO_BASE}×δ_adapt×y×∇E+{MESO_BASE}×η×ΣΦ(卦内约束)'
    d['_drift_fixes'] = ['V1(禁止跨卦)','V3(争议标记)','V4(锚点只读)','V5(基数)','V6(生克)']
    d['_wuji_origin'] = '(0,0,0,0,0,0,0,0)'

    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    # 分布统计
    cc = Counter(v['卦象'] for v in d['concepts'].values())
    print(f'\n═══ 分布 ═══')
    for gua in ['乾☰','兑☱','离☲','震☳','巽☴','坎☵','艮☶','坤☷','元']:
        n = cc.get(gua, 0)
        bar = '█'*(n//10)
        print(f'  {gua} {n:4d} {bar}')
    print(f'  总计 {len(d["concepts"])}')

    # 争议概念数
    dispute_count = sum(1 for v in d['concepts'].values() if v.get('dispute_state') == 'needs_review')
    print(f'  ⚠️ 待人工审查: {dispute_count}')


def chapter_analysis(text_path, chapter_pattern=r'第[一二三四五六七八九十百千\d]+章', existing_dict=None):
    """
    Task 16: 章节分析功能
    按章节输入文本，输出逐章推演报告。

    用法：
        from text_drift import chapter_analysis
        report = chapter_analysis('daodejing.txt')

    道德经章节边界：以"第X章"为分隔标记。
    """
    import re

    # 加载字典
    if existing_dict is None:
        with open(DICT_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
    else:
        d = existing_dict

    # 读取全文
    with open(text_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 按章节切分
    chapters = re.split(f'({chapter_pattern})', text)
    # 重新组合为 (章号, 正文) 对
    parsed = []
    i = 0
    while i < len(chapters):
        header = chapters[i].strip()
        content = chapters[i+1].strip() if i+1 < len(chapters) else ''
        if header and (re.match(chapter_pattern, header) or header.startswith('第')):
            parsed.append((header, content))
            i += 2
        else:
            i += 1

    DIMS_LOCAL = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
    anchors_local = {ch: c for ch, c in d['concepts'].items() if c.get('classify_state') == 'anchor'}
    all_chars = set(d['concepts'].keys())

    report_lines = []
    report_lines.append(f'# 章节推演报告: {os.path.basename(text_path)}')
    report_lines.append(f'生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    report_lines.append(f'总章节: {len(parsed)}')
    report_lines.append('')

    chapter_stats = []

    for ch_title, ch_text in parsed:
        if not ch_text: continue

        chars = list(ch_text.replace('\n','').replace('\r','').replace(' ',''))
        concepts_found = [c for c in chars if c in all_chars]
        anchor_count = sum(1 for c in concepts_found if c in anchors_local)

        if not concepts_found: continue

        # 本章概念分布
        gua_counts = Counter()
        wx_counts = Counter()
        for c in concepts_found:
            concept = d['concepts'][c]
            gua_counts[concept['卦象']] += 1
            wx = concept.get('五行', '不定')
            for w in ['金','木','水','火','土']:
                if w in str(wx):
                    wx_counts[w] += 1
                    break

        # 生克关系密度
        sheng_count = 0
        ke_count = 0
        for i_c in range(len(concepts_found)):
            for j_c in range(i_c+1, len(concepts_found)):
                a_wx = d['concepts'][concepts_found[i_c]].get('五行', '')
                b_wx = d['concepts'][concepts_found[j_c]].get('五行', '')
                ba, bb = bare_wx(a_wx), bare_wx(b_wx)
                if not ba or not bb: continue
                if SHENG.get(ba) == bb or SHENG.get(bb) == ba:
                    sheng_count += 1
                if KE.get(ba) == bb or KE.get(bb) == ba:
                    ke_count += 1

        dominant_gua = gua_counts.most_common(1)[0] if gua_counts else ('无', 0)
        dominant_wx = wx_counts.most_common(1)[0] if wx_counts else ('无', 0)

        stats = {
            'chapter': ch_title,
            'total_chars': len(chars),
            'concepts': len(concepts_found),
            'anchors': anchor_count,
            'dominant_gua': f'{dominant_gua[0]}({dominant_gua[1]})',
            'dominant_wx': f'{dominant_wx[0]}({dominant_wx[1]})',
            'sheng_density': sheng_count,
            'ke_density': ke_count,
            'sheng_ke_ratio': round(sheng_count/max(ke_count,1), 2)
        }
        chapter_stats.append(stats)

        report_lines.append(f'## {ch_title}')
        report_lines.append(f'- 字符数: {stats["total_chars"]}')
        report_lines.append(f'- 概念数: {stats["concepts"]} (锚点: {stats["anchors"]})')
        report_lines.append(f'- 主导卦象: {stats["dominant_gua"]}')
        report_lines.append(f'- 主导五行: {stats["dominant_wx"]}')
        report_lines.append(f'- 生关系: {stats["sheng_density"]} | 克关系: {stats["ke_density"]} | 生克比: {stats["sheng_ke_ratio"]}')
        report_lines.append('')

    # 整体摘要
    report_lines.append('---')
    report_lines.append('## 整体摘要')
    all_guas = Counter()
    for s in chapter_stats:
        dom = s['dominant_gua'].split('(')[0]
        if dom and dom != '无':
            all_guas[dom] += 1
    report_lines.append(f'- 卦象主导分布: {dict(all_guas.most_common())}')
    total_sheng = sum(s['sheng_density'] for s in chapter_stats)
    total_ke = sum(s['ke_density'] for s in chapter_stats)
    report_lines.append(f'- 总生关系: {total_sheng} | 总克关系: {total_ke}')
    report_lines.append(f'- 全局生克比: {round(total_sheng/max(total_ke,1), 2)}')

    # 输出
    report_path = os.path.join(SCRIPT_DIR, 'chapter_analysis.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f'✅ 章节分析完成: {len(chapter_stats)}/{len(parsed)} 章 → {report_path}')
    return chapter_stats


if __name__ == '__main__':
    main()
