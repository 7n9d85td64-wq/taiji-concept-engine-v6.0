"""v5.0 锚点重置：标记514个原始概念为锚点，重置465个drift_corrected为元态"""
import json
from collections import Counter

with open('concept_dict.json', encoding='utf-8') as f:
    d = json.load(f)

DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']
META_MEAN = {
    '力量感': 0.51, '方向性': 0.46, '边界性': 0.51, '持续性': 0.58,
    '灵动性': 0.45, '渗透性': 0.43, '温度': 0.38, '密度': 0.53
}

# 识别原始概念（classify_state不是drift_corrected也不是meta的）
# 它们已有正确的卦象/五行/生克/8维向量
anchors = []
to_reset = []
already_meta = []

for ch, c in d['concepts'].items():
    if c.get('classify_state') == 'drift_corrected':
        to_reset.append(ch)
    elif c.get('classify_state') == 'meta':
        already_meta.append(ch)
    else:
        # classify_state 为 None 或 '?' — 原始分类概念
        anchors.append(ch)

# 标记锚点
for ch in anchors:
    c = d['concepts'][ch]
    c['classify_state'] = 'anchor'
    c['drift_state'] = 'stable'
    c['drift_delta'] = 0.0
    c['interaction_count'] = 0
    # 确保生克关系完整
    if '我生' not in c or '我克' not in c:
        bare_map = {
            '金':'金','木':'木','水':'水','火':'火','土':'土',
            '阳金':'金','阴金':'金','阳木':'木','阴木':'木',
            '阳土':'土','阴土':'土'
        }
        SHENG = {'金':'水','木':'火','水':'木','火':'土','土':'金'}
        KE   = {'金':'木','木':'土','水':'火','火':'金','土':'水'}
        b = bare_map.get(c['五行'], c['五行'])
        c['我生'] = SHENG.get(b, '?')
        c['我克'] = KE.get(b, '?')
        c['生我'] = [k for k,v in SHENG.items() if v==b]
        c['克我'] = [k for k,v in KE.items() if v==b]
    c.pop('auto_confidence', None)
    c.pop('gravity_top3', None)
    c.pop('needs_activation', None)
    c.pop('activation_params', None)

# 重置 drift_corrected 为元态（同时重置向量为均值）
for ch in to_reset:
    c = d['concepts'][ch]
    c['卦象'] = '元'
    c['五行'] = '不定'
    c['属性'] = {k: round(v, 4) for k, v in META_MEAN.items()}
    c['baseline_vector'] = {k: round(v, 4) for k, v in META_MEAN.items()}
    c['classify_state'] = 'meta'
    c['drift_state'] = 'baseline'
    c['drift_delta'] = 0.0
    c['interaction_count'] = 0
    c.pop('auto_confidence', None)
    c.pop('gravity_top3', None)
    c.pop('我生', None)
    c.pop('我克', None)
    c.pop('生我', None)
    c.pop('克我', None)
    c.pop('needs_activation', None)
    c.pop('activation_params', None)
    c.pop('_anchor', None)
    c.pop('_anchor_gua', None)
    c.pop('_anchor_coupling', None)

# 对已有 meta 也做同样处理（重置向量）
for ch in already_meta:
    c = d['concepts'][ch]
    c['属性'] = {k: round(v, 4) for k, v in META_MEAN.items()}
    c['baseline_vector'] = {k: round(v, 4) for k, v in META_MEAN.items()}
    c['classify_state'] = 'meta'
    c['drift_state'] = 'baseline'
    c['drift_delta'] = 0.0
    c['interaction_count'] = 0
    c.pop('_anchor', None)
    c.pop('_anchor_gua', None)
    c.pop('_anchor_coupling', None)

# 清除记录
d.pop('_drift_processed', None)
d.pop('_drift_text', None)
d.pop('_last_activation', None)

with open('concept_dict.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

# 验证
from collections import Counter
cs = Counter(c.get('classify_state', '?') for c in d['concepts'].values())
cc = Counter(c['卦象'] for c in d['concepts'].values())
print(f'classify_state: {dict(cs)}')
print(f'锚点: {len(anchors)}')
print(f'元态: {len(to_reset) + len(already_meta)}')

# 锚点卦象分布
ac = Counter(d['concepts'][ch]['卦象'] for ch in anchors)
print('\n锚点分布:')
for gua in ['乾☰','兑☱','离☲','震☳','巽☴','坎☵','艮☶','坤☷']:
    print(f'  {gua}: {ac.get(gua, 0)}')

# 锚点五行分布
wx = Counter(d['concepts'][ch]['五行'] for ch in anchors)
print(f'\n锚点五行: {dict(wx)}')

print(f'\n总计: {len(d["concepts"])}')
print(f'元态(待引导): {len(to_reset) + len(already_meta)}')
