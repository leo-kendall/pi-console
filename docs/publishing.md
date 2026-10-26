# 发布版本

先运行 README 中的测试和源码检查：

```sh
python3 -B scripts/check_release.py
python3 -B scripts/package_source.py
```

源码包只导出 Git 跟踪文件，包含每个文件的 SHA-256 清单。本机配置、运行数据、签名材料和工具链不得加入提交。新增图片需经过检查，并在源码检查器中登记精确哈希。

确认 GitHub Actions 的测试和构建通过后再打版本标签。测试版使用预发布标签，例如 `v0.5.0-beta.1`，Release 中写明已知问题及 APK 使用的签名类型。

正式签名见[构建说明](build.md)。发布附件包括 APK、源码 ZIP 和 SHA-256 校验文件；不要上传 keystore、密码文件或本机配置备份。

```sh
sha256sum pi-console-*.apk pi-console-source-*.zip > SHA256SUMS
```

保留 LICENSE、NOTICE 和第三方组件声明。图标有独立的授权说明，不能随代码许可证一并宣称已获第三方商标许可。
