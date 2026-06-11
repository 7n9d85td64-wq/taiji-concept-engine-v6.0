#!/usr/bin/env python3
"""
CCP 知识令牌锚定工具
用法一（交互）: python anchor.py
用法二（批量）: python anchor.py --content "你的结论" --axioms "公理1" "公理2" --against "反例" --steps "步骤1" "步骤2" --confidence 0.85
用法三（一键）: python anchor.py --auto
"""
import json, urllib.request, argparse, sys, subprocess, os

BASE = "http://localhost:8741"
CONTEXT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_token_context.md")

def anchor(content, axioms, counter_examples, derivation, confidence):
    payload = json.dumps({
        "content": content,
        "axiom_transparency": list(axioms),
        "counter_examples": list(counter_examples),
        "derivation": list(derivation),
        "confidence": float(confidence)
    }, ensure_ascii=False).encode("utf-8")
    
    req = urllib.request.Request(
        f"{BASE}/token/anchor", data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def export_context():
    with urllib.request.urlopen(f"{BASE}/context/all") as resp:
        ctx = json.loads(resp.read())
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        f.write(ctx["context"])
    return ctx["token_count"], len(ctx["context"])

def upload_to_ima():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    upload_script = os.path.join(script_dir, "upload_all_to_ima.py")
    if os.path.exists(upload_script):
        subprocess.run([sys.executable, upload_script], cwd=script_dir)
        return True
    return False

def interactive():
    print("CCP 知识令牌锚定 · 交互模式\n")
    
    content = input("结论（核心观点）：").strip()
    if not content:
        print("结论不能为空。")
        return
    
    print("\n公理（底层假设，每行一条，空行结束）：")
    axioms = []
    while True:
        a = input(f"  公理 {len(axioms)+1}: ").strip()
        if not a:
            break
        axioms.append(a)
    
    print("\n反例（什么情况下可能错，空行结束）：")
    counter_examples = []
    while True:
        c = input(f"  反例 {len(counter_examples)+1}: ").strip()
        if not c:
            break
        counter_examples.append(c)
    
    print("\n推导步骤（每行一步，空行结束）：")
    derivation = []
    while True:
        d = input(f"  步骤 {len(derivation)+1}: ").strip()
        if not d:
            break
        derivation.append(d)
    
    conf_input = input("\n置信度 (0-1, 默认0.85): ").strip()
    confidence = float(conf_input) if conf_input else 0.85
    
    return do_anchor(content, axioms, counter_examples, derivation, confidence)

def do_anchor(content, axioms, counter_examples, derivation, confidence):
    try:
        result = anchor(content, axioms, counter_examples, derivation, confidence)
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"\n✗ 锚定被拒绝")
        print(f"  层: {err.get('layer', '?')}")
        print(f"  原因: {err.get('error', str(e))}")
        return False
    except Exception as e:
        print(f"\n✗ 连接失败: {e}")
        print(f"  确认服务器在运行: python token_server.py")
        return False
    
    print(f"\n✓ 锚定成功")
    print(f"  令牌: {result['token_id']}")
    print(f"  置信度: {result.get('confidence', confidence)}")
    if result.get('warnings'):
        for w in result['warnings']:
            print(f"  ⚠ {w}")
    
    # Auto-export
    n, size = export_context()
    print(f"  上下文已导出: {n} 令牌, {size} 字符")
    
    # Auto-upload
    if upload_to_ima():
        print(f"  已推送到 IMA 知识库")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CCP 知识令牌锚定工具")
    parser.add_argument("--content", help="核心结论")
    parser.add_argument("--axioms", nargs="*", help="公理列表")
    parser.add_argument("--against", nargs="*", help="反例列表")
    parser.add_argument("--steps", nargs="*", help="推导步骤")
    parser.add_argument("--confidence", type=float, default=0.85, help="置信度 (0-1)")
    parser.add_argument("--auto", action="store_true", help="从 last_anchor.txt 读取上次内容")
    args = parser.parse_args()
    
    if args.auto:
        auto_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_anchor.txt")
        if os.path.exists(auto_file):
            with open(auto_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            do_anchor(
                data.get("content", ""),
                data.get("axioms", []),
                data.get("against", []),
                data.get("steps", []),
                data.get("confidence", 0.85)
            )
        else:
            print("无上次锚定记录。先用 --content 手动锚定一次。")
    elif args.content:
        do_anchor(
            args.content,
            args.axioms or [],
            args.against or [],
            args.steps or [],
            args.confidence
        )
    else:
        interactive()
