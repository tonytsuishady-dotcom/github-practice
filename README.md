# Codex 灵兽小筑

这是一个 Codex 灵兽桌宠的浏览器 demo。它把 Codex 使用行为翻译成修仙设定：

- Token / 用量：灵气
- 5 小时剩余量：短期灵脉
- 1 周剩余量：长期灵脉
- 本地项目：洞府
- GitHub 仓库：宗门藏经阁
- Commit：刻印玉简
- Push：上交宗门
- 拖入文件：投喂灵材

## 运行方式

直接双击打开 `index.html` 即可体验。这个模式不会写入项目文件，但可以下载投喂玉简。

如果你想让 demo 真的在项目里生成投喂玉简，请在这个文件夹中运行：

```powershell
python server.py
```

然后访问：

```text
http://localhost:3000
```

## 当前 demo 包含

- Q 版饕餮灵兽
- 开灵仪式和灵根选择
- 灵气余量面板
- 启动本地服务时尝试读取 Codex 真实用量
- 饱腹值、消化率、投喂次数、修为境界
- 文件拖放投喂
- 文本类文件初步摘要
- 投喂玉简下载
- 通过 `server.py` 写入 `pet-inbox/`
- 本地浏览器状态保存

## 隐私说明

这个 demo 默认只在浏览器本地运行，不上传文件。拖入文本文件时，只在浏览器里读取前一小段内容用于生成摘要。图片、PDF、压缩包等二进制文件不会读取正文，只记录文件名、类型、大小和投喂时间。使用 `server.py` 时，服务只监听 `127.0.0.1`，并只把生成的 Markdown 玉简写入当前项目的 `pet-inbox/`。

`pet-inbox/` 已被 `.gitignore` 忽略，避免把本地投喂记录误传到 GitHub。

## Codex 用量读取

使用 `python server.py` 启动时，demo 会尝试通过本地 `codex app-server` 调用 `account/rateLimits/read`，读取 5 小时和 1 周用量窗口。

如果本机没有可用的 `codex` 命令、未登录、权限受限，或 app-server 协议变更，页面会自动保留 demo 用量，不影响其他功能。
