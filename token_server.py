"""
认知契约协议 · 令牌服务器
Cognitive Contract Protocol Token Server

用法：
  pip install cognicontract
  cognicontract serve              → http://localhost:8741
  cognicontract anchor "结论"     → 锚定共识
  cognicontract context            → 打印令牌上下文
  cognicontract test               → 自检
"""

import json, hashlib, datetime, os
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

TOKEN_DIR = Path.home() / ".cognicontract" / "tokens"
TOKEN_DIR.mkdir(parents=True, exist_ok=True)


# ─── 协议核心验证（数学不变式） ───

def validate_token(token):
    for f in ["protocol", "content", "axiom_transparency",
              "counter_examples", "derivation", "confidence"]:
        if f not in token:
            return False, f"缺少必填字段: {f}"
    c = token["confidence"]
    if not (0 <= (c if isinstance(c, (int, float)) else 0.5) <= 1):
        return False, f"置信度 {c} 须在 [0,1] 区间"
    if not token["axiom_transparency"]:
        return False, "公理透明声明不可为空"
    if not token["counter_examples"]:
        return False, "反例检查不可为空"
    if not token.get("derivation") or len(token["derivation"]) < 1:
        return False, "推导链至少需要 1 步"
    if not token["content"] or len(token["content"].strip()) < 3:
        return False, "令牌内容过短"
    for axiom in token["axiom_transparency"]:
        if axiom.strip() in token["content"]:
            return False, f"循环自指: {axiom[:30]}..."
    return True, "ok"


def generate_token_id(content, ts):
    h = hashlib.sha256(f"{content}{ts}".encode()).hexdigest()[:12]
    return f"cc-{ts[:10]}-{h}"


# ─── DAG 无环检测 ───

def _dag_check():
    tokens, edges = {}, []
    for f in TOKEN_DIR.glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            t = json.load(fp); tokens[t["token_id"]] = t
    for tid, t in tokens.items():
        for step in t.get("derivation", []):
            for oid in tokens:
                if oid != tid and oid in step:
                    edges.append((tid, oid))
    deg = {tid: 0 for tid in tokens}
    for _, to_n in edges:
        deg[to_n] = deg.get(to_n, 0) + 1
    q = [tid for tid, d in deg.items() if d == 0]
    v = 0
    while q:
        n = q.pop(0); v += 1
        for frm, to_n in edges:
            if frm == n:
                deg[to_n] -= 1
                if deg[to_n] == 0:
                    q.append(to_n)
    return {"total": len(tokens), "edges": len(edges), "cycle_free": v == len(tokens)}


# ─── API 端点 ───

@app.route("/health")
def health():
    return jsonify({
        "status": "ok", "protocol": "cognicontract/v1",
        "token_count": len(list(TOKEN_DIR.glob("*.json")))
    })


@app.route("/token/anchor", methods=["POST"])
def anchor_token():
    data = request.get_json(force=True)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    ts = now[:19].replace(":", "").replace("-", "").replace("T", "")
    if "protocol" not in data:
        data["protocol"] = "cognicontract/v1"
    if not data.get("token_id"):
        data["token_id"] = generate_token_id(data.get("content", ""), ts)
    data["anchor_time"] = data.get("anchor_time", now)
    ok, msg = validate_token(data)
    if not ok:
        return jsonify({"error": msg}), 400
    filepath = TOKEN_DIR / f"{data['token_id']}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "anchored", "token_id": data["token_id"]}), 201


@app.route("/token/<token_id>")
def get_token(token_id):
    fp = TOKEN_DIR / f"{token_id}.json"
    if not fp.exists():
        return jsonify({"error": "令牌不存在"}), 404
    with open(fp, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/token/<token_id>/context")
def get_token_context(token_id):
    fp = TOKEN_DIR / f"{token_id}.json"
    if not fp.exists():
        return jsonify({"error": "令牌不存在"}), 404
    with open(fp, encoding="utf-8") as f:
        t = json.load(f)
    lines = [
        f"[认知契约协议 · 已锚定知识令牌]",
        f"令牌ID：{t['token_id']}",
        f"锚定时间：{t['anchor_time']}",
        f"置信度：{t['confidence']}",
        f"",
        f"锚定结论：",
        f"{t['content']}",
        f"",
        f"底层公理：",
    ]
    lines += [f"  - {a}" for a in t["axiom_transparency"]]
    lines += ["", "已知反例："]
    lines += [f"  - {c}" for c in t["counter_examples"]]
    lines += ["", "推导路径："]
    lines += [f"  {i+1}. {d}" for i, d in enumerate(t["derivation"])]
    lines += ["", "--- 以上为不可变锚定共识 ---"]
    return jsonify({"token_id": token_id, "context": "\n".join(lines)})


@app.route("/tokens")
def list_tokens():
    toks = []
    for f in sorted(TOKEN_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        with open(f, encoding="utf-8") as fp:
            t = json.load(fp)
        toks.append({
            "token_id": t["token_id"],
            "content": t["content"][:80],
            "anchor_time": t.get("anchor_time", ""),
            "confidence": t["confidence"],
        })
    return jsonify({"count": len(toks), "tokens": toks})


@app.route("/context/all")
def get_all_context():
    toks = []
    for f in sorted(TOKEN_DIR.glob("*.json"), key=os.path.getmtime):
        with open(f, encoding="utf-8") as fp:
            toks.append(json.load(fp))
    lines = ["=== 认知契约协议 · 已锚定知识令牌库 ===\n"]
    for i, t in enumerate(toks):
        lines.append(f"【令牌{i+1}】{t['token_id']}")
        lines.append(f"锚定结论：{t['content']}")
        lines.append(f"公理：{'；'.join(t['axiom_transparency'])}")
        lines.append(f"反例：{'；'.join(t['counter_examples'])}")
        lines.append(f"置信度：{t['confidence']}\n")
    lines.append(f"--- 以上 {len(toks)} 条为不可变锚定共识 ---")
    return jsonify({"token_count": len(toks), "context": "\n".join(lines)})


@app.route("/context/index")
def get_context_index():
    toks = []
    for f in sorted(TOKEN_DIR.glob("*.json"), key=os.path.getmtime):
        with open(f, encoding="utf-8") as fp:
            t = json.load(fp)
        toks.append({
            "id": t["token_id"],
            "content": t["content"][:80],
            "confidence": t["confidence"],
        })
    lines = [f"=== 令牌索引 ===\n{len(toks)} 条令牌\n"]
    for t in toks:
        lines.append(f"置信度 {t['confidence']} | {t['content'][:60]}...")
    return jsonify({"token_count": len(toks), "context": "\n".join(lines)})


@app.route("/derive", methods=["POST"])
def derive():
    data = request.get_json(force=True)
    q = data.get("question", "")
    if not q:
        return jsonify({"error": "请提供 question 字段"}), 400
    toks = []
    for f in sorted(TOKEN_DIR.glob("*.json"), key=os.path.getmtime):
        with open(f, encoding="utf-8") as fp:
            toks.append(json.load(fp))
    lines = [
        f"基于 {len(toks)} 条共识推导命题：{q}\n",
    ]
    for i, t in enumerate(toks):
        lines.append(
            f"共识{i+1}（置信度 {t['confidence']}）：{t['content']}"
        )
    lines.append("\n请推导并标注每一步依赖的共识。")
    return jsonify({
        "question": q,
        "token_count": len(toks),
        "context_for_ai": "\n".join(lines),
    })


@app.route("/dag/check")
def check_dag():
    return jsonify(_dag_check())


@app.route("/test/verify")
def test_verify():
    toks = []
    for f in TOKEN_DIR.glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            toks.append(json.load(fp))
    dag = _dag_check()
    checks = [
        {"check": "公理透明声明", "pass": all(t.get("axiom_transparency") for t in toks)},
        {"check": "反例检查", "pass": all(t.get("counter_examples") for t in toks)},
        {"check": "推导链完整", "pass": all(t.get("derivation") for t in toks)},
        {"check": "置信度范围", "pass": all(0 <= t.get("confidence", -1) <= 1 for t in toks)},
        {"check": "依赖图无环", "pass": dag["cycle_free"]},
        {"check": "推导链非空", "pass": all(t.get("derivation") and len(t["derivation"]) >= 1 for t in toks)},
    ]
    all_pass = all(c["pass"] for c in checks)
    return jsonify({
        "status": "pass" if all_pass else "fail",
        "token_count": len(toks),
        "checks": checks,
    })


@app.route("/token/<token_id>/supersede", methods=["POST"])
def supersede_token(token_id):
    fp = TOKEN_DIR / f"{token_id}.json"
    if not fp.exists():
        return jsonify({"error": "令牌不存在"}), 404
    with open(fp, encoding="utf-8") as f:
        t = json.load(f)
    t["status"] = "superseded"
    t["superseded_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "superseded", "token_id": token_id})


if __name__ == "__main__":
    print("🧠 Cognitive Contract Protocol v0.1.0")
    print(f"   令牌目录: {TOKEN_DIR}")
    print("   启动: http://localhost:8741")
    app.run(host="0.0.0.0", port=8741, debug=False)
