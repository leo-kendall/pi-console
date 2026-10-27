# 服务器配置与应用更新

设置页可保存、命名及切换最多 32 台 HTTPS 服务器。每个配置拥有独立的配对凭证、应用入口、主题和刷新频率。凭证使用 Android Keystore 中的 AES-GCM 密钥加密；新格式还认证配置 ID，不能把一个配置的密文复制到另一个配置使用。首次升级会保留 beta2 的服务器地址、配对与应用入口，不删除原 Keystore 密钥。

添加服务器只保存本机配置，不会自动配对。切换后请使用对应服务器生成的配对码。切换会断开远程桌面、停止前台界面的旧轮询及持续通知监控；文件选择、文件传输及备份任务结束前不能切换。备份预览属于选取时的服务器，切换后必须重新选择，不能把旧预览应用到新服务器。每个请求同时捕获地址、凭证和配置代次，迟到的配对结果不能覆盖新配置。

“检查在线状态”只检查你点击的服务器，不会定时遍历所有已保存服务器。移除本机配置只删除此手机上的地址、凭证与入口，不会向服务器发送撤销请求。要撤销服务器端设备授权，请先切换到该服务器，再撤销配对或使用服务器设备管理。

应用更新仅在点击“检查官方更新”后访问 `leo-kendall/pi-console` 的 GitHub Releases API，可选择正式版或含测试版。版本比较使用语义版本规则，APK 的 Android versionCode 还必须高于当前安装。没有发布资源 SHA256 的旧发布仍可显示版本与说明，但不能通过应用下载。

下载在 Android 原生前台服务中进行，界面离开后继续；下载受大小、响应及重定向次数限制。每一跳都必须使用 GitHub 官方 HTTPS 域名，不携带服务器配对令牌。APK 存入 App 私有目录，验证 SHA256、文件长度、包名 `dev.piconsole`、最低 Android 版本、versionCode 及当前签名/有效签名轮换历史。Android 26–27 仅接受原签名，Android 28+ 可识别签名历史。校验通过后才显示安装按钮；你仍需在 Android 系统界面授予安装来源权限并确认安装。更新不会替你撤销或重建服务器配对。

## 发布与固定签名

`dev.piconsole` 包名不变。优先保留 beta2 实际分发 APK 的原私有签名，以便覆盖升级时保留应用数据及 Keystore 配对。先在私有环境对比原 APK 的证书指纹；固定签名只能存放在仓库外、权限为 0600 的受保护位置，并单独保存离线加密备份。不要把密钥、密码、个人配置或配对令牌放入 Git、源码包或 Release。

若 beta2 签名属于公开或丢失的开发签名，不能假装换一个生产密钥仍能覆盖升级。保留包名时，签名不匹配会被本更新器及 Android 拒绝；迁移必须明确安排重新安装和重新配对。设置备份不包含配对密钥，卸载会删除 Keystore 凭证。可在掌握原私钥且有可信签名方案时单独设计签名轮换，但 Android 26–27 仍需原签名兼容发布；不要未经验证在一次升级中更改证书。

普通构建先产生 `build/android/unsigned.apk`。在已安装 SDK/JDK 的私有发布环境运行：

```sh
python3 -B scripts/build_android.py
export PI_CONSOLE_KEYSTORE=/private/signing/pi-console.p12
export PI_CONSOLE_KEY_ALIAS=pi-console
read -rs PI_CONSOLE_KEYSTORE_PASSWORD
export PI_CONSOLE_KEYSTORE_PASSWORD
python3 -B scripts/release_android.py \
  --unsigned build/android/unsigned.apk \
  --expected-cert-sha256 APPROVED_CERTIFICATE_SHA256
unset PI_CONSOLE_KEYSTORE_PASSWORD
```

此脚本不会生成生产密钥、下载工具或发布文件。它固定 ZIP 排序、权限及时间戳（默认当前 Git 提交时间，也可用 `SOURCE_DATE_EPOCH`），对齐后通过环境传递密码签名，验证实际证书指纹再替换输出，并生成 SHA256 文件。要复现同一产物，还需固定源提交、SDK/JDK、aapt2、D8、zipalign、apksigner 版本及同一 RSA 签名密钥；EC 签名可能包含随机性。连续两次私有干净构建应对比 APK 哈希。

上传名为 `pi-console-release.apk` 或 `pi-console.apk` 的资源到官方 GitHub Release。GitHub API 应提供 `digest: sha256:…`，同时可附上脚本生成的 `.apk.sha256`。更新器不会信任网页说明中的散列值。最终 Android 安装器仍会执行平台的 APK 签名及升级权限验证。
