# AI-Scientist-SKILL（OpenClaw / Codex Agent）

这是一个受 [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) 启发的**轻量自动科研流水线**仓库，面向 **OpenClaw / Codex Agent** 使用（不是只针对 Cursor）。

## 目标

- 根据研究主题自动生成研究假设（Ideation）
- 自动检索 GitHub 基线与公开数据集（Experiment v2）
- 执行实验并生成论文草稿（Writeup）
- 多轮审稿与真实性检查（Review v2）

> 注意：该项目不是 AI-Scientist-v2 的一比一复刻，而是可扩展、可本地调试的工程化版本。

## 快速开始

```bash
python main.py --phase full --topic examples/topic_example.md --output ./research_output --mock
```

常用分阶段命令：

```bash
python main.py --phase ideation --topic examples/topic_example.md --output ./research_output
python main.py --phase experiment --ideas ./research_output/ideas.json --idea-id 1 --output ./research_output/experiment
python main.py --phase writeup --ideas ./research_output/ideas.json --idea-id 1 --summary ./research_output/experiment/summary.json --output ./research_output/experiment
python main.py --phase review --paper ./research_output/experiment/paper.md --output ./research_output/review --experiment-dir ./research_output/experiment
```

## 新增：候选实验池 + 自动淘汰（CPU-only）

`ExperimentPhaseV2` 已内置轻量 mini 管理器：

- 构建多个候选模型（如 LR / RF / LinearSVC / GBDT）
- 在 CPU 上快速跑通（不依赖 GPU）
- 按主指标（优先 `f1_score`）自动淘汰并保留 top-k
- 选择最佳候选作为 proposed 结果进入后续写作/审稿

对应配置（`config.yaml`）：

```yaml
experiment:
  candidate_manager:
    enabled: true
    max_candidates: 4
    top_k: 2
```

## 目录结构

```text
.
├── main.py
├── config.yaml
├── SKILL.md
├── phases/
├── templates/
├── utils/
└── examples/
```

## 免责声明

- 本仓库会执行自动生成代码，请在隔离环境运行。
- 若用于正式研究投稿，请披露 AI/自动化使用情况并完成人工复核。
