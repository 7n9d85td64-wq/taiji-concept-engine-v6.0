#!/usr/bin/env python3
"""太极概念字典 · 自动推演脚本
输入：新字列表 → 输出：兼容 concept_dict.json 的完整条目
用法：python auto_deduce.py <input.txt> [--output entries.json]
"""

import json, math, sys, os

# 八卦标准向量
GUA = {
    '乾☰': (0.9,0.8,0.7,0.9,0.1,0.1,0.3,0.8), '兑☱': (0.4,0.5,0.8,0.5,0.6,0.4,0.3,0.5),
    '离☲': (0.5,0.4,0.3,0.3,0.7,0.6,0.9,0.2), '震☳': (0.7,0.9,0.4,0.2,0.4,0.3,0.5,0.3),
    '巽☴': (0.2,0.5,0.1,0.4,0.9,0.9,0.3,0.1), '坎☵': (0.4,0.3,0.5,0.6,0.7,0.8,0.2,0.6),
    '艮☶': (0.5,0.2,0.9,0.8,0.1,0.1,0.2,0.9), '坤☷': (0.5,0.1,0.4,0.9,0.1,0.2,0.3,0.8),
}

WX_MAP = {'乾☰':'阳金','兑☱':'阴金','离☲':'火','震☳':'阳木','巽☴':'阴木','坎☵':'水','艮☶':'阳土','坤☷':'阴土'}
SHENG = {'阳金':'水','阴金':'水','火':'土','阳木':'火','阴木':'火','水':'木','阳土':'金','阴土':'金'}
KE = {'阳金':'木','阴金':'木','火':'金','阳木':'土','阴木':'土','水':'火','阳土':'水','阴土':'水'}
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']

def norm(v): return math.sqrt(sum(x*x for x in v))

def deduce(char, gua_str):
    """为单个字推演完整字典条目"""
    wx = WX_MAP[gua_str]
    vec = GUA[gua_str]
    return {
        '卦象': gua_str,
        '五行': wx,
        '属性': dict(zip(DIMS, vec)),
        '阴阳振幅': round(norm(vec)/1.543, 2),
        '我生': SHENG[wx], '我克': KE[wx],
        '生我': [k for k,v in SHENG.items() if v==wx],
        '克我': [k for k,v in KE.items() if v==wx],
        'baseline_vector': dict(zip(DIMS, vec)),
        'drift_state': 'stable',
        'drift_delta': 0.0,
        'interaction_count': 0
    }

# 推演策略：根据五行+语义推断阴阳
# 金: 硬/重/固定→乾☰(阳金) | 锋/利/装饰→兑☱(阴金)
# 木: 大树/硬→震☳(阳木) | 草/藤/柔软→巽☴(阴木)
# 土: 山/石/边界→艮☶(阳土) | 地/尘/形态→坤☷(阴土)

def auto_classify(char):
    """自动推断卦象。返回 (卦象, 置信度, 理由)"""
    # 默认按语义特征推断
    hard_metal = set('钢铁铜银锻铸钧铠钟铃铛镇鉴')
    soft_metal = set('锋刀剑刃针钉锥铲钩镰钗锦绣镶镀错')
    hard_wood  = set('树松柏竹槐榆杨桐杉榕樟橡檀')
    soft_wood  = set('草藤蔓花叶莲荷菊兰芝艾蔬菜芽苗茎笋')
    earth_solid= set('山岩石壁城墙塔碑坛丘陵垣')
    earth_loose= set('地尘沙土壤田坡坑坯胎壳模')
    fire_group = set('火焰烧燃灯烛爆炸灿烂辉煌照耀烁炫煜灼灸烤烘')
    water_group= set('水海江河湖渊泉溪涧潭瀑波浪潮涌流滴雨雪冰露霜雾潜溺')

    return None  # 需要人工指定

if __name__ == '__main__':
    print('太极概念字典 · 自动推演脚本')
    print('用法: python auto_deduce.py')
    print()
    print('示例——推演一个字:')
    print()
    entry = deduce('道', '乾☰')
    print(json.dumps(entry, ensure_ascii=False, indent=2))
