# 升级、回退与环境检查

以下命令在自己的后端项目目录中，以运行后端的普通 Linux 用户执行。先下载官方 Release 中的源码 ZIP 和校验文件，核对 SHA256；不要把未知来源的源码当作可信更新。清单校验用于检查文件完整性，不能证明发布者身份。

## 检查环境

```sh
python3 -B maintenance.py doctor
python3 -B maintenance.py uninstall-preview
```

检查 Python、用户服务工具、可选 Docker、源码、目录写权限、私有配置文件权限和未完成升级记录。输出不包含配置正文、配对令牌或桌面密码。它不会安装软件、修改权限、连接桌面或证明外部 HTTPS 已经可达。

## 预览并升级

```sh
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip
python3 -B maintenance.py upgrade /path/to/pi-console-source-VERSION.zip --apply --restart
```

没有 `--apply` 时只预览。源码包必须包含 `pi-console/SOURCE_MANIFEST.sha256`，文件内容、路径和数量均会核对。配置、用户文件、密钥、工具链及运行数据不能作为源码成员覆盖。Python 源码还会先进行语法检查。

`--restart` 只用于由本项目安装器管理、所有权收据仍匹配的 `pi-console.service`。它停止这一个用户服务、逐个原子替换源码、启动并检查本机健康接口。启动或检查失败时，先停止失败的新进程，再还原源码并尝试启动旧版。没有由安装器管理的服务时，省略 `--restart`，由自己的进程管理器完成停启。

每次升级会在 `state/maintenance/backups/` 生成私有备份，命令输出中的 `backup` 是回退编号。备份包括本次会替换的旧源码，以及存在的本机 `config.json`、桌面连接配置、告警、设备身份和授权资料；目录权限为 `0700`，备份文件为 `0600`。备份含敏感资料，不要上传到 GitHub、工单或公开网盘。用户上传文件、照片和数据库不复制到该备份中。

当前升级只替换包内源码，不删除包外旧文件，也不会执行数据库迁移、清理容器或修改反向代理。使用 `PI_CONSOLE_CONFIG` 指向项目外配置时，应另行备份该文件。升级运行中的程序前，保留可用的 SSH 或其他管理入口。

## 回退

```sh
python3 -B maintenance.py rollback BACKUP_ID
python3 -B maintenance.py rollback BACKUP_ID --apply --restart
```

预览不改变文件。回退前会检查备份和当前源码；发现升级后手工修改的文件、符号链接或备份变化时停止，保留资料供核对。回退恢复本次替换的源码，不回滚之后新增的手机授权、告警规则或用户文件。私有配置快照供管理员按需手工恢复。

中断的升级会保留事务收据。环境检查会提示未完成状态；用对应的回退编号恢复后，再执行下一次升级。不要直接删除 `state/maintenance/` 来跳过恢复检查。

## 卸载

`uninstall-preview` 列出本项目用户服务与可选组件记录，并说明数据会保留。实际卸载仍使用[卸载说明](uninstall.md)中的各组件命令。新的文件空间、传输暂存和私有备份均属于用户资料；自动清理不会把它们当作可随意删除的缓存。
