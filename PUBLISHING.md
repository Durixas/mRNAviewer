# 将当前 Web 服务发布到 GitHub

目标仓库：<https://github.com/Durixas/mRNAviewer>。
本地准备分支：`webserver-bert2bert-20261026`。

## 已整理的范围

- 当前前端、Flask 后端、CDS/两端 UTR 推理、本地 DNABERT2 运行时。
- 当前 RNAfold、miRNA/RBP 分析脚本，以及必需的 RBP 小型数据表。
- 两端各30个模型的配置、tokenizer、验证选择与来源校验值。
- 两套 Python 环境的依赖、启动脚本、资产恢复脚本和回归测试。
- 第三方代码原有许可证与来源说明。

旧 Covariant Script 后端、旧前端、备份、历史 Docker/打包脚本、训练
数据、旧 BART 权重、日志和用户任务结果没有加入本次发布目录。

## 代码与模型分开保存

普通 GitHub Git 会拦截大于100 MiB的单文件；每份UTR权重约906 MiB。
参见 [GitHub大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

代码和配置上传这个 GitHub 仓库。约53.35 GiB的运行资产单独保存在
Hugging Face model repo、对象存储或下载服务器；按
`assets/manifest.json`中的相对路径、大小和SHA256恢复。
Hugging Face 的上传方法见[官方文档](https://huggingface.co/docs/huggingface_hub/guides/upload)。

本目录已用`.gitignore`排除模型、数据库、论文PDF、任务结果和环境配置。
`assets/manifest.json`只记录文件身份，不包含权重内容。
当前没有执行任何模型资产上传；确定托管位置后可在 README 填入实际下载地址。

## 首次推送

此副本已整理为本地提交。在此目录检查后推送：

```bash
git log -1 --oneline
git status --short
git push -u origin webserver-bert2bert-20261026
```

本副本的本地提交身份为`Durixas`和该账号的GitHub noreply邮箱；设置
只作用于这个副本。当前SSH已验证为Durixas，remote已配置为以下地址。
推送使用有目标仓库写入权限的 GitHub 认证：

```bash
git remote set-url origin git@github.com:Durixas/mRNAviewer.git
git push -u origin webserver-bert2bert-20261026
```

推送后在 GitHub 创建此分支到默认分支的 Pull Request，查看文件范围
和 README，再合并。后续修改正常提交、推送：

```bash
git add .
git diff --cached --stat
git commit -m "Describe the update"
git push
```

模型资产按版本保存在各自的存储位置。

## 资产托管与复现

若已有完整应用目录，可以按 README 的`--source`命令恢复运行资产。
若采用 Hugging Face，先建立自己的 model repository，再使用已登录的
`huggingface_hub.HfApi.upload_folder`，把完整应用目录作为`folder_path`，
并将`allow_patterns`设置为`assets/manifest.json`中每项的`path`。
这样只上传110项清单资产，不包含旧文件或用户任务。配置、tokenizer
和来源信息已经随 GitHub 代码提供。

确定托管位置后记录仓库ID与commit/tag，部署者即可执行：

```bash
python scripts/restore_assets.py --hf-repo YOUR_HF_NAME/mRNAviewer-assets --revision COMMIT_OR_TAG --verify
```

HF账号的存储配额按其[当前官方规则](https://huggingface.co/docs/hub/storage-limits)确定。
