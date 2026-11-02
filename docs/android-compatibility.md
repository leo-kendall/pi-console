# Android 通用兼容性

Pi Console 面向主流 Android 手机和平板，不按小米、三星、OPPO、vivo 等品牌写固定尺寸或专用分支。安装包最低 Android 8.0（API26），没有随包原生 ABI 库；Android 系统本身和系统 WebView 都需要满足要求。iPhone 不能安装 Android APK。

## 运行条件

- 系统 WebView 已启用，能够执行现代 JavaScript、对话框、文本编码和相应 DOM 方法。启动时检测实际能力，不用厂商版本号猜测。
- WebView 太旧、被禁用或不可用时，提供原生更新／设置／重试界面。更新系统 WebView 或 Chrome 后再试。完整界面加载失败和旧内核不兼容分别提示。
- 网络能访问自行部署的 HTTPS 后端；证书须受 Android 系统信任。公网、局域网和 VPN 都可使用。桌面组件另需配置，见[桌面兼容范围](desktop-compatibility.md)。

## 通用适配策略

- 读取实际窗口、系统栏、摄像头区域和键盘遮挡，不硬编码某一手机分辨率。全屏采用对称安全区域并保持画面等比，退出后恢复普通界面。
- 自适应或固定／自定义分辨率，16:9、16:10、4:3、3:2、21:9。固定像素尺寸不会随旋转改变；远端不接受调整时显示实际尺寸并停止有限重试。
- 横屏控件可滚动，长标签不挤压；触控、实体键鼠、字体放大和前后台切换分别处理。
- 软件／默认绘制和布局／旧版缩放可在诊断中对比，保留 GPU/WebView 绘制问题的排查入口。

## 验证分层，不能混为一谈

| 层次 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| JVM 原生边界测试 | API26/27/28/29/30/33/35/36/37 分支、边距、键盘、坐标、恢复与数据边界 | Android 系统和硬件真的执行过这些分支 |
| 浏览器界面测试 | 多种尺寸、密度、字体、比例、Guacamole 合成帧和用户流程 | 厂商系统、手机 GPU 或 Android WebView 行为 |
| Android 模拟器 | 实际 Android Framework/WebView、窗口旋转、PixelCopy 颜色、原生桥接与安全区域 | 三星、小米等厂商固件和每一种 GPU 的真机认证 |
| 手机真机 | 指定型号、系统与 WebView 组合的实际使用结果 | 同品牌其他机型或所有版本都正常 |

项目没有“绝大多数品牌已实测”或“所有手机保证兼容”的证据，不作此承诺。发现问题请提供 App/Android/WebView 版本、屏幕方向、分辨率与去除私人信息的统计。

## 持续集成矩阵

[Android compatibility matrix](https://github.com/leo-kendall/pi-console/actions/workflows/android-compatibility.yml) 配置 API26、28、30、33、35、36，覆盖16:9、20:9，以及系统镜像提供时的角落摄像头模拟。每次运行都保留有界几何和颜色统计，不导出桌面截图、文本或按键。模拟器采用显式参考尺寸配置，读取 `wm size` 的实际生效尺寸，并要求完整界面全屏窗口与请求像素一致；系统限制导致尺寸未生效时直接失败，不能只根据场景名称认定比例已覆盖。

旧系统镜像附带的旧 WebView 可以只验证原生更新提示，但报告必须标为 `requires-webview-update`，且 `full_ui_tested=false`；不能当作完整功能通过。较新镜像必须通过完整界面测试。报告明确区分“已配置测试”“实际执行结果”和“仍待真机验证”。

本次新增模拟器流水线的实际结果以对应 commit 的 Actions 报告为准；提交文档本身不等于测试通过。API37 的一次实际尝试在 SDK 下载阶段因 `platforms;android-37` 不可用而停止，尚未运行 App，不计入运行时覆盖；待官方 SDK／系统镜像在构建环境中可用后再加入必需矩阵。

不同 WebView 对 CSS zoom 的矩形坐标口径不同，测试会用独立元素检测实际行为并换算到视口坐标。原生 PixelCopy 检查三种分区颜色，防止把裁切／未缩放的画面误判为正常；只排除可见“控件”浮动按钮占用的少量取样点，仍要求至少 30 个有效颜色点。

## 本机／模拟器复现

```sh
python3 -B scripts/build_android_compat.py
# 只构建开发版和测试 APK，不安装到任何设备。
python3 -B scripts/test_android_compat.py --run --serial emulator-5554 --label manual --require-full-ui
```

运行器只接受 Android 模拟器，必须显式 `--run`，会重置其中的开发版 App 数据。不能把它指向正在使用的真机。开发证书只用于测试，不会访问正式签名密钥；正式 APK 请从 Releases 获取。
