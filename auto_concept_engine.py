#!/usr/bin/env python3
"""
太极概念引擎 · 自动推演脚本 v2.0
输入：新字列表 → 输出：完整字典条目 JSON

用法：
    python auto_concept_engine.py 钢 钩 镰 锥 针              # 命令行输入
    python auto_concept_engine.py --file words.txt              # 文件输入
    python auto_concept_engine.py --file words.txt --dict concept_dict.json  # 指定字典
"""

import json, math, sys, os, time
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DICT = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
ε = 1e-8

# ═══════════════════════════════════════════
# 八卦标准向量 + 默认振幅
# ═══════════════════════════════════════════
GUA_VEC = {
    '乾☰': (0.9,0.8,0.7,0.9,0.1,0.1,0.3,0.8),
    '兑☱': (0.4,0.5,0.8,0.5,0.6,0.4,0.3,0.5),
    '离☲': (0.5,0.4,0.3,0.3,0.7,0.6,0.9,0.2),
    '震☳': (0.7,0.9,0.4,0.2,0.4,0.3,0.5,0.3),
    '巽☴': (0.2,0.5,0.1,0.4,0.9,0.9,0.3,0.1),
    '坎☵': (0.4,0.3,0.5,0.6,0.7,0.8,0.2,0.6),
    '艮☶': (0.5,0.2,0.9,0.8,0.1,0.1,0.2,0.9),
    '坤☷': (0.5,0.1,0.4,0.9,0.1,0.2,0.3,0.8),
    '元':   (0.51,0.46,0.51,0.58,0.45,0.43,0.38,0.53),  # 八卦均值·元态未定
}
DEFAULT_AMPLITUDE = {'乾☰':0.89,'兑☱':0.79,'离☲':0.80,'震☳':0.78,'巽☴':0.79,'坎☵':0.81,'艮☶':0.82,'坤☷':0.77,'元':0.50}
WX_MAP = {'乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木','巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土','元':'不定'}
SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金','不定':'?'}
KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水','不定':'?'}

def norm(v): return math.sqrt(sum(x*x for x in v))
def cos_sim(a,b):
    return sum(a[i]*b[i] for i in range(8))/(norm(a)*norm(b)+ε)

# ═══════════════════════════════════════════
# 部首映射表 (100+)
# ═══════════════════════════════════════════
RADICAL_WX = {
    # ── 金 (40) ──
    '钅':'金','金':'金','釒':'金','钢':'金','铁':'金','银':'金','铜':'金','锁':'金','链':'金','钟':'金','铃':'金',
    '铛':'金','铲':'金','钩':'金','镰':'金','锥':'金','针':'金','钉':'金','钗':'金','锦':'金','绣':'金','镶':'金',
    '镀':'金','错':'金','镇':'金','镜':'金','鉴':'金','銮':'金','锻':'金','铸':'金','铠':'金','铭':'金','铮':'金',
    '钧':'金','锋':'金','刀':'金','剑':'金','刃':'金','锐':'金',
    # ── 水 (35) ──
    '氵':'水','水':'水','冫':'水','雨':'水','雪':'水','霜':'水','冰':'水','露':'水','雾':'水','海':'水','江':'水',
    '河':'水','湖':'水','渊':'水','泉':'水','波':'水','浪':'水','涛':'水','涌':'水','流':'水','滴':'水','溪':'水',
    '涧':'水','潭':'水','瀑':'水','涟':'水','漪':'水','汪':'水','洋':'水','浩':'水','瀚':'水','洪':'水','涝':'水',
    '沐':'水','浴':'水','沁':'水','润':'水','滋':'水','清':'水','浊':'水','潜':'水','溺':'水',
    # ── 木 (35) ──
    '木':'木','林':'木','森':'木','禾':'木','艹':'木','竹':'木','矛':'木','树':'木','松':'木','柏':'木','槐':'木',
    '榆':'木','杨':'木','桐':'木','杉':'木','榕':'木','桦':'木','枫':'木','橡':'木','檀':'木','叶':'木','花':'木',
    '草':'木','藤':'木','蔓':'木','柳':'木','笋':'木','芽':'木','苗':'木','茎':'木','菜':'木','莲':'木','荷':'木',
    '菊':'木','兰':'木','芝':'木','艾':'木','苇':'木','荆':'木','蔬':'木','核':'木','果':'木','根':'木','枝':'木',
    # ── 火 (30) ──
    '火':'火','日':'火','光':'火','灯':'火','烛':'火','焰':'火','烧':'火','燃':'火','热':'火','烈':'火','爆':'火',
    '炸':'火','灿':'火','烂':'火','辉':'火','煌':'火','照':'火','耀':'火','烁':'火','熔':'火','焚':'火','燎':'火',
    '烤':'火','烘':'火','烙':'火','煎':'火','熬':'火','烹':'火','煮':'火','熏':'火','炒':'火','灼':'火','灸':'火',
    '炮':'火','煅':'火','炫':'火','煜':'火',
    # ── 土 (35) ──
    '土':'土','石':'土','山':'土','瓦':'土','田':'土','阝':'土','皿':'土','广':'土','地':'土','尘':'土','沙':'土',
    '岩':'土','矿':'土','陶':'土','瓷':'土','砖':'土','壁':'土','垒':'土','城':'土','墙':'土','基':'土','址':'土',
    '坦':'土','坪':'土','均':'土','垣':'土','坡':'土','坎':'土','坑':'土','垄':'土','丘':'土','陵':'土','墟':'土',
    '墓':'土','坟':'土','坛':'土','塔':'土','碑':'土','塑':'土','型':'土','坯':'土','胎':'土','壳':'土','模':'土',
    '范':'土','疆':'土',
}

# ═══════════════════════════════════════════
# 概念四类型语义分类层
# CJK字符是单码点，不能子串匹配，用查找表
# ═══════════════════════════════════════════
SEMANTIC_LOOKUP = {
    # ── 哲理(离☲·火, 温润光明) ──
    '仁':'离☲','思':'离☲','想':'离☲','意':'离☲','志':'离☲','德':'离☲','惠':'离☲',
    '慈':'离☲','恕':'离☲','忍':'离☲','怨':'离☲','惑':'离☲','悲':'离☲','恐':'离☲',
    '忧':'离☲','惊':'离☲','恩':'离☲','忿':'离☲','怠':'离☲','忘':'离☲','欢':'离☲',
    '爱':'离☲','恨':'离☲','喜':'离☲','怒':'离☲','哀':'离☲','乐':'离☲',
    # ── 言说/价值(兑☱·金, 边界规范) ──
    '信':'兑☱','诚':'兑☱','让':'兑☱','谦':'兑☱','谏':'兑☱','谤':'兑☱','誉':'兑☱',
    '诺':'兑☱','谓':'兑☱','语':'兑☱','言':'兑☱','说':'兑☱','词':'兑☱','讲':'兑☱',
    '训':'兑☱','论':'兑☱','议':'兑☱','讼':'兑☱','谨':'兑☱','谋':'兑☱',
    '美':'兑☱','善':'兑☱','真':'兑☱','是':'兑☱','对':'兑☱','义':'兑☱',
    '贵':'兑☱','贱':'兑☱','贫':'兑☱','富':'兑☱','贤':'兑☱','圣':'兑☱','名':'兑☱',
    # ── 认知/洞察(坎☵·水, 深渊明澈) ──
    '智':'坎☵','知':'坎☵','识':'坎☵','觉':'坎☵','悟':'坎☵','察':'坎☵','省':'坎☵',
    '闻':'坎☵','听':'坎☵','思':'坎☵','精':'坎☵',
    '恶':'坎☵','非':'坎☵','错':'坎☵','伪':'坎☵','丑':'坎☵','枉':'坎☵',
    # ── 行动/突破(震☳·木, 破土向上) ──
    '行':'震☳','动':'震☳','作':'震☳','为':'震☳','学':'震☳','习':'震☳','修':'震☳',
    '治':'震☳','教':'震☳','化':'震☳','改':'震☳','变':'震☳','争':'震☳','战':'震☳',
    '胜':'震☳','克':'震☳','取':'震☳','夺':'震☳','进':'震☳','退':'震☳',
    '生':'震☳','成':'震☳','建':'震☳','立':'震☳','兴':'震☳','废':'震☳','直':'震☳',
    # ── 柔渗/和顺(巽☴·木, 渗透灵动) ──
    '和':'巽☴','气':'巽☴','虚':'巽☴','而':'巽☴','柔':'巽☴',
    # ── 刚健/至高(乾☰·金, 天道本体) ──
    '道':'乾☰','义':'乾☰','忠':'乾☰','命':'乾☰','有':'乾☰','阳':'乾☰','君':'乾☰',
    '一':'乾☰','十':'乾☰','万':'乾☰','亿':'乾☰','数':'乾☰','主':'乾☰','神':'乾☰',
    '父':'乾☰','师':'乾☰','同':'乾☰','元':'乾☰','太':'乾☰',
    # ── 承载/根基(艮☶·土, 如山不动) ──
    '礼':'艮☶','敬':'艮☶','恭':'艮☶','孝':'艮☶','信':'艮☶','质':'艮☶','实':'艮☶',
    '体':'艮☶','身':'艮☶','己':'艮☶','自':'艮☶','始':'艮☶','极':'艮☶','五':'艮☶',
    '百':'艮☶','理':'艮☶',
    # ── 包容/承载(坤☷·土, 大地之母) ──
    '名':'坤☷','性':'坤☷','德':'坤☷','臣':'坤☷','民':'坤☷','众':'坤☷','母':'坤☷',
    '我':'坤☷','吾':'坤☷','以':'坤☷','为':'坤☷','于':'坤☷','与':'坤☷','无':'坤☷',
    '常':'坤☷','恒':'坤☷','久':'坤☷','终':'坤☷','阴':'坤☷','二':'坤☷','八':'坤☷',
    '零':'坤☷','下':'坤☷','小':'坤☷',
}

def detect_semantic(ch):
    """语义查找表→卦象检测（仅当部首检测失败时调用）"""
    if ch in SEMANTIC_LOOKUP:
        gua = SEMANTIC_LOOKUP[ch]
        wx = WX_MAP[gua]
        return gua, wx, f'语义查表→{gua}'
    return None, None, '查表未命中'

# 阴阳倾向词集
YANG_BIAS = set('钢铁铜银铸锻钟铃镇鉴刚强硬坚固钧铠剑锋刃锐岩壁城墙塔碑陵丘岭垒矿锭')
YIN_BIAS  = set('锋刀剑针钉锥钩镰钗锦绣镶镀错铭铮柔润滋沁沐浴露霜雾雪冰凝')

def detect_wuxing(ch):
    """部首→五行识别"""
    for radical, wx in sorted(RADICAL_WX.items(), key=lambda x:-len(x[0])):
        if radical in ch:
            return wx, radical
    return None, None

def classify_trigram(ch, wuxing):
    """五行+语义→卦象阴阳判定"""
    if ch in YANG_BIAS: polarity = '阳'
    elif ch in YIN_BIAS: polarity = '阴'
    else: polarity = '中'
    
    mapping = {
        ('金','阳'):('乾☰',0.9,'刚硬→阳金·乾☰'),
        ('金','阴'):('兑☱',0.85,'锋锐装饰→阴金·兑☱'),
        ('金','中'):('兑☱',0.7,'金部默认→阴金·兑☱'),
        ('水','阳'):('坎☵',0.85,'大水→坎☵'),
        ('水','阴'):('坎☵',0.85,'细水→坎☵'),
        ('水','中'):('坎☵',0.85,'水部→坎☵'),
        ('木','阳'):('震☳',0.9,'硬木大树→阳木·震☳'),
        ('木','阴'):('巽☴',0.85,'软草细藤→阴木·巽☴'),
        ('木','中'):('巽☴',0.7,'木部默认→阴木·巽☴'),
        ('火','阳'):('离☲',0.85,'大火烈炎→离☲'),
        ('火','阴'):('离☲',0.80,'温火→离☲'),
        ('火','中'):('离☲',0.85,'火部→离☲'),
        ('土','阳'):('艮☶',0.9,'山石城墙→阳土·艮☶'),
        ('土','阴'):('坤☷',0.85,'地尘沙壤→阴土·坤☷'),
        ('土','中'):('坤☷',0.7,'土部默认→阴土·坤☷'),
    }
    return mapping.get((wuxing,polarity), ('坤☷',0.3,'无法判定→默认坤☷'))

def deduce(ch, existing_dict=None):
    """为单个字推演完整条目"""
    log = []
    sem_type = None
    
    # 1. 部首识别（物类）
    wuxing, radical_hit = detect_wuxing(ch)
    
    if wuxing:
        # 物类：部首→五行→八卦定型
        gua, confidence, reason = classify_trigram(ch, wuxing)
        classify_state = 'radical'
        log.append(f'物·部首:{radical_hit}→五行:{wuxing} | {reason}(置信度:{confidence:.0%})')
    else:
        # 部首失败 → 语义查找表
        gua, wx_sem, reason = detect_semantic(ch)
        if gua:
            wuxing = wx_sem
            confidence = 0.60
            classify_state = 'semantic'
            log.append(f'语义查表→{gua}({wuxing}) | {reason}(置信度:{confidence:.0%})')
        else:
            wuxing = '不定'
            gua = '元'
            confidence = 0.10
            classify_state = 'meta'
            log.append(f'元态·待漂移定卦 | 无部首无查表→八卦均值')
    
    # 2. 属性赋值
    vec = GUA_VEC[gua]
    amp = DEFAULT_AMPLITUDE[gua]
    
    # 4. 生克计算
    bare = wuxing
    sheng_me = SHENG.get(bare, '?')
    ke_me = KE.get(bare, '?')
    sheng_wo = [k for k,v in SHENG.items() if v==bare]
    ke_wo = [k for k,v in KE.items() if v==bare]
    
    entry = {
        '卦象': gua,
        '五行': WX_MAP[gua],
        '属性': dict(zip(DIMS, vec)),
        '阴阳振幅': amp,
        '我生': sheng_me, '我克': ke_me,
        '生我': sheng_wo, '克我': ke_wo,
        'baseline_vector': dict(zip(DIMS, vec)),
        'drift_state': 'stable',
        'drift_delta': 0.0,
        'interaction_count': 0,
        'auto_classified': True,
        'auto_confidence': confidence,
        'auto_reason': reason,
        'classify_state': classify_state,  # radical|semantic|meta|drift_corrected
        'radical': radical_hit if wuxing and wuxing != '不定' else '(无)'
    }
    
    # 5. 生克关系预计算
    if existing_dict:
        relations = {}
        for other_ch, other in existing_dict.items():
            if other_ch == ch: continue
            other_wx = other['五行']
            ob = other_wx.split('(')[0] if '(' in str(other_wx) else other_wx
            oe = ob.replace('阳','').replace('阴','')
            
            if sheng_me == oe: rel = '我生彼'
            elif ke_me == oe: rel = '我克彼'
            elif bare in sheng_wo: rel = '彼生我'
            elif bare in ke_wo: rel = '彼克我'
            elif bare == oe: rel = '五行相同'
            else: rel = '无直接关系'
            
            sa = cos_sim(list(vec), list(other['属性'].values()))
            relations[other_ch] = {'relation': rel, 'coupling': round(0.5*_get_sw(rel)+0.3*sa,3)}
        
        entry['_relations'] = relations
    
    return entry, log

def _get_sw(rel):
    return {'我生彼':0.5,'我克彼':-0.5,'彼生我':0.3,'彼克我':-0.3,'五行相同':0.2}.get(rel, 0)

def main():
    import argparse
    words = []
    
    # 解析输入
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        fpath = sys.argv[idx+1] if idx+1 < len(sys.argv) else None
        if fpath and os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]
    elif '--dict' in sys.argv:
        pass  # handled below
    else:
        words = [a for a in sys.argv[1:] if not a.startswith('--')]
    
    if not words:
        print('用法: python auto_concept_engine.py 字1 字2 ...')
        print('      python auto_concept_engine.py --file words.txt')
        return
    
    # 加载现有字典
    dict_idx = None
    if '--dict' in sys.argv:
        dict_idx = sys.argv.index('--dict')
    dict_path = sys.argv[dict_idx+1] if dict_idx and dict_idx+1 < len(sys.argv) else DEFAULT_DICT
    
    existing = {}
    if os.path.exists(dict_path):
        with open(dict_path, 'r', encoding='utf-8') as f:
            existing = json.load(f).get('concepts', {})
    
    # 批量推演
    results = {}
    all_logs = []
    total = len(words)
    
    print(f'═══ 批量推演 {total} 字 ═══')
    for i, ch in enumerate(words, 1):
        if ch in existing:
            all_logs.append(f'[{i}/{total}] {ch} → 已在字典中，跳过')
            continue
        
        entry, log = deduce(ch, existing)
        results[ch] = entry
        status = '✅' if entry['auto_confidence'] >= 0.7 else '⚠️'
        gua_name = entry['卦象']
        wx_name = entry['五行']
        conf = entry['auto_confidence']
        all_logs.append(f'[{i}/{total}] {ch} → {gua_name}({wx_name}) 置信度{conf:.0%} {status}')
    
    # 输出
    out_path = os.path.join(SCRIPT_DIR, 'new_concepts.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'deduced_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'count': len(results), 'concepts': results}, f, ensure_ascii=False, indent=2)
    
    # 日志
    log_path = os.path.join(SCRIPT_DIR, 'deduce_log.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_logs))
    
    print(f'\n✅ 完成: {len(results)}新增 | {total-len(results)}跳过 | 输出: new_concepts.json')
    print(f'📋 日志: deduce_log.txt')

if __name__ == '__main__':
    main()
