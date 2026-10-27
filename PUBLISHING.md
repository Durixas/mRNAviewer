# 发布 mRNAviewer 代码、数据与评估材料

目标仓库：<https://github.com/Durixas/mRNAviewer>。
整理分支：`webserver-bert2bert-20261026`。

## 本次发布范围

- 当前前端、Flask 后端、CDS/两端 BERT2BERT 推理与本地运行时。
- RNAfold、miRNA/RBP 分析脚本及必需的小型 motif 表。
- 29 tissue 和 General 的模型配置、tokenizer 与来源校验值。
- 29 tissue 的实际 CDS/UTR 训练、验证和测试数据及冻结拆分。
- 稿件 benchmark 的真实预测、原指标与评估脚本；UTR 报告 ROUGE/BLEU。
- 环境依赖、启动脚本、资产恢复脚本、回归检查和第三方来源声明。

数据以四个带 SHA-256 清单的压缩包版本化，合计137.29 MiB，最大
单文件70.21 MiB。解压副本、用户任务、凭据、旧版本备份和虚拟环境
由 `.gitignore` 排除。根 README 面向稿件读者，部署细节在
[安装说明](docs/INSTALLATION.md)。

## 模型资产单独托管

完整运行资产约53.35 GiB，其中 UTR 权重约53.08 GiB。
`assets/manifest.json` 记录110项资产的相对路径、大小和SHA-256。
权重和BLAST索引不放普通Git，单独托管在 Hugging Face model repo、
对象存储或下载服务器。当前尚未配置公开的权重下载地址。

已有完整安装时：

```bash
python scripts/restore_assets.py --source /path/to/mRNAoptimizer_1212
python scripts/restore_assets.py --check --verify
```

托管到 Hugging Face 后，使用固定版本恢复：

```bash
python scripts/restore_assets.py --hf-repo YOUR_HF_NAME/mRNAviewer-assets --revision COMMIT_OR_TAG --verify
```

配置、tokenizer 与元数据已在Git中；上传资产时按manifest白名单选取。
归档预测的评估复算无需权重。全新推断需要额外恢复相应模型。

## 复现与提交检查

```bash
python evaluation/reproduce.py
python -m unittest discover -s evaluation/cds -p 'test_*.py' -v
python -m unittest discover -s evaluation/utr -p test_metrics.py -v
git diff --check
git diff --cached --stat
```

CDS历史最高test、实际checkpoint测量和日志选择审计保留各自来源；
数据文档如实记录实际拆分。稿件的方法文字应与这些记录保持一致。

## 推送整理分支

```bash
git status --short
git log -1 --oneline
git push -u origin webserver-bert2bert-20261026
```

本副本的remote为 `git@github.com:Durixas/mRNAviewer.git`，Git身份设置
只作用于本副本。推送后可通过 Pull Request 查看整个发布范围，再合并
到默认分支。后续更新正常提交、推送即可；模型资产按独立版本保存。
