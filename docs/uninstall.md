# 卸载与恢复

先处理已安装的可选组件，再移除后台服务。每一步仅针对有匹配记录的项目资源，遇到被修改或未知内容时保留并报告。

```sh
python3 -B bridge_manage.py uninstall --remove-image
sudo /usr/bin/python3 -I -B remote-desktop/manage.py uninstall
sudo /usr/bin/python3 -I -B system-control/manage.py uninstall
sudo /usr/bin/python3 -I -B process-control/manage.py uninstall
python3 -B manage.py uninstall
python3 -B manage.py uninstall --apply
```

只执行与你实际安装的组件对应的命令。桥接默认保留镜像；显式 `--remove-image` 也只尝试删除记录确认原先不存在的镜像，Docker 拒绝仍被其他容器使用的镜像。没有所有权记录时不删除容器/镜像。可选 root 安装器不需要在卸载时指定用户。

后台卸载保留源码、本机配置、配对/操作记录和用户文件。确认文件区及回收区均无待保留内容后，可请求清理本项目运行目录：

```sh
python3 -B manage.py uninstall --apply --purge-runtime
```

`--purge-runtime` 应在第一次卸载时一起使用；已删除安装记录的实例不能由工具推定所有权。用户文件、未知目录/文件或可选组件记录会阻止清理。停止服务后再次检查，避免停止期间新写入的文件被误删。文件区/trash/uploads 若被普通文件或链接替代，也会被保留。

最后按你自己的部署记录移除反向代理中该项目的配置。安装器从未修改 VPN、DNS、代理或全局软件包，因此不代为删除这些共享资源。若你专门为本项目启用了 linger，确认无其他用户服务依赖后再自行关闭。

清理完成后可手动删除本地 `config.json`、`build/`、源码 checkout；源码不由卸载器自动删除。手机端卸载 App 会移除该 App 的本机数据；为撤销服务器授权，请先在 App 撤销配对或在服务器执行 `control.py revoke-all`。
