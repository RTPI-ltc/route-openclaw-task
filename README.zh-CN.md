# OpenClaw Task Router

面向 OpenClaw 的确定性、可审计 planner 路由 Skill。

[English](README.md) | [完整评测](docs/BENCHMARKS.md) | [安全策略](SECURITY.md) | [架构](docs/ARCHITECTURE.md)

`route-openclaw-task` 在工具执行前，把自然语言任务转换成有界 JSON 决策：planner profile、执行器类型、上下文策略、权限行为和下一步动作。它不会生成命令，也不会替代 OpenClaw 的权限引擎。

## 核心结果

在新的 258 项 ToolSandbox 任务上，基线和优化使用相同 OpenClaw 镜像、Qwen3.7-Max、planner policy 和容器安全策略：

| 指标 | 基线 | 启用 Skill |
|---|---:|---:|
| Strict route success | 26.74% | **93.02%** |
| Holdout success | 30.43% | **84.78%** |
| Executor coverage | 36.43% | **98.06%** |
| Executor precision | 65.50% | **100.00%** |
| Safety | 100.00% | **100.00%** |

独立 router 在旧 1,000 项泛化套件上保持 99.90% task-route success、100.00% holdout。

## 安装

```bash
openclaw skills install git:RTPI-ltc/route-openclaw-task@v0.1.0
```

本地安装：

```bash
git clone https://github.com/RTPI-ltc/route-openclaw-task.git
openclaw skills install ./route-openclaw-task
```

要求 Python 3.10+，不需要第三方 Python 包、网络或 API key。发布流程会在官方 OpenClaw `2026.6.11` 镜像中，以断网、只读根文件系统方式验证安装、识别和执行。

## 快速使用

```bash
python3 scripts/route_task.py \
  --goal "Add Ada to contacts. Available tool interfaces: add_contact, search_stock, get_wifi_status." \
  --pretty
```

批量处理：

```bash
python3 scripts/route_task.py --input-jsonl examples/tasks.jsonl --output-jsonl routes.jsonl
python3 scripts/validate_route.py routes.jsonl
```

## 安全边界

- router 不启动子进程、不执行 shell、不联网、不读取凭据。
- JSON 模型是词频表，不是可执行模型文件。
- 发布资产不包含原始训练 prompt，并经过邮箱、IP、URL、私钥和常见 API key 形状扫描。
- 缺少工具依赖时选择 abstain/replan，不猜测执行。
- 最终权限仍由 OpenClaw `PermissionEngine` 决定。

更多信息见 [安全策略](SECURITY.md)、[模型卡](references/model-card.md) 和 [评测说明](docs/BENCHMARKS.md)。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_skill.py .
python3 scripts/verify_release.py .
```

项目代码采用 [MIT License](LICENSE)，第三方数据和 benchmark 保留原始许可，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
