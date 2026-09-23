# 教资刷题 · 安卓 APK 说明

目标：像普通 App 一样安装使用（不是浏览器书签）。

## 出 APK（推荐：GitHub Actions，本机无需装安卓环境）

1. 将本仓库推到 GitHub
2. 打开 **Actions → Build Android APK → Run workflow**
3. 完成后在该次运行的 **Artifacts** 下载 `jiaozhi-quiz-apk`
4. 手机打开 `app-debug.apk` 安装（需允许「未知来源」）

> 当前电脑未安装 Android SDK / Java，故 APK 在云端/本机 Android Studio 编译。

## 出 APK（本机 Android Studio）

1. 安装 Android Studio（含 SDK 34、JDK 17）
2. 打开目录 `android/`
3. 等待 Gradle 同步 → **Build → Build APK(s)**
4. 产物：`android/app/build/outputs/apk/debug/app-debug.apk`

## 本地试用（无需 APK）

手机/电脑浏览器直接打开 `index.html`，或使用 PWA「添加到主屏幕」。

## 包结构

- `android/app/src/main/assets/www/` — 内嵌 H5（与根目录同步）
- `android/.../MainActivity.java` — WebView 壳，全屏竖屏
- 应用图标：`assets/icons/app-icon-master.png`（launcher）
