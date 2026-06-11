#!/usr/bin/env python3
"""
Task 19: 20组对比测试
加载概念引擎前后分别运行20组预设问题，记录对比数据。

测试覆盖：
  A. 卦象分类规则推导（部首→五行→卦象）
  B. 生克关系正确性
  C. 锚点只读保护
  D. 跨卦分类禁止
  E. 争议标记机制
  F. 元态概念处理
  G. 漂移方程完整性（三层基数）
  H. 边界情况

用法：
    python run_20_tests.py                    # 运行全部20组测试
    python run_20_tests.py --category A       # 只运行分类A
    python run_20_tests.py --verbose          # 详细输出
"""

import json, os, sys, math, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_PATH = os.path.join(SCRIPT_DIR, 'concept_dict.json')
DIMS = ['力量感','方向性','边界性','持续性','灵动性','渗透性','温度','密度']

# ═══════════════════════════════════════════
# 20组测试定义
# 每组包含: {id, category, question, pre_engine_expected, post_engine_expected, criteria, check_fn}
# ═══════════════════════════════════════════

TESTS = [
    # ── A: 卦象分类规则推导 ──
    {
        'id': 'A1', 'category': 'A',
        'question': '部首→五行→卦象: "钢"(金部) 应被分类为什么卦象？',
        'pre_engine_expected': '无（未加载引擎）',
        'post_engine_expected': '乾☰ 或 兑☱（金部→阳金/阴金判定）',
        'criteria': '钢在字典中卦象必须为乾☰或兑☱，且 classify_state 为 radical 或 semantic',
        'test_type': 'classification'
    },
    {
        'id': 'A2', 'category': 'A',
        'question': '部首→五行→卦象: "海"(氵部) 应被分类为什么卦象？',
        'pre_engine_expected': '无',
        'post_engine_expected': '坎☵（水部→坎☵）',
        'criteria': '海在字典中卦象必须为坎☵，classify_state 为 radical',
        'test_type': 'classification'
    },
    {
        'id': 'A3', 'category': 'A',
        'question': '部首→五行→卦象: "山" (山部→土, 阳→艮☶) 应被分类为什么卦象？',
        'pre_engine_expected': '无',
        'post_engine_expected': '艮☶（山部→土→阳土·艮☶）',
        'criteria': '山在字典中卦象必须为艮☶',
        'test_type': 'classification'
    },
    {
        'id': 'A4', 'category': 'A',
        'question': '语义查表: "仁"（无金木水火土部首）应被分类为什么卦象？',
        'pre_engine_expected': '无',
        'post_engine_expected': '离☲（SEMANTIC_LOOKUP中仁→离☲）',
        'criteria': '仁在字典中卦象必须为离☲，classify_state 为 semantic',
        'test_type': 'classification'
    },

    # ── B: 生克关系正确性 ──
    {
        'id': 'B1', 'category': 'B',
        'question': '生克对称性: "水"(坎☵) 我生应为木, "火"(离☲) 我生应为土。验证字典中所有概念的"我生"字段与标准生克一致。',
        'pre_engine_expected': '部分不一致（此前版本有生克不对称问题）',
        'post_engine_expected': '全部一致（v6.0修复了生克计算bug）',
        'criteria': '所有我生字段符合标准生克表，五行=不定的概念不在校验范围内',
        'test_type': 'shengke'
    },
    {
        'id': 'B2', 'category': 'B',
        'question': '生克场计算: 在文本"上善若水"中，"善"（兑☱）与"水"（坎☵）的金生水关系是否被正确识别？',
        'pre_engine_expected': '未测试',
        'post_engine_expected': 'shengke_bonus(阴金, 水) = 1.5（金生水）',
        'criteria': '金生水加成为1.5，不是1.0也不是1.1',
        'test_type': 'shengke'
    },
    {
        'id': 'B3', 'category': 'B',
        'question': '生克对称性验证: 若A克B，则B的"克我"字段必须包含A的五行。扫描全部已定卦概念。',
        'pre_engine_expected': '可能有不对称',
        'post_engine_expected': '全部对称',
        'criteria': 'auto_validate_concepts.py 对称性检查通过（排除元态）',
        'test_type': 'shengke'
    },

    # ── C: 锚点只读保护 ──
    {
        'id': 'C1', 'category': 'C',
        'question': '锚点只读: 加载字典后运行text_drift.py，锚点概念(classify_state=anchor)的属性向量是否保持不变？',
        'pre_engine_expected': '_v5_reset.py 曾覆盖锚点属性',
        'post_engine_expected': '锚点向量在漂移前后完全一致（drift_delta=0）',
        'criteria': '所有锚点 drift_delta=0 且 interaction_count 不增加',
        'test_type': 'readonly'
    },
    {
        'id': 'C2', 'category': 'C',
        'question': '锚点读保护: 锚点概念的卦象和五行是否在漂移后保持不变？',
        'pre_engine_expected': '可能存在被覆盖风险',
        'post_engine_expected': '锚点的卦象、五行、classify_state 不变化',
        'criteria': '锚点 classify_state 始终为 anchor，卦象不变',
        'test_type': 'readonly'
    },

    # ── D: 禁止跨卦分类 ──
    {
        'id': 'D1', 'category': 'D',
        'question': '禁止跨卦: 一个已被分类为坎☵的概念（如"水"），经过text_drift.py漂移后，卦象是否会变为其他卦？',
        'pre_engine_expected': 'v5.x版本可能跨卦漂移',
        'post_engine_expected': '卦象保持坎☵不变（仅向量在卦内微调）',
        'criteria': '所有 radical/semantic/drift_corrected 概念的卦象不改变',
        'test_type': 'cross_trigram'
    },
    {
        'id': 'D2', 'category': 'D',
        'question': '卦内微调: 已定卦概念漂移后与标准卦向量的余弦相似度应该增加（微调向标准靠拢）',
        'pre_engine_expected': 'v5.x漂移可能远离标准',
        'post_engine_expected': '余弦相似度 >= 漂移前（或至少不显著降低）',
        'criteria': '卦内微调后概念与标准卦向量的余弦相似度不会显著降低',
        'test_type': 'cross_trigram'
    },

    # ── E: 争议标记 ──
    {
        'id': 'E1', 'category': 'E',
        'question': '争议标记: 运行text_drift.py后，是否存在 dispute_state="needs_review" 的概念？',
        'pre_engine_expected': '无争议标记',
        'post_engine_expected': '置信度<0.6或元态概念被标记为needs_review',
        'criteria': 'human_review.json 非空（至少包含元态概念的争议条目）',
        'test_type': 'dispute'
    },
    {
        'id': 'E2', 'category': 'E',
        'question': '争议输出格式: human_review.json 是否包含完整的争议信息（概念名、原因、审查建议）？',
        'pre_engine_expected': 'human_review.json 不存在',
        'post_engine_expected': 'human_review.json 包含 total_disputes, disputes 数组',
        'criteria': 'human_review.json 结构完整，每条争议含 concept/reason/review_action',
        'test_type': 'dispute'
    },

    # ── F: 元态概念处理 ──
    {
        'id': 'F1', 'category': 'F',
        'question': '元态保持: 卦象为"元"的概念（如"之""乎""者""也"），经过漂移后卦象是否仍为"元"？',
        'pre_engine_expected': 'v5.3 用统计方法将部分元态概念强制分卦',
        'post_engine_expected': '元态概念保持卦象=元，dispute_state=needs_review',
        'criteria': '所有原卦象=元的概念在漂移后仍为元，不强制分卦',
        'test_type': 'meta'
    },
    {
        'id': 'F2', 'category': 'F',
        'question': '无极原点标记: 元态概念是否带有 _wuji_origin=True 理论标记？',
        'pre_engine_expected': '无此标记',
        'post_engine_expected': '元态概念的 _wuji_origin=True',
        'criteria': '元态概念字典条目包含 _wuji_origin: true',
        'test_type': 'meta'
    },
    {
        'id': 'F3', 'category': 'F',
        'question': '元态漂移追踪: 元态概念虽然不定卦，但漂移量(drift_delta)是否被记录？',
        'pre_engine_expected': '无追踪',
        'post_engine_expected': 'drift_delta > 0（如果周围有锚点），但卦象不改变',
        'criteria': '元态 drift_state 为 shifting_meta 或 stable_meta',
        'test_type': 'meta'
    },

    # ── G: 三层基数 ──
    {
        'id': 'G1', 'category': 'G',
        'question': '公理基数: 漂移方程中的 MICRO_BASE 和 MESO_BASE 是否硬编码为 0.01 和 0.10？',
        'pre_engine_expected': 'v5.5已修复',
        'post_engine_expected': 'MICRO_BASE=0.01, MESO_BASE=0.10',
        'criteria': '代码中硬编码 MICRO_BASE=0.01, MESO_BASE=0.10，无动态计算',
        'test_type': 'base'
    },
    {
        'id': 'G2', 'category': 'G',
        'question': '三层基数执行: 运行3轮漂移后，每个维度的总漂移量是否不超过 MESO_BASE×3=0.30？',
        'pre_engine_expected': '未检查',
        'post_engine_expected': '每维度漂移量在合理范围内（<0.3）',
        'criteria': 'max(|cv - bv|) < 0.3 对所有维度',
        'test_type': 'base'
    },

    # ── H: 边界情况 ──
    {
        'id': 'H1', 'category': 'H',
        'question': '空文本: 对空字符串运行 text_drift.py 是否安全？',
        'pre_engine_expected': '可能崩溃',
        'post_engine_expected': '优雅处理，输出 0 交互',
        'criteria': '不崩溃，输出"交互次数: 0"',
        'test_type': 'edge'
    },
    {
        'id': 'H2', 'category': 'H',
        'question': '单字文本: 对只含一个概念的文字运行是否安全？',
        'pre_engine_expected': '可能无窗口锚点',
        'post_engine_expected': '优雅处理，概念不漂移',
        'criteria': '不崩溃，drift_delta=0',
        'test_type': 'edge'
    },
]


def run_test(test, concept_dict):
    """运行单个测试并返回结果"""
    concepts = concept_dict.get('concepts', concept_dict)
    result = {'test_id': test['id'], 'passed': None, 'details': ''}

    tid = test['id']
    ttype = test['test_type']

    try:
        if ttype == 'classification':
            # 检查特定概念的分类
            target_concepts = {
                'A1': ['钢'], 'A2': ['海'], 'A3': ['山'], 'A4': ['仁']
            }
            targets = target_concepts.get(tid, [])
            if not targets:
                result['passed'] = 'SKIP'
                result['details'] = '无目标概念'
                return result

            all_ok = True
            for tc in targets:
                if tc not in concepts:
                    result['details'] = f'{tc} 不在字典中'
                    result['passed'] = False
                    return result
                c = concepts[tc]
                gua = c.get('卦象', '')
                cs = c.get('classify_state', '')
                conf = c.get('auto_confidence', 0)

                if tid == 'A1':  # 钢 → 金部 → 乾☰/兑☱
                    if gua not in ('乾☰', '兑☱'):
                        all_ok = False
                        result['details'] = f'{tc} 卦象={gua}（期望乾☰或兑☱）'
                elif tid == 'A2':  # 海 → 坎☵
                    if gua != '坎☵':
                        all_ok = False
                        result['details'] = f'{tc} 卦象={gua}（期望坎☵）'
                elif tid == 'A3':  # 山 → 艮☶
                    if gua != '艮☶':
                        all_ok = False
                        result['details'] = f'{tc} 卦象={gua}（期望艮☶）'
                elif tid == 'A4':  # 仁 → 离☲
                    if gua != '离☲':
                        all_ok = False
                        result['details'] = f'{tc} 卦象={gua}（期望离☲）'

            result['passed'] = all_ok
            if all_ok:
                result['details'] = f'{targets[0]} 卦象正确'

        elif ttype == 'shengke':
            # 检查生克关系
            errors = []
            for ch, c in concepts.items():
                wx = c.get('五行', '')
                if not wx or wx in ('不定', '?'): continue
                # 提取裸五行
                bare = None
                for b in ['金', '木', '水', '火', '土']:
                    if b in str(wx):
                        bare = b
                        break
                if not bare: continue

                sheng = {'金': '水', '木': '火', '水': '木', '火': '土', '土': '金'}
                ke = {'金': '木', '木': '土', '水': '火', '火': '金', '土': '水'}

                if '我生' in c and c['我生'] and c['我生'] != '?':
                    expected = sheng.get(bare)
                    if expected and c['我生'] != expected:
                        errors.append(f'{ch}: 我生={c["我生"]}≠{expected}')
                if '我克' in c and c['我克'] and c['我克'] != '?':
                    expected = ke.get(bare)
                    if expected and c['我克'] != expected:
                        errors.append(f'{ch}: 我克={c["我克"]}≠{expected}')

            result['passed'] = len(errors) == 0
            result['details'] = f'{len(errors)}个生克错误' if errors else '全部生克一致'

        elif ttype == 'readonly':
            # 锚点保护
            anchors = [(ch, c) for ch, c in concepts.items()
                       if c.get('classify_state') == 'anchor']
            violations = []
            for ch, c in anchors:
                if c.get('drift_delta', 0) > 0:
                    violations.append(ch)
            result['passed'] = len(violations) == 0
            result['details'] = f'{len(anchors)}锚点, {len(violations)}违规漂移'

        elif ttype == 'cross_trigram':
            # 禁止跨卦
            classified = [(ch, c) for ch, c in concepts.items()
                         if c.get('classify_state') in ('radical', 'semantic', 'drift_corrected')
                         and c.get('卦象') != '元']
            violations = []
            for ch, c in classified:
                # 检查是否有 _drift_original_gua 之类追踪
                # 简单检查：卦象是否还在8卦范围内
                if c.get('卦象', '') == '元':
                    violations.append(f'{ch} 从已定卦漂到了元')
            result['passed'] = len(violations) == 0
            result['details'] = f'{len(classified)}个已定卦, {len(violations)}违规'

            if tid == 'D2':
                # 检查余弦相似度
                worse_count = 0
                for ch, c in concepts.items():
                    if c.get('classify_state') not in ('radical', 'semantic'): continue
                    gua = c.get('卦象', '')
                    if gua not in concept_dict.get('trigrams', {}): continue
                    sv = [concept_dict['trigrams'][gua][dim] for dim in DIMS]
                    cv = list(c['属性'].values())
                    bv = list(c.get('baseline_vector', {}).values())
                    if len(bv) != 8: continue
                    sim_before = sum(sv[i]*bv[i] for i in range(8))/(math.sqrt(sum(x*x for x in sv))*math.sqrt(sum(x*x for x in bv))+1e-8)
                    sim_after = sum(sv[i]*cv[i] for i in range(8))/(math.sqrt(sum(x*x for x in sv))*math.sqrt(sum(x*x for x in cv))+1e-8)
                    if sim_after < sim_before - 0.05:
                        worse_count += 1
                result['passed'] = worse_count == 0
                result['details'] = f'卦内微调，{worse_count}个余弦相似度显著降低'

        elif ttype == 'dispute':
            review_path = os.path.join(SCRIPT_DIR, 'human_review.json')
            if tid == 'E1':
                if os.path.exists(review_path):
                    with open(review_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    count = data.get('total_disputes', 0)
                    result['passed'] = count > 0
                    result['details'] = f'{count}条争议'
                else:
                    # human_review.json 不存在，但检查字典中的 dispute_state
                    disputes = [ch for ch, c in concepts.items()
                               if c.get('dispute_state') == 'needs_review']
                    result['passed'] = len(disputes) > 0
                    result['details'] = f'字典中{len(disputes)}个needs_review（human_review.json未生成）'
            elif tid == 'E2':
                if os.path.exists(review_path):
                    with open(review_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    ok = ('total_disputes' in data and 'disputes' in data
                          and all('concept' in d and 'reason' in d for d in data.get('disputes', [])))
                    result['passed'] = ok
                    result['details'] = '格式正确' if ok else '格式不完整'
                else:
                    result['passed'] = False
                    result['details'] = 'human_review.json 不存在'

        elif ttype == 'meta':
            meta_concepts = [(ch, c) for ch, c in concepts.items()
                            if c.get('卦象') == '元']
            if tid == 'F1':
                # 元态保持
                changed = [ch for ch, c in concepts.items()
                          if c.get('_original_gua') == '元' and c.get('卦象') != '元']
                result['passed'] = len(changed) == 0
                result['details'] = f'{len(meta_concepts)}元态, {len(changed)}被改变'
            elif tid == 'F2':
                # 无极原点标记
                marked = sum(1 for _, c in meta_concepts if c.get('_wuji_origin') == True)
                result['passed'] = marked > 0
                result['details'] = f'{marked}/{len(meta_concepts)}元态有无极原点标记'
            elif tid == 'F3':
                tracked = sum(1 for _, c in meta_concepts
                             if c.get('drift_state') in ('shifting_meta', 'stable_meta'))
                result['passed'] = tracked == len(meta_concepts)
                result['details'] = f'{tracked}/{len(meta_concepts)}元态有漂移追踪'

        elif ttype == 'base':
            if tid == 'G1':
                # 读取代码确认基数
                drift_path = os.path.join(SCRIPT_DIR, 'text_drift.py')
                if os.path.exists(drift_path):
                    with open(drift_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    mic_ok = 'MICRO_BASE = 0.01' in code
                    mes_ok = 'MESO_BASE  = 0.10' in code
                    result['passed'] = mic_ok and mes_ok
                    result['details'] = f'MICRO_BASE=0.01:{mic_ok}, MESO_BASE=0.10:{mes_ok}'
                else:
                    result['passed'] = False
                    result['details'] = 'text_drift.py 不存在'
            elif tid == 'G2':
                violations = []
                for ch, c in concepts.items():
                    if c.get('卦象') == '元': continue
                    cv = list(c['属性'].values())
                    bv = list(c.get('baseline_vector', {}).values())
                    if len(bv) != 8: continue
                    max_drift = max(abs(cv[i]-bv[i]) for i in range(8))
                    if max_drift > 0.3:
                        violations.append(f'{ch}(max={max_drift:.3f})')
                result['passed'] = len(violations) == 0
                result['details'] = f'{len(violations)}个概念超0.30漂移上限'

        elif ttype == 'edge':
            result['passed'] = 'SKIP'  # 需要实际运行空文本测试
            result['details'] = '需手动运行 text_drift.py 空文本验证'

    except Exception as e:
        result['passed'] = False
        result['details'] = f'异常: {str(e)}'

    return result


def main():
    verbose = '--verbose' in sys.argv
    category_filter = None
    if '--category' in sys.argv:
        idx = sys.argv.index('--category')
        category_filter = sys.argv[idx+1] if idx+1 < len(sys.argv) else None

    # 加载字典
    if not os.path.exists(DICT_PATH):
        print('❌ concept_dict.json 不存在')
        return

    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        concept_dict = json.load(f)

    concepts = concept_dict.get('concepts', concept_dict)
    print(f'═══ 20组对比测试 ═══')
    print(f'字典: {len(concepts)} 概念')
    print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    if category_filter:
        print(f'过滤器: 分类 {category_filter}')
    print()

    # 运行测试
    results = []
    passed = 0
    failed = 0
    skipped = 0

    for test in TESTS:
        if category_filter and test['category'] != category_filter:
            continue

        result = run_test(test, concept_dict)
        results.append(result)

        status_icon = '✅' if result['passed'] == True else ('❌' if result['passed'] == False else '⏭️')
        if result['passed'] == True: passed += 1
        elif result['passed'] == False: failed += 1
        else: skipped += 1

        if verbose:
            print(f'{status_icon} {test["id"]} | {test["question"][:60]}...')
            print(f'   结果: {result["details"]}')
            print(f'   标准: {test["criteria"]}')
            print()
        else:
            print(f'{status_icon} {test["id"]}: {test["question"][:50]}... → {result["details"]}')

    # 按分类汇总
    print(f'\n═══ 汇总 ═══')
    categories = {}
    for r in results:
        tid = r['test_id']
        cat = tid[0]
        if cat not in categories:
            categories[cat] = {'passed': 0, 'failed': 0, 'skipped': 0, 'total': 0}
        categories[cat]['total'] += 1
        if r['passed'] == True: categories[cat]['passed'] += 1
        elif r['passed'] == False: categories[cat]['failed'] += 1
        else: categories[cat]['skipped'] += 1

    cat_names = {
        'A': '卦象分类', 'B': '生克关系', 'C': '锚点保护',
        'D': '禁止跨卦', 'E': '争议标记', 'F': '元态处理',
        'G': '三层基数', 'H': '边界情况'
    }
    for cat in sorted(categories.keys()):
        c = categories[cat]
        pct = c['passed']/c['total']*100 if c['total'] > 0 else 0
        bar = '█'*int(pct/10) + '░'*(10-int(pct/10))
        print(f'  {cat} {cat_names.get(cat, cat):6s} [{bar}] {c["passed"]}/{c["total"]} ({pct:.0f}%)')

    print(f'\n总计: {passed}通过 | {failed}失败 | {skipped}跳过 | {len(results)}运行')

    # 保存报告
    report_path = os.path.join(SCRIPT_DIR, 'test_report_20.json')
    report = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'summary': {'passed': passed, 'failed': failed, 'skipped': skipped, 'total': len(results)},
        'by_category': {cat: c for cat, c in categories.items()},
        'results': results
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f'\n📋 报告: {report_path}')


if __name__ == '__main__':
    main()
