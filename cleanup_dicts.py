#!/usr/bin/env python3
"""
Task 17: 字典版本清理
删除所有 v5.3 之前的旧版备份，保留 v5.3（已校准）和当前工作版本。

用法：
    python cleanup_dicts.py                    # 扫描并列出所有版本
    python cleanup_dicts.py --execute          # 执行删除
"""

import os, sys, glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 受保护的文件（不删除）
PROTECTED = [
    'concept_dict.json',          # 当前工作版本
    'concept_dict_v5.3.json',     # v5.3 已校准版本
]

def find_dict_versions():
    """扫描所有概念字典版本文件"""
    versions = []

    # 精确匹配模式
    patterns = [
        'concept_dict*.json',
        'concept_dict_v*.json',
    ]

    for pattern in patterns:
        for fpath in glob.glob(os.path.join(SCRIPT_DIR, pattern)):
            fname = os.path.basename(fpath)
            if fname in PROTECTED:
                continue
            mtime = os.path.getmtime(fpath)
            versions.append((fpath, fname, mtime))

    # 去重并按修改时间排序
    versions = sorted(versions, key=lambda x: x[2])

    return versions


def list_versions():
    """列出所有版本"""
    versions = find_dict_versions()
    protected_in_dir = [os.path.join(SCRIPT_DIR, p) for p in PROTECTED
                        if os.path.exists(os.path.join(SCRIPT_DIR, p))]

    print('═══ 字典版本扫描 ═══')
    print(f'\n🛡️ 受保护文件（保留）:')
    for p in protected_in_dir:
        mtime = os.path.getmtime(p)
        size = os.path.getsize(p)
        print(f'  {os.path.basename(p)} ({size:,} bytes, {_format_time(mtime)})')

    print(f'\n🗑️ 可清理文件:')
    if not versions:
        print('  无需清理')
    for fpath, fname, mtime in versions:
        size = os.path.getsize(fpath)
        print(f'  {fname} ({size:,} bytes, {_format_time(mtime)})')

    print(f'\n总计: {len(protected_in_dir)} 保留 + {len(versions)} 可清理')
    return versions


def execute_cleanup():
    """执行删除"""
    versions = find_dict_versions()
    if not versions:
        print('✅ 无需清理')
        return

    print(f'⚠️ 将删除 {len(versions)} 个旧版本文件:')
    for fpath, fname, mtime in versions:
        print(f'  - {fname}')

    confirm = input('\n确认删除？输入 yes: ').strip().lower()
    if confirm != 'yes':
        print('取消')
        return

    deleted = 0
    errors = 0
    for fpath, fname, _ in versions:
        try:
            os.remove(fpath)
            deleted += 1
            print(f'  ✅ 已删除: {fname}')
        except OSError as e:
            errors += 1
            print(f'  ❌ 删除失败: {fname} ({e})')

    print(f'\n完成: {deleted} 删除, {errors} 失败')


def _format_time(ts):
    import time
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))


if __name__ == '__main__':
    if '--execute' in sys.argv:
        execute_cleanup()
    else:
        list_versions()
        print('\n💡 提示: 加 --execute 执行删除')
