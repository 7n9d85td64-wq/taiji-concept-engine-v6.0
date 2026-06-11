# Cognitive Contract Protocol (认知契约协议)

> **换AI不掉共识 · 跨对话不失智 · 可验证不幻觉**  
> *Switching AIs? Your consensus stays. New chat? Knowledge persists. Hallucination? Verifiable.*

## ⚡ 一眼看懂 / At a Glance

| 能力 / Capability | 说明 / Description |
|:---|:---|
| 🔗 **跨AI知识继承** / Cross-AI Knowledge Inheritance | 和DeepSeek定的共识，WorkBuddy秒懂。换模型不掉结论。 |
| ✅ **可验证共识** / Verifiable Consensus | 每条结论附公理+反例+推导链，不是"我信"，是"我能查"。 |
| 🛡️ **降低幻觉** / Hallucination Reduction | 强制反例自检，AI不能蒙混过关。 |
| 📋 **推理可审计** / Auditable Reasoning | 谁、什么时候、基于什么、得出了什么——每一步可追溯。 |
| 🔓 **去中心化** / Decentralized | 令牌存你本地，不绑任何平台。协议是你的，知识也是你的。 |
| ⏱️ **三分钟跑通** / 3-Minute Setup | `pip install flask` → `python token_server.py` → 跑通。 |

## ⚡ 三分钟跑通 / Quick Start

```bash
# 1. 安装依赖
pip install flask requests

# 2. 启动令牌服务器
python token_server.py
# → http://localhost:8741

# 3. 锚定第一条共识
curl -X POST http://localhost:8741/token/anchor \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "cognicontract/v1",
    "content": "Python是AI工程落地的最佳语言（LLM应用层）",
    "axiom_transparency": ["生态丰富度优先于单一性能"],
    "counter_examples": ["Go在网关场景更优"],
    "derivation": ["对比主流语言生态", "评估部署成本", "得出结论"],
    "confidence": 0.85
  }'

# 4. 新AI加载共识
#    → 浏览器打开 http://localhost:8741/context/all
#    → 复制文本 → 粘贴给任何AI → 完事！

# 5. 跑测试
python test_automated.py  # 10轮50项, 100%通过
```

## 📄 更多

- 📄 [完整论文 (中英双语)](./paper_v3_bilingual.md)
- 🧮 [数学形式化定义](./spec_math.md)
- 🧪 [区块链时间戳验证](https://github.com/7n9d85td64-wq/cognitive-contract-protocol/releases/tag/v1.0)

## 💖 支持

Apache 2.0 永久开源。有帮助的话：

- [爱发电](https://ifdian.net/a/cognitive_contract)
- [GitHub Sponsors](https://github.com/sponsors/7n9d85td64-wq)

## 📜 许可证

代码：Apache 2.0 | 论文：CC BY 4.0
