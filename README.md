# 前排提示：这个插件全是AI写的，包括readme

# AstrBot Teacher - 智能题目解析助手

[![Version](https://img.shields.io/badge/version-0.2.5-blue.svg)](https://github.com/lipsc/astrbot_teacher)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-orange.svg)](https://github.com/Soulter/AstrBot)

智能题目解析助手，为 AstrBot 提供强大的解题与知识问答能力。支持文字和图片输入，自动识别题目并给出详细的解答步骤，输出高质量的数学公式和代码渲染图片。

## ✨ 核心特性

- 📝 **多模态输入**：支持文字、图片或文字+图片组合输入
- 🔍 **OCR 识别**：自动识别图片中的题目内容
- 🎨 **高质量渲染**：KaTeX 数学公式 + Markdown 完整支持 + 代码语法高亮
- 🚀 **本地渲染**：基于 Playwright 的稳定本地渲染引擎
- 🌐 **完全离线**：支持完全离线运行，无需外部 CDN
- 🎯 **专业解题**：数学、物理、化学、算法题等全方位支持

## 🚀 使用方法

使用 `/g` 命令触发插件：

**文字问题**：
```
/g 求解方程 x^2 + 5x + 6 = 0
```

**图片问题**：
发送图片 + `/g` 命令，插件会自动 OCR 识别并解答

## 📦 安装指南

### 1. 克隆插件

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/lipsc/astrbot_teacher.git
cd astrbot_teacher
```

### 2. 安装依赖

```bash
pip install aiohttp playwright jinja2
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 4. 下载离线资源（必需）

插件需要以下资源才能正常工作：

#### KaTeX 资源

1. 访问 [KaTeX Releases](https://github.com/KaTeX/KaTeX/releases)
2. 下载最新的 `katex.zip`（推荐 v0.16.9+）
3. 解压到插件目录：

```bash
mkdir -p assets
# 将 katex 文件夹解压到 assets/ 下
```

#### marked.js

```bash
cd assets
wget https://cdn.jsdelivr.net/npm/marked/marked.min.js
```

### 5. 验证目录结构

确保目录结构如下：

```
astrbot_teacher/
├── main.py
├── metadata.yaml
├── _conf_schema.json
├── LICENSE
└── assets/
    ├── katex/
    │   ├── katex.min.css
    │   ├── katex.min.js
    │   └── fonts/
    │       │
    │       └──XXX.ttf/woff2
    └── marked.min.js
```

### 6. 重启 AstrBot

重启 AstrBot 以加载插件。

## ⚙️ 配置选项

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `ocr_provider_id` | string | OCR 使用的 Provider ID | `""` |
| `ocr_model` | string | OCR 使用的模型 | `""` |
| `solver_provider_id` | string | 解题使用的 Provider ID | `""` |
| `solver_model` | string | 解题使用的模型 | `""` |
| `prefer_local_render` | bool | 是否优先使用本地渲染 | `false` |
| `local_device_scale` | int | 本地渲染缩放倍率 | `2` |
| `offline_katex_assets` | bool | 是否使用本地 KaTeX 资源 | `true` |
| `katex_assets_dir` | string | KaTeX 资源目录路径 | `assets/katex` |
| `offline_marked_assets` | bool | 是否使用本地 marked.js | `true` |
| `marked_assets_path` | string | marked.js 文件路径 | `assets/marked.min.js` |

**推荐配置**：
- `prefer_local_render`: `true`（更稳定）
- `offline_katex_assets`: `true`（离线运行）
- `offline_marked_assets`: `true`（离线运行）

## 🐛 故障排除

### 渲染失败

**解决方案**：
```bash
playwright install chromium
# 或
playwright install --with-deps chromium
```

### 公式或代码显示异常

**检查项**：
1. 确认 `assets/katex/` 和 `assets/marked.min.js` 存在
2. 配置中启用 `offline_katex_assets` 和 `offline_marked_assets`

### DeepSeek API 错误

如果遇到 JSON 解析错误，请将 `deepseek-reasoner` 模型切换为 `deepseek-chat`。

## 🧑‍💻 技术栈

- **AstrBot Plugin API** - 插件框架
- **Jinja2** - HTML 模板
- **marked.js** - Markdown 解析
- **KaTeX** - 数学公式渲染
- **Playwright** - 浏览器渲染
- **aiohttp** - 异步 HTTP

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [AstrBot](https://github.com/Soulter/AstrBot)
- [KaTeX](https://katex.org/)
- [marked.js](https://marked.js.org/)
- [Playwright](https://playwright.dev/)

---

<div align="center">

**如果有帮助，请给个 ⭐️ Star！**

Made with ❤️ for AstrBot Community

</div>
