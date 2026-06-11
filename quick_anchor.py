#!/usr/bin/env python3
"""
CCP 快速锚定工具
接收 AI 生成的 JSON 令牌文件，一键锚定。
"""
import json, urllib.request, sys, os, subprocess

BASE = "http://localhost:8741"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "_pending_token.json")
CONTEXT_FILE = os.path.join(SCRIPT_DIR, "_token_context.md")

def anchor_from_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        token = json.load(f)
    
    # Ensure required fields
    for field in ["content", "axiom_transparency", "counter_examples", "derivation"]:
        if field not in token:
            print(f"✗ 缺少字段: {field}")
            return False
    
    if "confidence" not in token:
        token["confidence"] = 0.85
    
    payload = json.dumps(token, ensure_ascii=False).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{BASE}/token/anchor", data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"✗ 拒绝 [{err.get('layer','?')}]: {err.get('error', str(e))}")
        return False
    except Exception as e:
        print(f"✗ 服务器未启动? {e}")
        return False
    
    print(f"✓ 令牌: {result['token_id']}")
    print(f"  置信度: {result.get('confidence', '?')}")
    for w in result.get('warnings', []):
        print(f"  ⚠ {w}")
    
    # Export
    with urllib.request.urlopen(f"{BASE}/context/all") as resp:
        ctx = json.loads(resp.read())
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        f.write(ctx["context"])
    print(f"  上下文: {ctx['token_count']} 令牌")
    
    # Upload
    upload_script = os.path.join(SCRIPT_DIR, "upload_all_to_ima.py")
    if os.path.exists(upload_script):
        subprocess.run([sys.executable, upload_script], cwd=SCRIPT_DIR)
        print("  IMA: 已推送")
    
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=TOKEN_FILE)
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()
    
    if args.stdin:
        data = sys.stdin.read()
        fp = os.path.join(SCRIPT_DIR, "_stdin_token.json")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(data)
        print("管道输入 → 锚定...")
        anchor_from_file(fp)
    elif args.paste:
        print("粘贴 JSON，Ctrl+Z 回车：")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        fp = os.path.join(SCRIPT_DIR, "_paste_token.json")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        anchor_from_file(fp)
    else:
        fp = args.file
        if not os.path.exists(fp):
            print(f"文件不存在: {fp}")
            print("用法: python quick_anchor.py [文件] | --stdin | --paste")
            sys.exit(1)
        anchor_from_file(fp)
