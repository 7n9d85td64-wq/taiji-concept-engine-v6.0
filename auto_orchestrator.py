#!/usr/bin/env python3
"""
太极概念引擎 · 调度中枢 v1.0
===
定义完整协议调度链，串联太极协议5函数 + 权舆协议3函数。

数据流：
  anomalies.json → 盘古(找对立) → 共工(否定测试) → 名家(崩塌预警) → 兵家(势能) → 烛龙(元认知总结)

触发时机：每次 text_drift.py 运行完成后自动调用。
audit_log 格式：JSONL，每行 {timestamp, event_type, details, severity}

用法：
    python auto_orchestrator.py                          # 全链路运行
    python auto_orchestrator.py --step pangu             # 单步运行
    python auto_orchestrator.py --from anomalies.json    # 从指定异常文件启动
"""

import json, os, sys, time, math
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
VALID_STEPS = ['pangu', 'gonggong', 'mingjia', 'bingjia', 'zhulong']
ε = 1e-8

# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════
SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}

def cos_sim(a, b):
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return sum(a[i]*b[i] for i in range(8))/(na*nb+ε) if na*nb > ε else 0

def bare_wx(wx):
    if not wx or wx in ('不定','?'): return None
    for b in ['金','木','水','火','土']:
        if b in wx: return b
    return wx

# ═══════════════════════════════════════════
# audit_log 基础设施
# ═══════════════════════════════════════════
AUDIT_LOG_PATH = os.path.join(SCRIPT_DIR, 'audit_log.jsonl')

def audit_log(event_type, details, severity='info'):
    """写入一条审计日志（JSONL格式）"""
    entry = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'event_type': event_type,
        'details': details,
        'severity': severity  # info | warning | critical
    }
    with open(AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


# ═══════════════════════════════════════════
# M1: 盘古 · 矛盾制造
# ═══════════════════════════════════════════
def taiji_pangu(concept_dict):
    """
    扫描所有概念对，计算属性互补度。
    互补度 < 0.2 且存在生克关系的，标记为"强对立"。

    Returns:
        List[ConflictPair]: {a, b, complementarity, relation, severity}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    if not isinstance(concepts, dict): return []

    pairs = []
    concept_list = list(concepts.items())

    for i in range(len(concept_list)):
        for j in range(i + 1, len(concept_list)):
            a_ch, a_ct = concept_list[i]
            b_ch, b_ct = concept_list[j]

            # 计算属性互补度
            a_vec = list(a_ct.get('属性', {}).values())
            b_vec = list(b_ct.get('属性', {}).values())
            if len(a_vec) != 8 or len(b_vec) != 8: continue

            comp = 1.0 - cos_sim(a_vec, b_vec)  # 互补度（越大越对立）

            # 检查生克关系
            a_wx = bare_wx(a_ct.get('五行', ''))
            b_wx = bare_wx(b_ct.get('五行', ''))

            relation = None
            severity = 'low'
            if a_wx and b_wx:
                if KE.get(a_wx) == b_wx:
                    relation = 'a_ke_b'  # A克B
                    severity = 'high'
                elif KE.get(b_wx) == a_wx:
                    relation = 'b_ke_a'  # B克A
                    severity = 'high'
                elif SHENG.get(a_wx) == b_wx:
                    relation = 'a_sheng_b'
                    severity = 'medium'
                elif SHENG.get(b_wx) == a_wx:
                    relation = 'b_sheng_a'
                    severity = 'medium'
                elif a_wx == b_wx:
                    relation = 'tong_wx'
                    severity = 'low'

            # 判定：互补度 > 0.8（即 cos_sim < 0.2）且有生克关系 → 强对立
            if comp > 0.8 and relation and severity in ('high', 'medium'):
                pairs.append({
                    'a': a_ch, 'b': b_ch,
                    'complementarity': round(comp, 3),
                    'relation': relation,
                    'severity': severity
                })

    # 按互补度降序排序
    pairs.sort(key=lambda x: -x['complementarity'])

    audit_log('pangu_complete', {
        'total_pairs_scanned': len(concept_list) * (len(concept_list) - 1) // 2,
        'conflict_pairs_found': len(pairs),
        'top_conflict': f"{pairs[0]['a']}↔{pairs[0]['b']}({pairs[0]['complementarity']})" if pairs else 'none'
    }, severity='info')

    return pairs


# ═══════════════════════════════════════════
# M2: 共工 · 前提撞击
# ═══════════════════════════════════════════
def taiji_gonggong(concept_dict, hypothesis):
    """
    对给定假设进行否定测试，计算否定后的属性漂移方向。

    Args:
        hypothesis: {concept: str, relation: str, target: str}
            例: {'concept': '道', 'relation': 'sheng', 'target': '德'}

    Returns:
        NegationReport: {hypothesis, negated_impact, drift_direction, risk_level}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    ch = hypothesis.get('concept', '')
    target = hypothesis.get('target', '')
    if ch not in concepts or target not in concepts:
        return {'error': 'concept not found', 'hypothesis': hypothesis}

    c_vec = list(concepts[ch]['属性'].values())
    t_vec = list(concepts[target]['属性'].values())

    # 原始耦合度
    original_coupling = cos_sim(c_vec, t_vec)

    # 否定测试：反转假设方向
    negated_vec = [1.0 - v for v in c_vec]
    negated_coupling = cos_sim(negated_vec, t_vec)

    # 漂移方向
    drift = math.sqrt(sum((negated_vec[i] - c_vec[i])**2 for i in range(8)))

    risk_level = 'high' if negated_coupling < 0.0 else ('medium' if negated_coupling < 0.3 else 'low')

    report = {
        'hypothesis': hypothesis,
        'original_coupling': round(original_coupling, 3),
        'negated_coupling': round(negated_coupling, 3),
        'drift_magnitude': round(drift, 4),
        'risk_level': risk_level,
        'conclusion': f'否定后耦合度从{original_coupling:.2f}→{negated_coupling:.2f}，风险{risk_level}'
    }

    audit_log('gonggong_test', {
        'hypothesis': f"{ch}→{target}",
        'original': round(original_coupling, 3),
        'negated': round(negated_coupling, 3),
        'risk': risk_level
    }, severity=risk_level if risk_level == 'high' else 'info')

    return report


# ═══════════════════════════════════════════
# M3: 名家 · 概念崩塌追踪
# ═══════════════════════════════════════════
def taiji_mingjia(concept_dict, concept_name):
    """
    追踪概念的δ漂移量，判定是否触发崩塌警告。

    触发条件：
      - cos(c_n, c_0) < 0.3（漂移过大，失去原始语义）
      - Entropy >= 0.7（属性分布熵过高，语义消散）

    Returns:
        CollapseWarning: {concept, drift_cos, entropy, warning, level}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    if concept_name not in concepts:
        return {'error': f'concept {concept_name} not found'}

    c = concepts[concept_name]
    cv = list(c['属性'].values())
    bl = list(c.get('baseline_vector', {}).values()) if c.get('baseline_vector') else cv

    # cos(c_n, c_0) —— 当前向量与基线的余弦相似度
    drift_cos = cos_sim(cv, bl)

    # Entropy —— 属性分布熵
    p_vals = [max(v, ε) for v in cv]
    p_sum = sum(p_vals)
    p_norm = [v / p_sum for v in p_vals]
    entropy = -sum(p * math.log2(p) if p > 0 else 0 for p in p_norm)

    warning = False
    reasons = []
    if drift_cos < 0.3:
        warning = True
        reasons.append(f'drift_cos={drift_cos:.3f}<0.3(语义漂失)')
    if entropy >= 0.7:
        warning = True
        reasons.append(f'entropy={entropy:.3f}>=0.7(属性消散)')

    level = 'critical' if len(reasons) >= 2 else ('warning' if warning else 'stable')

    result = {
        'concept': concept_name,
        'drift_cos': round(drift_cos, 4),
        'entropy': round(entropy, 4),
        'warning': warning,
        'reasons': reasons,
        'level': level
    }

    if warning:
        audit_log('mingjia_collapse_warning', {
            'concept': concept_name,
            'drift_cos': round(drift_cos, 4),
            'entropy': round(entropy, 4),
            'reasons': reasons
        }, severity='warning' if level == 'warning' else 'critical')

    return result


# ═══════════════════════════════════════════
# M4: 兵家 · 势能推演
# ═══════════════════════════════════════════
def taiji_bingjia(concept_dict, option_a, option_b, steps=5):
    """
    为两个对立选项推演N步生克流转，计算势能曲线。

    V(t) = ||Φ_t(A)||² - ||Φ_t(B)||²

    Returns:
        MomentumCurve: {option_a, option_b, steps, curve, winner, confidence}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    if option_a not in concepts or option_b not in concepts:
        return {'error': 'option not found'}

    a_vec = list(concepts[option_a]['属性'].values())
    b_vec = list(concepts[option_b]['属性'].values())
    a_wx = bare_wx(concepts[option_a].get('五行', ''))
    b_wx = bare_wx(concepts[option_b].get('五行', ''))

    curve = []
    a_state = a_vec[:]
    b_state = b_vec[:]

    for t in range(steps):
        # A的演化：受生克关系推动
        if a_wx and b_wx:
            if KE.get(a_wx) == b_wx:
                # A克B → A增强
                a_state = [min(1.0, v + 0.05) for v in a_state]
                b_state = [max(0.0, v - 0.03) for v in b_state]
            elif KE.get(b_wx) == a_wx:
                # B克A → A减弱
                a_state = [max(0.0, v - 0.05) for v in a_state]
                b_state = [min(1.0, v + 0.03) for v in b_state]

        # 势能计算
        v_a = sum(v**2 for v in a_state)
        v_b = sum(v**2 for v in b_state)
        curve.append(round(v_a - v_b, 4))

    final_v = curve[-1]
    winner = option_a if final_v > 0 else option_b
    confidence = min(abs(final_v) / 2.0, 0.95)

    result = {
        'option_a': option_a,
        'option_b': option_b,
        'steps': steps,
        'curve': curve,
        'winner': winner,
        'confidence': round(confidence, 3),
        'trend': 'ascending' if curve[-1] > curve[0] else 'descending'
    }

    audit_log('bingjia_momentum', {
        'contest': f"{option_a}vs{option_b}",
        'winner': winner,
        'confidence': round(confidence, 3),
        'curve': curve
    }, severity='info')

    return result


# ═══════════════════════════════════════════
# M5: 烛龙 · 元认知反思
# ═══════════════════════════════════════════
def taiji_zhulong(audit_log_path=AUDIT_LOG_PATH):
    """
    定期审视审计日志，检测重复错误模式，输出反思报告。

    Returns:
        ReflectionReport: {patterns, recommendations, summary}
    """
    if not os.path.exists(audit_log_path):
        return {'error': 'audit_log.jsonl not found'}

    logs = []
    with open(audit_log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not logs:
        return {'summary': 'no audit logs found', 'patterns': [], 'recommendations': []}

    # 统计事件类型
    event_counts = defaultdict(int)
    severity_counts = defaultdict(int)
    recent_warnings = []

    for log_entry in logs:
        event_counts[log_entry.get('event_type', 'unknown')] += 1
        severity_counts[log_entry.get('severity', 'info')] += 1
        if log_entry.get('severity') in ('warning', 'critical'):
            recent_warnings.append(log_entry)

    # 检测重复模式
    patterns = []
    for event_type, count in event_counts.items():
        if count >= 3:
            patterns.append({
                'pattern': f'重复{event_type}（{count}次）',
                'count': count,
                'suggestion': f'建议检查{event_type}相关逻辑是否存在系统性偏差'
            })

    # 生成建议
    recommendations = []
    if severity_counts.get('critical', 0) > 0:
        recommendations.append(f"⚠️ 存在{severity_counts['critical']}条严重事件，需立即处理")
    if len(recent_warnings) > 10:
        recommendations.append(f"⚠️ 近期警告较多({len(recent_warnings)}条)，建议暂停漂移进行人工审查")
    if not patterns:
        recommendations.append('✅ 未检测到重复错误模式')

    report = {
        'analyzed_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'total_events': len(logs),
        'event_distribution': dict(event_counts),
        'severity_distribution': dict(severity_counts),
        'patterns': patterns,
        'recommendations': recommendations,
        'summary': f"共分析{len(logs)}条日志，发现{len(patterns)}个重复模式，{len(recent_warnings)}条近期警告"
    }

    audit_log('zhulong_reflection', {
        'total_events': len(logs),
        'patterns_found': len(patterns),
        'warnings': len(recent_warnings)
    }, severity='info')

    return report


# ═══════════════════════════════════════════
# 权舆协议函数（阶段二预留接口）
# ═══════════════════════════════════════════

def quanyu_yaogua(concept_dict):
    """
    摇卦·脆弱性审计
    计算生克网络中每个节点的中心度，找出最脆弱节点。

    Returns:
        VulnerabilityReport: {nodes, most_vulnerable, regret_score}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    if not isinstance(concepts, dict): return {'error': 'invalid dict format'}

    # 构建生克网络邻接表
    adjacency = defaultdict(list)
    concept_list = list(concepts.items())

    for ch, c in concept_list:
        c_wx = bare_wx(c.get('五行', ''))
        if not c_wx: continue

        for other_ch, other in concept_list:
            if other_ch == ch: continue
            o_wx = bare_wx(other.get('五行', ''))
            if not o_wx: continue

            if KE.get(c_wx) == o_wx:
                adjacency[ch].append((other_ch, 'ke_out', 1.0))
            elif KE.get(o_wx) == c_wx:
                adjacency[ch].append((other_ch, 'ke_in', -0.8))
            elif SHENG.get(c_wx) == o_wx:
                adjacency[ch].append((other_ch, 'sheng_out', 0.5))
            elif SHENG.get(o_wx) == c_wx:
                adjacency[ch].append((other_ch, 'sheng_in', 0.3))

    # 计算节点脆弱性：被克越多越脆弱
    vulnerability = {}
    for ch, edges in adjacency.items():
        ke_in_count = sum(1 for _, rel, _ in edges if rel == 'ke_in')
        total_edges = len(edges)
        vuln = ke_in_count / max(total_edges, 1)
        vulnerability[ch] = round(vuln, 3)

    if not vulnerability:
        return {'error': 'no valid network nodes'}

    most_vulnerable = max(vulnerability, key=vulnerability.get)
    regret_score = vulnerability[most_vulnerable]

    report = {
        'total_nodes': len(vulnerability),
        'most_vulnerable': most_vulnerable,
        'regret_score': regret_score,
        'top_vulnerable': sorted(vulnerability.items(), key=lambda x: -x[1])[:10]
    }

    audit_log('quanyu_yaogua', {
        'total_nodes': len(vulnerability),
        'most_vulnerable': most_vulnerable,
        'regret_score': regret_score
    }, severity='warning' if regret_score > 0.5 else 'info')

    return report


def quanyu_zhuanggua(concept_dict, target, steps=5):
    """
    装卦·行动序列生成
    沿生/克方向推演N步路径，输出行动建议。

    Returns:
        ActionSequence: {target, path, actions}
    """
    concepts = concept_dict.get('concepts', concept_dict)
    if target not in concepts:
        return {'error': f'target {target} not found'}

    target_wx = bare_wx(concepts[target].get('五行', ''))
    if not target_wx:
        return {'error': f'target {target} has no valid wuxing'}

    # 找所有能生目标的或克目标的
    actions = []
    for ch, c in concepts.items():
        if ch == target: continue
        c_wx = bare_wx(c.get('五行', ''))
        if not c_wx: continue

        if SHENG.get(c_wx) == target_wx:
            actions.append({
                'concept': ch,
                'action': 'sheng',
                'description': f'{ch}({c_wx})生{target}({target_wx}) → 增强'
            })
        elif KE.get(c_wx) == target_wx:
            actions.append({
                'concept': ch,
                'action': 'ke',
                'description': f'{ch}({c_wx})克{target}({target_wx}) → 抑制'
            })

    # 排序：生优先于克
    actions.sort(key=lambda x: 0 if x['action'] == 'sheng' else 1)

    report = {
        'target': target,
        'target_wuxing': target_wx,
        'total_actions': len(actions),
        'path': actions[:steps]
    }

    audit_log('quanyu_zhuanggua', {
        'target': target,
        'total_actions': len(actions),
        'top_action': actions[0]['description'] if actions else 'none'
    }, severity='info')

    return report


def quanyu_duangua(concept_dict, question):
    """
    断卦·综合推断（已有，此处做接口适配）
    基于概念网络对问题进行综合推断。

    Returns:
        DivinationReport
    """
    # 接口预留，实际逻辑在 auto_iterate.py 中
    return {
        'question': question,
        'status': 'interface_ready',
        'note': '核心断卦逻辑在 auto_iterate.py 中，此函数为调度接口'
    }


# ═══════════════════════════════════════════
# 主调度器
# ═══════════════════════════════════════════

def run_full_pipeline(concept_dict=None, anomalies_path=None):
    """
    全链路运行：anomalies → 盘古 → 共工 → 名家 → 兵家 → 烛龙

    Args:
        concept_dict: 概念字典（dict 或 path）
        anomalies_path: anomalies.json 路径（可选，默认自动查找）
    """
    # 加载字典
    if concept_dict is None:
        with open(DICT_PATH, 'r', encoding='utf-8') as f:
            concept_dict = json.load(f)
    elif isinstance(concept_dict, str):
        with open(concept_dict, 'r', encoding='utf-8') as f:
            concept_dict = json.load(f)

    # 加载异常文件（如果有）
    anomalies = []
    if anomalies_path is None:
        default_anomalies = os.path.join(SCRIPT_DIR, 'anomalies.json')
        if os.path.exists(default_anomalies):
            with open(default_anomalies, 'r', encoding='utf-8') as f:
                anomalies = json.load(f)
    elif os.path.exists(anomalies_path):
        with open(anomalies_path, 'r', encoding='utf-8') as f:
            anomalies = json.load(f)

    print(f'═══ 太极协议 · 全链路调度 ═══')
    print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'概念数: {len(concept_dict.get("concepts", concept_dict))}')
    print(f'异常数: {len(anomalies) if isinstance(anomalies, list) else "N/A"}')
    print()

    results = {}

    # Step 1: 盘古 · 矛盾制造
    print('[1/5] 盘古·矛盾制造...')
    conflicts = taiji_pangu(concept_dict)
    results['pangu'] = {'conflict_count': len(conflicts), 'top_conflicts': conflicts[:5]}
    print(f'  发现 {len(conflicts)} 对强对立概念')

    # Step 2: 共工 · 前提撞击（取盘古产出的top1冲突做测试）
    if conflicts:
        top = conflicts[0]
        print(f'[2/5] 共工·前提撞击（测试: {top["a"]}↔{top["b"]}）...')
        hypothesis = {'concept': top['a'], 'relation': top['relation'], 'target': top['b']}
        negation = taiji_gonggong(concept_dict, hypothesis)
        results['gonggong'] = negation
        print(f'  风险等级: {negation.get("risk_level", "N/A")}')
    else:
        print('[2/5] 共工·前提撞击 → 跳过（无冲突对）')

    # Step 3: 名家 · 概念崩塌追踪（扫描漂移最大的前10个概念）
    print('[3/5] 名家·崩塌追踪...')
    concepts = concept_dict.get('concepts', concept_dict)
    drift_scores = []
    for ch, c in concepts.items():
        delta = c.get('drift_delta', 0)
        if delta > 0.001:
            drift_scores.append((ch, delta))
    drift_scores.sort(key=lambda x: -x[1])

    collapse_warnings = []
    for ch, _ in drift_scores[:10]:
        warning = taiji_mingjia(concept_dict, ch)
        if warning.get('warning'):
            collapse_warnings.append(warning)
    results['mingjia'] = {'scanned': min(10, len(drift_scores)), 'warnings': len(collapse_warnings)}
    print(f'  扫描10个高漂移概念，发现 {len(collapse_warnings)} 个崩塌警告')

    # Step 4: 兵家 · 势能推演（取盘古产出的top1冲突对）
    if conflicts:
        top = conflicts[0]
        print(f'[4/5] 兵家·势能推演（{top["a"]} vs {top["b"]}, 5步）...')
        momentum = taiji_bingjia(concept_dict, top['a'], top['b'], steps=5)
        results['bingjia'] = momentum
        print(f'  胜者: {momentum.get("winner")} (置信度: {momentum.get("confidence")})')
    else:
        print('[4/5] 兵家·势能推演 → 跳过（无冲突对）')

    # Step 5: 烛龙 · 元认知反思
    print('[5/5] 烛龙·元认知反思...')
    reflection = taiji_zhulong()
    results['zhulong'] = reflection
    print(f'  {reflection.get("summary", "N/A")}')

    # 保存结果
    output_path = os.path.join(SCRIPT_DIR, 'orchestrator_output.json')
    results['_meta'] = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'dict_path': DICT_PATH
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 全链路完成 → {output_path}')
    print(f'📋 审计日志 → {AUDIT_LOG_PATH}')

    return results


def run_single_step(step_name, concept_dict=None):
    """运行单步协议函数"""
    if concept_dict is None:
        with open(DICT_PATH, 'r', encoding='utf-8') as f:
            concept_dict = json.load(f)

    concepts = concept_dict.get('concepts', concept_dict)

    if step_name == 'pangu':
        return taiji_pangu(concept_dict)
    elif step_name == 'gonggong':
        # 需要手动指定 hypothesis
        ch_list = list(concepts.keys())[:2]
        hypothesis = {'concept': ch_list[0], 'relation': 'sheng', 'target': ch_list[1]} if len(ch_list) >= 2 else {}
        return taiji_gonggong(concept_dict, hypothesis)
    elif step_name == 'mingjia':
        # 找漂移最大的概念
        drift_scores = [(ch, c.get('drift_delta', 0)) for ch, c in concepts.items()]
        drift_scores.sort(key=lambda x: -x[1])
        if drift_scores:
            return taiji_mingjia(concept_dict, drift_scores[0][0])
        return {'error': 'no drifted concepts'}
    elif step_name == 'bingjia':
        ch_list = list(concepts.keys())[:2]
        if len(ch_list) >= 2:
            return taiji_bingjia(concept_dict, ch_list[0], ch_list[1])
        return {'error': 'need at least 2 concepts'}
    elif step_name == 'zhulong':
        return taiji_zhulong()
    else:
        return {'error': f'unknown step: {step_name}'}


# ═══════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='太极概念引擎 · 调度中枢')
    parser.add_argument('--step', choices=VALID_STEPS, help='单步运行指定协议函数')
    parser.add_argument('--from', dest='from_file', help='从指定异常文件启动')
    parser.add_argument('--dict', default=DICT_PATH, help='概念字典路径')
    args = parser.parse_args()

    if args.step:
        # 单步模式
        result = run_single_step(args.step, args.dict)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 全链路模式
        run_full_pipeline(args.dict, getattr(args, 'from_file', None))


if __name__ == '__main__':
    main()
