#!/usr/bin/env python3
"""
太极概念字典 · 自动迭代引擎 v1.0
新字进入 → 自动定型 → 生克计算 → 交互中累积 → 属性漂移 → 触底偏移 → 自动更新字典

用法：
    python auto_iterate.py add 钢       # 新增一个字，自动定型
    python auto_iterate.py interact 柔 刚  # 模拟一次交互，追踪累积效应
    python auto_iterate.py drift           # 扫描全字典，检测漂移
    python auto_iterate.py split           # 检测是否有概念需要拆分
    python auto_iterate.py status 柔       # 查看某概念当前状态
"""

import json, math, sys, os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
ε = 1e-8

# ─── 八卦标准向量 ───
GUA_VEC = {
    '乾☰': (0.9,0.8,0.7,0.9,0.1,0.1,0.3,0.8),
    '兑☱': (0.4,0.5,0.8,0.5,0.6,0.4,0.3,0.5),
    '离☲': (0.5,0.4,0.3,0.3,0.7,0.6,0.9,0.2),
    '震☳': (0.7,0.9,0.4,0.2,0.4,0.3,0.5,0.3),
    '巽☴': (0.2,0.5,0.1,0.4,0.9,0.9,0.3,0.1),
    '坎☵': (0.4,0.3,0.5,0.6,0.7,0.8,0.2,0.6),
    '艮☶': (0.5,0.2,0.9,0.8,0.1,0.1,0.2,0.9),
    '坤☷': (0.5,0.1,0.4,0.9,0.1,0.2,0.3,0.8),
}
WX = {'乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木','巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土'}
SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
KE = {'金':'木','木':'土','水':'火','火':'金','土':'水'}

def norm(v): return math.sqrt(sum(x*x for x in v))

def load():
    with open(DICT_PATH,'r',encoding='utf-8') as f:
        return json.load(f)

def save(d):
    with open(DICT_PATH,'w',encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════
# 第一步：自动定型
# ═══════════════════════════════════════════

# 部首→五行映射
RADICAL_WX = {
    # 金
    '钅':'金','金':'金','釒':'金','钢':'金','银':'金','铜':'金','锁':'金','链':'金','鼎':'金',
    '铁':'金','钟':'金','铃':'金','铛':'金','铲':'金','钩':'金','镰':'金','锥':'金','针':'金','钉':'金',
    '锦':'金','绣':'金','镶':'金','镀':'金','错':'金','镇':'金','镜':'金','鉴':'金','銮':'金','锻':'金','铸':'金','铠':'金','铭':'金','铮':'金','钧':'金',
    # 水
    '氵':'水','水':'水','冫':'水','雨':'水','雪':'水','霜':'水','冰':'水','灬':'水','露':'水','雾':'水',
    '海':'水','江':'水','河':'水','湖':'水','渊':'水','泉':'水','波':'水','浪':'水','涛':'水','涌':'水','流':'水','滴':'水','溪':'水','涧':'水','潭':'水','瀑':'水','涟':'水','漪':'水','汪':'水','洋':'水','浩':'水','瀚':'水','洪':'水','涝':'水','沐':'水','浴':'水','沁':'水','润':'水','滋':'水','清':'水','浊':'水','潜':'水','溺':'水',
    # 木
    '木':'木','林':'木','森':'木','禾':'木','艹':'木','竹':'木','⺮':'木','矛':'木','柔':'木',
    '树':'木','松':'木','柏':'木','竹':'木','槐':'木','榆':'木','杨':'木','桐':'木','杉':'木','榕':'木','桦':'木','枫':'木','橡':'木','檀':'木',
    '叶':'木','花':'木','草':'木','藤':'木','蔓':'木','柳':'木','笋':'木','芽':'木','苗':'木','茎':'木','菜':'木','莲':'木','荷':'木','菊':'木','兰':'木','芝':'木','艾':'木','苇':'木','荆':'木',
    # 火
    '火':'火','日':'火','光':'火','灯':'火','烛':'火','灬':'火',
    '焰':'火','烧':'火','燃':'火','热':'火','烈':'火','爆':'火','炸':'火','灿':'火','烂':'火','辉':'火','煌':'火','照':'火','耀':'火','烁':'火','熔':'火','焚':'火','燎':'火','烤':'火','烘':'火','烙':'火','煎':'火','熬':'火','烹':'火','煮':'火','熏':'火','炒':'火','灼':'火','灸':'火','炮':'火','煅':'火',
    # 土
    '土':'土','石':'土','山':'土','瓦':'土','田':'土','阝':'土','皿':'土','广':'土','彐':'土',
    '地':'土','尘':'土','沙':'土','岩':'土','矿':'土','陶':'土','瓷':'土','砖':'土','壁':'土','垒':'土','城':'土','墙':'土','基':'土','址':'土','坦':'土','坪':'土','均':'土','垣':'土','坡':'土','坎':'土','坑':'土','垄':'土','丘':'土','陵':'土','墟':'土','墓':'土','坟':'土','坛':'土','塔':'土','碑':'土','塑':'土','型':'土','坯':'土','胎':'土','壳':'土','模':'土','范':'土','疆':'土',
}

# 语义特征→阴阳判断（阳=硬/重/刚，阴=软/轻/柔）
YANG_BIAS = set('钢铁铜银铸锻钟铃镇鉴刚强硬坚固钧铠岩壁城墙塔碑陵丘树干松柏竹槐榆杨桐杉榕樟橡檀剑锋刃锐')
YIN_BIAS  = set('花叶草藤蔓绣锦钗针链镶镀错泥尘沙粉尘温柔软弱细纤')

# 八卦定型（用W矩阵+爻位模拟，无需真实LLM）
def auto_classify(ch):
    """自动推断汉字卦象。返回 (卦象, 置信度, 理由)"""
    wx_base = None
    for radical, wx in sorted(RADICAL_WX.items(), key=lambda x:-len(x[0])):
        if radical in ch:
            wx_base = wx; break
    if not wx_base: return ('坤☷', 0.3, f'无法从部首推断五行，默认坤☷(承载)')
    
    if ch in YANG_BIAS: polarity = '阳'
    elif ch in YIN_BIAS: polarity = '阴'
    else: polarity = '中'
    
    mapping = {
        ('金','阳'):('乾☰',0.9,f'部首金→刚硬→阳金·乾☰'),
        ('金','阴'):('兑☱',0.85,f'部首金→锋利/装饰→阴金·兑☱'),
        ('金','中'):('兑☱',0.7,f'部首金→默认精加工→阴金·兑☱'),
        ('水','阳'):('坎☵',0.85,f'部首水→流动→水·坎☵'),
        ('水','阴'):('坎☵',0.85,f'部首水→渗透→水·坎☵'),
        ('水','中'):('坎☵',0.85,f'部首水→水·坎☵'),
        ('木','阳'):('震☳',0.9,f'部首木→硬木大树→阳木·震☳'),
        ('木','阴'):('巽☴',0.85,f'部首木→柔软草本→阴木·巽☴'),
        ('木','中'):('震☳',0.7,f'部首木→默认向上突破→阳木·震☳'),
        ('火','阳'):('离☲',0.85,f'部首火→光明→火·离☲'),
        ('火','阴'):('离☲',0.8,f'部首火→温暖→火·离☲'),
        ('火','中'):('离☲',0.85,f'部首火→火·离☲'),
        ('土','阳'):('艮☶',0.9,f'部首土→石/山→阳土·艮☶'),
        ('土','阴'):('坤☷',0.85,f'部首土→尘/地→阴土·坤☷'),
        ('土','中'):('坤☷',0.7,f'部首土→承载→阴土·坤☷'),
    }
    return mapping.get((wx_base,polarity), ('坤☷',0.3,f'未匹配，默认坤☷'))

def classify_and_deduce(ch):
    """完整的自动定型→属性赋值→生克计算"""
    gua, conf, reason = auto_classify(ch)
    wx_str = WX[gua]
    vec = GUA_VEC[gua]
    bare = wx_str.split('(')[0] if '(' in str(wx_str) else wx_str
    # strip 阳/阴 prefix for SHENG/KE lookup
    element = bare.replace('阳','').replace('阴','')
    
    return {
        '卦象': gua, '五行': wx_str,
        '属性': dict(zip(DIMS, vec)),
        '阴阳振幅': round(norm(vec)/1.543, 2),
        '我生': SHENG.get(element,'?'), '我克': KE.get(element,'?'),
        '生我': [k for k,v in SHENG.items() if v==element],
        '克我': [k for k,v in KE.items() if v==element],
        'baseline_vector': dict(zip(DIMS, vec)),
        'drift_state': 'stable',
        'drift_delta': 0.0,
        'interaction_count': 0,
        'auto_classified': True,
        'auto_confidence': conf,
        'auto_reason': reason
    }

# ═══════════════════════════════════════════
# 第二步：累积效应追踪
# ═══════════════════════════════════════════

def interact(d, a_name, b_name):
    """模拟概念A→B的一次交互，追踪累积效应"""
    if a_name not in d['concepts'] or b_name not in d['concepts']:
        missing = a_name if a_name not in d['concepts'] else b_name
        print(f'❌ 概念不存在: {missing}')
        return
    
    ca = d['concepts'][a_name]
    cb = d['concepts'][b_name]
    
    # 提取属性值
    pa = ca['属性']['渗透性']
    la = ca['属性']['灵动性']
    bb = cb['属性']['边界性']
    pb = cb['属性']['持续性']
    ya = ca['阴阳振幅']
    
    # 阴阳调制克制——克力基值恒存，阴阳调强度
    ke_base = 0.05
    ke_mod = 2.0 if ya < 0.5 else 0.5  # 阴盛增强，阳盛减弱
    ke_strength = ke_base * ke_mod
    
    # 时间积分效应（合并克制基值）
    t = ca['interaction_count'] + 1
    lt = d['evolution']['time_integrated_shengke']['lambda_t']
    effect = lt * ya * pa * (1 - bb) * t + ke_strength
    
    # 检查是否触发生克翻转
    flip = pa * la * t > bb * pb
    
    # 更新交互计数
    ca['interaction_count'] += 1
    cb['interaction_count'] += 1
    
    # 自适应漂移步长（δ_base × max(|a-b|, ε)）+ 中观层生克合力
    delta_base = d['evolution']['concept_drift']['delta']  # 0.01
    eta = d['evolution']['concept_drift']['eta']  # 0.1
    a_vec = list(ca['属性'].values())
    b_vec = list(cb['属性'].values())
    delta_vec = []
    for i in range(8):
        diff = abs(a_vec[i] - b_vec[i])
        delta_adaptive = delta_base * max(diff, ε)
        # 内部语义张力 + 外部生克合力
        delta_vec.append(delta_adaptive * ya + eta * effect * (1.0 if a_vec[i] > b_vec[i] else -1.0))
    
    for i, dim in enumerate(DIMS):
        new_val = max(0.0, min(1.0, b_vec[i] + delta_vec[i]))
        cb['属性'][dim] = round(new_val, 4)
    
    # 更新漂移量：Δ = ||c_n - c_0||
    c0 = list(cb['baseline_vector'].values())
    cn = list(cb['属性'].values())
    cb['drift_delta'] = round(norm([cn[i]-c0[i] for i in range(8)]), 4)
    
    # 检查底色偏移
    cos_sim = sum(c0[i]*cn[i] for i in range(8))/(norm(c0)*norm(cn)+ε)
    entropy = -sum(abs(cn[i])*math.log(abs(cn[i])+ε) for i in range(8))
    
    old_state = cb['drift_state']
    if entropy >= 0.7 or cos_sim < 0.3:
        cb['drift_state'] = 'shifted'
    
    flip_msg = '⚠️ 触发' if flip else '未触发'
    print(f'═══ {a_name}→{b_name} 第{t}次交互 ═══')
    print(f'  累积效应: {effect:.6f}')
    print(f'  生克翻盘: {flip_msg}')
    if flip:
        print(f'    渗透{pa}×灵动{la}×{t}次({pa*la*t:.2f}) > 边界{bb}×持续{pb}({bb*pb:.2f})')
    bd = cb['drift_delta']
    print(f'  {b_name}属性漂移: Δ={bd:.4f}')
    bds = cb['drift_state']
    print(f'  底色状态: {old_state} → {bds}')
    
    return effect

# ═══════════════════════════════════════════
# 第三步：漂移扫描
# ═══════════════════════════════════════════

def scan_drift(d):
    """扫描全字典，标记所有漂移概念"""
    shifted = []
    for ch, c in d['concepts'].items():
        if c['drift_delta'] > 0.1:
            shifted.append((ch, c['drift_delta'], c['drift_state']))
    shifted.sort(key=lambda x:-x[1])
    
    total = len(d['concepts'])
    print(f'═══ 漂移扫描 ═══')
    print(f'  总概念: {total}')
    print(f'  漂移>0.1: {len(shifted)}')
    
    if shifted:
        print(f'\n  漂移排名:')
        for ch, delta, state in shifted[:10]:
            bar = '▓'*int(delta*20)
            flag = ' ⚠️' if state=='shifted' else ''
            print(f'    {ch:4s} Δ={delta:.4f} {bar}{flag}')
    
    return shifted

# ═══════════════════════════════════════════
# 第四步：概念拆分检测
# ═══════════════════════════════════════════

def detect_split(d, min_dist=0.4):
    """检测8维空间中是否存在需要拆分的概念"""
    candidates = []
    for ch, c in d['concepts'].items():
        vec = list(c['属性'].values())
        # 检查是否有内部不一致（用属性极差判断）
        spread = max(vec) - min(vec)
        entropy = -sum(abs(vec[i])*math.log(abs(vec[i])+ε) for i in range(8))
        if entropy > 0.5 or spread > 0.7:
            candidates.append((ch, spread, entropy, c['卦象']))
    
    candidates.sort(key=lambda x:-x[2])
    print(f'═══ 概念拆分检测 ═══')
    print(f'  待审查: {len(candidates)} 个')
    if candidates:
        print(f'\n  高熵概念（可能需拆分）:')
        for ch, spread, entropy, gua in candidates[:5]:
            print(f'    {ch:4s}({gua}) 属性极差={spread:.2f} 熵={entropy:.3f}')
    
    return candidates

# ═══════════════════════════════════════════
# 权舆协议 v6.1 · 确定性汇聚引擎
# ═══════════════════════════════════════════

def quanyu_pan(nodes):
    """
    排盘：将不确定性节点构建为加权生克网络
    输入: [{'name':str, '卦象':str, '五行':str, '阴阳振幅':float, '矛盾值':float}]
    输出: {'nodes':[...], 'edges':[...], 'network_density':float}
    """
    edges = []
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i >= j: continue
            bare_a = a['五行'].replace('阳','').replace('阴','').split('(')[0]
            bare_b = b['五行'].replace('阳','').replace('阴','').split('(')[0]
            
            # 生边
            if SHENG.get(bare_a) == bare_b and a['阴阳振幅'] >= 0.5:
                edges.append({'from': a['name'], 'to': b['name'], 'type': '生', 
                             'weight': round(0.1 * math.tanh(a['阴阳振幅']), 4)})
            elif SHENG.get(bare_b) == bare_a and b['阴阳振幅'] >= 0.5:
                edges.append({'from': b['name'], 'to': a['name'], 'type': '生',
                             'weight': round(0.1 * math.tanh(b['阴阳振幅']), 4)})
            
            # 克边
            if KE.get(bare_a) == bare_b and a['阴阳振幅'] < 0.5:
                edges.append({'from': a['name'], 'to': b['name'], 'type': '克',
                             'weight': round(-0.1 * math.tanh(1 - a['阴阳振幅']), 4)})
            elif KE.get(bare_b) == bare_a and b['阴阳振幅'] < 0.5:
                edges.append({'from': b['name'], 'to': a['name'], 'type': '克',
                             'weight': round(-0.1 * math.tanh(1 - b['阴阳振幅']), 4)})
    
    density = len(edges) / (len(nodes) * (len(nodes) - 1) / 2) if len(nodes) > 1 else 0
    
    return {'nodes': nodes, 'edges': edges, 'density': round(density, 3)}


def quanyu_najia(network, user_profile=None):
    """
    纳甲：特征向量中心度计算，定位核心矛盾 G_main
    user_profile: 可选，{'boost_elements': ['火','土'], 'boost_value': 0.1}
    """
    nodes = network['nodes']
    edges = network['edges']
    n = len(nodes)
    if n == 0: return None
    if n == 1:
        nodes[0]['centrality'] = 1.0
        return {'G_main': nodes[0], 'ranking': nodes}
    
    # 简化PageRank式中心度
    adj = {}
    for node in nodes: adj[node['name']] = {}
    for e in edges:
        adj[e['from']][e['to']] = e['weight']
    
    # 迭代计算特征向量中心度
    ranks = {node['name']: 1.0/n for node in nodes}
    for _ in range(100):
        new_ranks = {}
        for node in nodes:
            incoming = sum(adj.get(other, {}).get(node['name'], 0) * ranks[other] 
                         for other in [n2['name'] for n2 in nodes])
            new_ranks[node['name']] = 0.15/n + 0.85 * incoming
        s = sum(abs(v) for v in new_ranks.values()) or 1
        ranks = {k: v/s for k, v in new_ranks.items()}
    
    # 标准中心度（无偏好）
    for node in nodes:
        node['centrality'] = round(ranks[node['name']], 4)
    
    # 可选用神加权
    if user_profile:
        boost_elements = user_profile.get('boost_elements', [])
        boost_value = user_profile.get('boost_value', 0.1)
        for node in nodes:
            bare = node['五行'].replace('阳','').replace('阴','').split('(')[0]
            if bare in boost_elements:
                node['centrality'] = round(node['centrality'] + boost_value, 4)
    
    nodes_sorted = sorted(nodes, key=lambda x: -x['centrality'])
    
    return {
        'G_main': nodes_sorted[0],
        'ranking': nodes_sorted,
        'top3': nodes_sorted[:3]
    }


def quanyu_duangua(najia_result, threshold_pos=0.65, threshold_neg=0.30):
    """
    断卦：基于 G_main 中心度计算确定性概率，给出判决
    
    判决规则:
    - Prob >= 0.65 → 继续执行主路径
    - Prob <= 0.30 → 触发重新拆解
    - 0.30 < Prob < 0.65 → 临界区裁决，交人判断
    """
    if not najia_result or not najia_result.get('G_main'):
        return {'verdict': 'insufficient_data', 'action': '请提供更多不确定性节点'}
    
    G_main = najia_result['G_main']
    ranking = najia_result['ranking']
    
    total = sum(n['centrality'] for n in ranking)
    prob = G_main['centrality'] / total if total > 0 else 0
    
    # 后悔度
    regret = 0
    if len(ranking) >= 2:
        regret = (ranking[0]['centrality'] - ranking[1]['centrality']) / (ranking[0]['centrality'] + ε)
    
    if prob >= threshold_pos:
        verdict = 'execute'
        action = f'继续执行主路径(G_main={G_main["name"]})，确定性概率 {prob:.1%}'
    elif prob <= threshold_neg:
        verdict = 're_split'
        action = '触发重新拆解，将当前不确定性反馈回太极协议'
    else:
        verdict = 'critical_zone'
        action = f'临界区裁决。主路径(Prob={prob:.1%})vs备选(后悔度={regret:.2f})。请人做最终判断。'
    
    return {
        'verdict': verdict,
        'Prob_final': round(prob, 4),
        'regret': round(regret, 4),
        'action': action,
        'G_main_name': G_main['name'],
        'G_main_gua': G_main.get('卦象','?'),
        'G_main_centrality': G_main['centrality'],
        'threshold_pos': threshold_pos,
        'threshold_neg': threshold_neg
    }


def quanyu_full(nodes, threshold_pos=0.65, threshold_neg=0.30, user_profile=None):
    """
    权舆协议完整流程：排盘→纳甲→断卦
    user_profile: 可选 {'boost_elements':['火','土'], 'boost_value':0.1}
    """
    network = quanyu_pan(nodes)
    najia = quanyu_najia(network, user_profile)
    duangua = quanyu_duangua(najia, threshold_pos, threshold_neg)
    
    return {
        'network': {'nodes': len(nodes), 'edges': len(network['edges']), 'density': network['density']},
        'najia': {'G_main': najia['G_main']['name'] if najia and najia.get('G_main') else None, 
                  'top3': [(r['name'], r['centrality']) for r in (najia['ranking'][:3] if najia else [])]},
        'duangua': duangua
    }


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    d = load()
    
    if cmd == 'add':
        for ch in sys.argv[2:]:
            if ch in d['concepts']:
                print(f'  ⚠️ {ch} 已在字典中')
                continue
            entry = classify_and_deduce(ch)
            d['concepts'][ch] = entry
            conf = entry['auto_confidence']
            gua = entry['卦象']
            wx = entry['五行']
            reason = entry['auto_reason']
            print(f'  ✅ {ch} → {gua}({wx}) 置信度={conf:.0%} | {reason}')
        d['total_concepts'] = len(d['concepts'])
        save(d)
    
    elif cmd == 'interact':
        a, b = sys.argv[2], sys.argv[3]
        interact(d, a, b)
        save(d)
    
    elif cmd == 'drift':
        scan_drift(d)
    
    elif cmd == 'split':
        detect_split(d)
    
    elif cmd == 'quanyu':
        # 用法: python auto_iterate.py quanyu 柔 刚 道 一 水 火
        # 构建不确定性节点并跑权舆完整流程
        names = sys.argv[2:]
        nodes = []
        for name in names:
            if name in d['concepts']:
                c = d['concepts'][name]
                nodes.append({
                    'name': name,
                    '卦象': c['卦象'],
                    '五行': c['五行'],
                    '阴阳振幅': c['阴阳振幅'],
                    '矛盾值': c.get('drift_delta', 0.1)  # fallback
                })
        
        if len(nodes) < 2:
            print('需要至少2个概念节点')
            return
        
        result = quanyu_full(nodes)
        
        node_names = [n['name'] for n in nodes]
        print(f'═══ 权舆协议 v6.1 · 确定性汇聚 ═══')
        print(f'输入节点: {node_names}')
        print()
        net_nodes = result['network']['nodes']
        net_edges = result['network']['edges']
        net_dens = result['network']['density']
        print(f'[排盘] 生克网络: {net_nodes}节点 {net_edges}边 密度={net_dens}')
        print()
        print('[纳甲] 核心矛盾排序')
        for i, (name, cent) in enumerate(result['najia']['top3'], 1):
            bar = '█' * int(cent * 20)
            print(f'  {i}. {name:4s} 中心度={cent:.4f} {bar}')
        print()
        
        dg = result['duangua']
        verdict_emoji = {'execute': '✅', 're_split': '🔄', 'critical_zone': '⚠️'}
        gname = dg['G_main_name']
        ggua = dg['G_main_gua']
        prob = dg['Prob_final']
        reg = dg['regret']
        gverdict = dg['verdict']
        gaction = dg['action']
        print(f'[断卦] 确定性概率')
        print(f'  G_main: {gname}({ggua})')
        print(f'  Prob_final: {prob:.1%}')
        print(f'  后悔度: {reg:.3f}')
        print(f'  判决: {verdict_emoji.get(gverdict,"")} {gverdict}')
        print(f'  行动: {gaction}')
    
    elif cmd == 'status':
        ch = sys.argv[2]
        if ch in d['concepts']:
            c = d['concepts'][ch]
            gua = c['卦象']
            wx = c['五行']
            attr = c['属性']
            bl = c.get('baseline_vector', '无')
            dd = c.get('drift_delta', 0)
            ds = c.get('drift_state', '?')
            ic = c.get('interaction_count', 0)
            print(f'═══ {ch} ═══')
            print(f'  卦象: {gua}({wx})')
            print(f'  属性: {attr}')
            print(f'  基准: {bl}')
            print(f'  漂移: Δ={dd:.4f} | {ds}')
            print(f'  交互次数: {ic}')
        else:
            print(f'❌ {ch} 不在字典中')

if __name__ == '__main__':
    main()
