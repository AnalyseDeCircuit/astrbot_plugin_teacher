import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional, Any, Awaitable, Callable, cast
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from jinja2 import Template


TMPL = """
<!doctype html>
<html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {{ KATEX_CSS | safe }}
        <style>
            :root { --font: 'Noto Sans', 'Noto Serif CJK SC',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial; }
            body { font-family: var(--font); background: #fff; color: #222; padding: 32px; font-size: 16px; line-height: 1.7;}
            .card { background: white; border-radius: 12px; padding: 32px; box-shadow: 0 10px 24px rgba(20,20,20,0.08); width: 1100px; margin: 0 auto; }
            .header { margin-bottom: 24px; }
            .header h1 { font-size: 24px; margin: 0 0 8px 0; }
            .header .small { color: #666; font-size: 13px; }
            .question-box { background: #f8f9fa; border-left: 4px solid #007bff; padding: 16px 20px; margin: 20px 0; border-radius: 4px; }
            .question-box h2 { font-size: 18px; margin: 0 0 8px 0; color: #007bff; }
            .question-text { font-size: 15px; white-space: pre-wrap; word-break: break-word; color: #333; }
            .content { font-size: 16px; line-height: 1.8; }
            .content h1 { font-size: 22px; margin: 28px 0 12px 0; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }
            .content h2 { font-size: 20px; margin: 24px 0 10px 0; color: #333; }
            .content h3 { font-size: 18px; margin: 20px 0 8px 0; color: #555; }
            .content p { margin: 12px 0; }
            .content ul, .content ol { padding-left: 28px; margin: 12px 0; }
            .content li { margin: 6px 0; }
            .content strong { font-weight: 600; color: #000; }
            .content em { font-style: italic; color: #555; }
            .content code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; }
            .content pre { background: #f5f5f5; padding: 16px; border-radius: 6px; overflow: auto; margin: 16px 0; }
            .content pre code { background: none; padding: 0; }
            .content blockquote { border-left: 4px solid #ddd; padding-left: 16px; margin: 16px 0; color: #666; font-style: italic; }
            .content hr { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
            .content table {border-collapse: collapse;margin: 16px 0;width: 100%;}
            .content th, .content td {border: 1px solid #ddd;padding: 8px 12px;text-align: left;}
            .content th {background: #f2f2f2;font-weight: 600;}
            .content tr:nth-child(even) {background: #fafafa;}
            .katex .mtable {border-collapse: separate !important;border-spacing: 0 0.5em !important;}

        </style>
        {{ KATEX_JS | safe }}
        {{ AUTORENDER_JS | safe }}
        {{ MARKED_JS | safe }}
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // 从 script[type="text/plain"] 读取原始 Markdown
                // 这样可以防止浏览器将 <iostream> 当作 HTML 标签处理
                const sourceEl = document.getElementById('markdown-source');
                const contentEl = document.getElementById('markdown-content');
                
                if (sourceEl && contentEl && window.marked) {
                    // 读取原始 Markdown 文本
                    const mdText = sourceEl.textContent;
                    
                    // marked.js 会自动转义代码块中的 HTML
                    const htmlResult = marked.parse(mdText);
                    
                    contentEl.innerHTML = htmlResult;
                }
                
                // 用 KaTeX 渲染数学公式
                if (window.renderMathInElement) {
                    renderMathInElement(document.body, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false}
                        ],
                        throwOnError: false
                    });
                }
            });
        </script>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h1>📚 题目解析</h1>
                <div class="small">由 AstrBot 插件 <strong>astrbot_teacher</strong> 生成</div>
            </div>

            <div class="question-box">
                <h2>📝 题目</h2>
                <div class="question-text">{{ question }}</div>
            </div>

            <!-- 使用 script type="text/plain" 保存原始 Markdown，防止被浏览器解析 -->
            <script type="text/plain" id="markdown-source">{{ content }}</script>
            <div class="content" id="markdown-content"></div>
        </div>
    </body>
    </html>
"""


@register("astrbot_teacher", "lipsc", "智能题目解析助手，支持文字/图片输入并输出美观解析图片（完全离线）", "0.2.5")
class TeacherPlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        self.config = config or {}

    async def initialize(self):
        logger.info("astrbot_teacher 初始化完成（Markdown 模式）")

    def _pick_llm_provider(self, preferred_id: str, event: AstrMessageEvent):
        """根据优先 ID 或当前会话选择可用的 LLM Provider（具备 text_chat 方法）。"""
        prov = None
        try:
            if preferred_id:
                prov = self.context.get_provider_by_id(provider_id=preferred_id)
            if not prov:
                prov = self.context.get_using_provider(umo=event.unified_msg_origin)
            # 仅接受有 text_chat 的 Provider（LLM）
            if prov and not hasattr(prov, "text_chat"):
                logger.warning("选择的 Provider 不支持 text_chat，将忽略: %s", getattr(prov, "provider_config", {}))
                return None
            return prov
        except Exception:
            logger.exception("选择 Provider 失败")
            return None

    async def _text_chat(self, provider: object, **kwargs) -> Any:
        """以更安全的方式调用 provider.text_chat，避免类型检查器误报。"""
        func = getattr(provider, "text_chat", None)
        if not callable(func):
            raise RuntimeError("所选 Provider 不支持 text_chat 方法")
        func_typed = cast(Callable[..., Awaitable[Any]], func)
        return await func_typed(**kwargs)

    def _build_template(self) -> tuple[str, str, str, str, str]:
        """根据配置决定使用本地 KaTeX 和 marked.js 资源或 CDN。

        返回:
        - tpl: 模板字符串
        - katex_css_tag: 最终 CSS 片段
        - katex_js_tag: 最终 KaTeX JS 片段
        - autorender_js_tag: 最终 KaTeX auto-render JS 片段
        - marked_js_tag: 最终 marked.js 片段
        """
        use_offline_katex = bool((self.config or {}).get("offline_katex_assets", True))
        use_offline_marked = bool((self.config or {}).get("offline_marked_assets", True))
        assets_dir_cfg = (self.config or {}).get("katex_assets_dir", "assets/katex")
        marked_path_cfg = (self.config or {}).get("marked_assets_path", "assets/marked.min.js")
        plugin_dir = Path(__file__).parent
        assets_dir = Path(assets_dir_cfg)
        if not assets_dir.is_absolute():
            assets_dir = plugin_dir / assets_dir

        # KaTeX 资源
        katex_css_tag = (
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" crossorigin="anonymous">'
        )
        katex_js_tag = (
            '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" crossorigin="anonymous"></script>'
        )
        autorender_js_tag = (
            '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" crossorigin="anonymous"></script>'
        )

        if use_offline_katex:
            css_path = (assets_dir / "katex.min.css").resolve()
            js_path = (assets_dir / "katex.min.js").resolve()
            auto_path = (assets_dir / "auto-render.min.js").resolve()
            fonts_dir = assets_dir / "fonts"

            if css_path.exists() and js_path.exists() and auto_path.exists():
                if not fonts_dir.exists():
                    logger.warning("离线 KaTeX 字体目录缺失，将退回系统字体，显示效果可能有差异。缺少: %s", fonts_dir)
                katex_css_tag = f"<link rel=\"stylesheet\" href=\"file://{css_path.as_posix()}\">"
                katex_js_tag = f"<script defer src=\"file://{js_path.as_posix()}\"></script>"
                autorender_js_tag = f"<script defer src=\"file://{auto_path.as_posix()}\"></script>"
            else:
                logger.warning("离线 KaTeX 资源未找到或不完整，回退使用 CDN。路径: %s", assets_dir)

        # marked.js 资源
        marked_js_tag = '<script src="https://cdn.jsdelivr.net/npm/marked@11.1.0/marked.min.js"></script>'
        
        if use_offline_marked:
            marked_path = Path(marked_path_cfg)
            if not marked_path.is_absolute():
                marked_path = plugin_dir / marked_path
            marked_path = marked_path.resolve()
            
            if marked_path.exists():
                marked_js_tag = f"<script src=\"file://{marked_path.as_posix()}\"></script>"
                logger.info("使用本地 marked.js: %s", marked_path)
            else:
                logger.warning("离线 marked.js 资源未找到，回退使用 CDN。路径: %s", marked_path)

        tpl = TMPL
        return tpl, katex_css_tag, katex_js_tag, autorender_js_tag, marked_js_tag

    async def _render_locally(self, html: str, *, device_scale: int = 2, full_page: bool = True) -> str:
        """使用本地 Playwright 渲染 HTML 为图片，返回本地文件路径。

        注意：为确保 file:// 资源（KaTeX CSS/JS 与 fonts/）可加载，这里先将 HTML 写入临时文件，
        再以 file:// 协议打开该页面（避免 about:blank 环境下的"Not allowed to load local resource"）。

        需要：pip install playwright && playwright install chromium
        """
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception as e:
            raise RuntimeError("本地渲染需要安装 playwright，请先 pip install playwright 并执行 playwright install chromium") from e

        tmp_dir = Path(tempfile.gettempdir())
        ts = int(asyncio.get_event_loop().time() * 1000)
        out_path = str(tmp_dir / f"astrbot_teacher_{ts}.png")
        html_file = tmp_dir / f"astrbot_teacher_{ts}.html"
        html_file.write_text(html, encoding="utf-8")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(device_scale_factor=device_scale)
            await page.goto(f"file://{html_file.as_posix()}", wait_until="load")

            # -- 注入自定义字体 --
            custom_font_dirs = (self.config or {}).get("custom_font_dirs") or []
            if custom_font_dirs:
                font_faces = []
                for font_dir_str in custom_font_dirs:
                    font_dir = Path(font_dir_str)
                    if not font_dir.is_dir():
                        logger.warning(f"自定义字体目录不存在: {font_dir_str}")
                        continue
                    
                    logger.info(f"正在从目录加载字体: {font_dir_str}")
                    for font_file in font_dir.rglob('*'):
                        if font_file.suffix.lower() in ['.ttf', '.otf', '.woff', '.woff2']:
                            font_family_name = font_file.stem  # 使用文件名作为字体族名
                            font_faces.append(f"""
                                @font-face {{
                                    font-family: '{font_family_name}';
                                    src: url('file://{font_file.as_posix()}');
                                }}
                            """)
                
                if font_faces:
                    style_content = "\n".join(font_faces)
                    await page.add_style_tag(content=style_content)
                    logger.info(f"成功注入 {len(font_faces)} 个自定义字体。")

            # 等待字体与渲染加载
            try:
                await page.wait_for_function("() => document.fonts && document.fonts.status === 'loaded'", timeout=1500)
            except Exception:
                pass
            try:
                await page.wait_for_selector('.katex', timeout=2000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            await page.screenshot(path=out_path, full_page=full_page, type="png")
            await browser.close()
        return out_path

    def _get_full_plain_text(self, event: AstrMessageEvent) -> str:
        """从消息链重建完整纯文本，避免仅拿到第一个参数的情况。"""
        parts: List[str] = []
        try:
            for comp in event.message_obj.message:
                text = getattr(comp, "text", None)
                if text is None:
                    d = getattr(comp, "__dict__", {}) or {}
                    text = d.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        except Exception:
            parts.append(event.message_str or "")
        return "".join(parts)

    def _extract_text_after_command(self, event: AstrMessageEvent, cmd: str) -> str:
        """从完整原始文本中抽取 `/cmd` 之后的文本，兼容多空格、换行、特殊字符。"""
        raw = self._get_full_plain_text(event)
        if not raw:
            raw = event.message_str or ""
        m = re.search(rf"(^|\s)/{re.escape(cmd)}\b(.*)$", raw, flags=re.S)
        if not m:
            m = re.search(rf"(^|\s){re.escape(cmd)}\b(.*)$", raw, flags=re.S)
        if m:
            tail = (m.group(2) or "").strip()
            return tail
        return raw.strip()

    def _extract_image_urls(self, event: AstrMessageEvent) -> List[str]:
        urls: List[str] = []
        try:
            for comp in event.message_obj.message:
                v = getattr(comp, "url", None) or getattr(comp, "file", None) or getattr(comp, "path", None)
                if v:
                    urls.append(str(v))
                    continue
                d = getattr(comp, "__dict__", {}) or {}
                for k in ("url", "file", "path", "image"):
                    val = d.get(k)
                    if val:
                        urls.append(str(val))
                        break
        except Exception:
            logger.exception("提取图片 URL 时出错")
        return urls

    @filter.command("g")
    async def solve(self, event: AstrMessageEvent, question: str = ""):
        """/g <题目内容>

        如果附带图片，会先对图片进行 OCR（由模型做图片理解），再统一交给解题模型。
        """
        try:
            # 1. 准备 provider
            solver_provider_id = (self.config or {}).get("solver_provider_id") or ""
            ocr_provider_id = (self.config or {}).get("ocr_provider_id") or ""

            prov_solver = self._pick_llm_provider(solver_provider_id, event)
            prov_ocr = self._pick_llm_provider(ocr_provider_id, event)

            if not prov_solver:
                yield event.plain_result("❌ 未找到可用的解题 Provider，请在 AstrBot 管理界面配置模型提供商或在插件配置中指定 solver_provider_id。")
                return
            if not prov_ocr:
                logger.warning("未找到 OCR Provider，将仅使用文字输入进行解题。")

            # 2. 收集图片
            image_urls = self._extract_image_urls(event)
            ocr_text = ""

            # 3. 如果有图片，先调用模型做图片到文本的提取（OCR）
            if image_urls and prov_ocr:
                ocr_model = (self.config or {}).get("ocr_model") or None
                ocr_prompt = '''你是一个视觉识别模型，任务是从图像中提取所有有意义的文字信息，包括题目文字、符号、公式和标注。

要求：
1. 尽可能完整、准确地转录所有文字内容。
2. 对数学公式使用 LaTeX 语法输出，保持原有结构（不要简化或改写）。
3. 保留题目排版顺序（上到下、左到右），适当添加换行。
4. 如果有表格、图示标签或编号，保留其文本信息。
5. 不要解释内容，不要做任何推理。
6. 如果遇到模糊区域，请以 `[可能为: ...]` 形式标注。

输出格式：
[OCR_TEXT]
(在这里输出提取到的文字与公式)
注意：
- **不得使用\(\)和\[\]包裹任何东西，请用别的方式替代**
- 例如："这是 $ r $ 的半径"
- 仅限简短表达，复杂公式应放入 `$$...$$`
- 正确示例：
  - "函数的值域为 $ g(x) \\in [a,b] $"
  - "设 $ a = 1 $，$ b = 2 $"
  - "在区间 $ x \\in (0, 1) $ 上"
- **错误示例**（不会渲染）：
  - "(g(x) \\in [a,b])" ← 缺少 $ 符号
  - "$g(x) \\in [a,b]$" ← 紧贴文字，缺少空格
  - "\( R \)"← 使用\( \) 语法导致最后渲染不成功

积分、求和、分式、矩阵、对齐推导等复杂表达式使用块级公式：

$$
... 
$$

- 独占一行，上下各留空行
- 块内可使用 `aligned`、`cases` 等环境进行多行排版
- 禁止在块级公式中嵌套 `$...$`


### 其他说明
**不要输出额外说明或前后缀。**
**输出中的 LaTeX 代码不做任何字符清理或转义，保持原样。**

'''
                try:
                    ocr_resp = await self._text_chat(
                        prov_ocr,
                        prompt=ocr_prompt,
                        context=[],
                        system_prompt="OCR: 将图片中的题目转为可编辑文本。",
                        image_urls=image_urls,
                        model=ocr_model,
                    )
                    ocr_text = ocr_resp.completion_text.strip() if ocr_resp else ""
                except Exception:
                    logger.exception("OCR 请求失败")
                    ocr_text = ""

            # 4. 合并用户输入的文字题目与 OCR 结果
            base_q = (question or "").strip()
            q_from_event = self._extract_text_after_command(event, "g")
            if q_from_event:
                if (len(q_from_event) > len(base_q)) or (base_q and q_from_event.startswith(base_q)):
                    base_q = q_from_event

            combined_question = "\n".join([s for s in (base_q, ocr_text) if s]).strip()
            logger.debug(f"astrbot_teacher: extracted question length={len(combined_question)}")
            logger.info(combined_question)
            if not combined_question:
                yield event.plain_result(
                    "未检测到题目文本。请直接在 /g 后输入题目，例如：\n"
                    "/g 求解方程 x^2 + 2x + 1 = 0\n"
                    "或发送 /g 并附带题目图片。"
                )
                return
            else:
                yield event.plain_result("收到！正在处理题目...")

            # 5. 请求解题模型（输出 Markdown）
            solver_model = (self.config or {}).get("solver_model") or None

            solver_system = """你是智能题目讲解助手。你的任务不是只给出结果，而是像一位认真讲题的老师那样，把思路讲清楚，让听的人能跟上、听懂、学会。

如果输入中包含来自图片的 OCR 文本或公式识别结果，请将其与题干内容整合，一并理解后进行讲解。

## 总体目标

输出清晰、准确、逻辑连贯的题目解析。重点在于让人理解推理过程，而非堆砌结论或定义。

## 输出格式 — 纯 Markdown

直接输出 Markdown 格式的讲解内容，不要输出 JSON、代码围栏或其他包装。

建议按以下结构组织（但可根据题目特点灵活调整）：

1. **## 题目分析**：分析知识点、已知条件、求解目标、隐藏信息
2. **## 解题思路**：总体策略、关键直觉、思路转折点
3. **## 详细步骤**：逐步推导，清晰说明每一步的逻辑
4. **## 最终答案**：明确、规范的答案
5. **## 知识点总结**：规律、易错点、思维推广

## 讲解语气与风格

- 像老师在讲黑板题：有节奏，有过渡，有解释
- 使用 Markdown 的标题、列表、引用等语法组织内容
- 核心概念或结论用 **粗体** 强调
- 在思路转折处提示"我们换个角度看""此处需特别注意"等自然过渡
- 不写空洞套话（如"由定义可得"），要点出"为什么这样定义"

## 数学规范 — KaTeX 渲染

### 行间公式

积分、求和、分式、矩阵、对齐推导等复杂表达式使用块级公式：

$$
... 
$$

- 独占一行，上下各留空行
- 块内可使用 `aligned`、`cases` 等环境进行多行排版
- 禁止在块级公式中嵌套 `$...$`

为避免在 Markdown→HTML→KaTeX 管道中 \\ 被吞掉或转义，请严格使用以下约定：

行间（display）公式 使用 $$ ... $$（独占一行，且上/下空行）。

在需要换行处必须使用 \\newline（即反斜杠 + 单词 newline）

不要使用 \\ 或单独 \ 来换行。（说明：模板端会对数学区块做额外保护，但请优先用 \\newline 以避免兼容问题。）

复杂多行结构（cases、aligned 等）仍使用 LaTeX 环境，但换行位置请用 \\newline

	
### 行内公式
- **不得使用\(\)和\[\]包裹任何东西，必须使用 `$...$` 包围**，结束前开始后各留一个空格
- 例如："这是 $ r $ 的半径"
- 仅限简短表达，复杂公式应放入 `$$...$$`
- 正确示例：
  - "函数的值域为 $ g(x) \\in [a,b] $"
  - "设 $ a = 1 $，$ b = 2 $"
  - "在区间 $ x \\in (0, 1) $ 上"
- **错误示例**（不会渲染）：
  - "(g(x) \\in [a,b])" ← 缺少 $ 符号
  - "$g(x) \\in [a,b]$" ← 紧贴文字，缺少空格
  - "\( R \)"← 使用\( \) 语法导致最后渲染不成功
- 行内矩阵公式使用 \displaystyle 保证正常渲染；如：
$\displaystyle
A=\begin{bmatrix}2&1\\1&2\end{bmatrix}
$

### 粗体与符号

- 普通文字用 Markdown：`**文字**`
- 数学符号在公式中使用 `\\mathbf{r}` 或 `\\boldsymbol{\\alpha}`
- 不混用 Markdown 粗体与数学模式

### 表格表达
- 若输出包含结构化数据或对比信息，优先使用表格表达。
- 所有表格使用标准 Markdown 表格语法（不输出 HTML）。
- 表头、列对齐需符合 GitHub Flavored Markdown (GFM) 语法，例如：

| 项目 | 数值 | 单位 |
|------|------:|:----:|
| 长度 | 10 | cm |
| 宽度 | 5 | cm  |

数字列右对齐，文字列左对齐。

- 不在表格外额外加 代码块 标记（```）。

### 分数与一致性

- 优先使用最简分数（ `$ 1/2 $` 而非 `$ 2/4 $` ）
- 简单分式可写作斜线分数；复杂分式使用 `\\frac{a}{b}` 并独立成行

### 多行推导

多步相关推导可写为：

$$
\\begin{aligned}
A &= B + C \\newline
&= D
\\end{aligned}
$$

避免每步单独一个 `$$...$$`。

多步相关推导或分段方程可写为：

$$
\\begin{cases}
A = B + C \\newline
D = E - F
\\end{cases}
$$

⚠️ 注意
-**每行末尾使用 \\newline 来换行（例如：A = B + C \\newline D = E - F）。**
- 避免使用 \\\\，部分 Markdown 渲染器会自动合并或转义它。
- 不要在行尾直接写单反斜杠 `\` 或双反斜杠 `\\`，会导致行间不分行。

### 书写规范与函数格式

- 相邻数字和函数必须显式分隔，如 $ 3 \\ln 2 $、$ \\frac{\\pi}{2} \\cdot 3\\ln 2 $
- 所有函数都需加反斜杠：`\\sin`、`\\cos`、`\\ln`、`\\log`、`\\tan`、`\\exp` 等
- 连乘项需加 `\\cdot` 或空格，避免粘连

## 解释优先级

- 关键决策步骤：说明为什么这样做
- 机械运算步骤：可简略
- 若信息不足，在分析中说明假设或不确定性

针对**数学证明题**的增强要求（必须遵守）

先写明要证明的命题（Theorem），把结论用数学符号写清楚，列出所有已知前提与定义。

若题目涉及特定定义或定理（如柯西不等式、极限定理、拓扑概念等），先列出或引用定义/定理（带简短说明），并在需要时说明可用性与前置条件。

将证明拆成Claim / Lemma / Step：先声明引理，再给出证明（每个引理都写清楚“证明”二字），最后由引理合并得主结论。

对于 归纳法：明确基底（base case）、归纳假设（IH）、归纳步骤（show n→n+1），并检查边界 n 值与可用性。

对于 反证法：写出假设的反面、推导矛盾点，并明确指出矛盾来自何处（与已知条件冲突或违反定义）。

对于 构造性证明：给出构造步骤并证明构造合法性与满足性（包括存在性/唯一性证明）。

说明 必要性与充分性：若命题含双向条件，分清“必要性证明”与“充分性证明”。

提供反例/边界分析：若条件不可省略，给出最小修改导致命题不成立的反例；若命题可放宽，说明如何放宽并给出新的结论。

结尾处写上“证毕”或“QED”。

## 针对 **算法题** 的增强要求（必须遵守）

- 在 **解题思路** 内明确给出算法类型（贪心 / 分治 / 动态规划 / 回溯 / 图算法 / 数学推导 等）以及为什么适用该方法。  
- 给出 **清晰的C++代码**(除非指定用其他语言）（可用缩进的 Markdown 代码块形式），例如：

```Cpp
int main()
{
 return 0;
}
...

复制代码
（注意：最终输出以 Markdown 为主，但不要用反引号包裹整个回答——伪码块可以用三反引号包含伪码段落。）

提供 时间复杂度 与 空间复杂度 的渐进分析（大 O 表示法），并说明最坏/平均/最好情况。

证明算法正确性：给出不变式（invariant）或归纳不变性，证明初始成立、保持性与终止性。

指出 边界条件、特殊输入、以及至少 2 个 示例测试用例（含输入输出），必要时给出手算推导。

若算法有多种实现（例如递归与迭代），简短比较优缺点。

若题目涉及数值精度或近似算法，请说明误差范围与稳定性。

若题目为竞赛/面试风格，给出可提交/可跑的参考代码思路（语言无必须，以伪码为主）并注明关键实现注意点（例如边界索引、整数溢出、并发安全等）。

## 准确性与安全性

- 所有推导逻辑必须可复核；涉及近似须注明范围与理由
- 仅使用 KaTeX 支持的命令；不定义新宏、不写 HTML 标签
- **在任何内容中都不得使用\(\)和\[\]包裹任何东西，必须使用 `$...$` 包围**，结束前开始后各留一个空格
- 对于多行推导，每行末尾使用 \\newline 来换行（例如：A = B + C \\newline D = E - F）。避免使用 \\\\，部分 Markdown 渲染器会自动合并或转义它。
- 矩阵输出时优先使用 \begin{bmatrix}...\end{bmatrix} 而不是 \begin{matrix}
- 行内矩阵使用 \displaystyle 保证正常渲染；如：$ \displaystyle A=\begin{bmatrix} 2 & 1 \\ 1 & 2 \end{bmatrix} $

## 总结

你的目标不是"写报告"，而是"把题讲明白"。像课堂讲题那样，让思路自然展开，每一步都能被理解。
"""

            try:
                solver_resp = await self._text_chat(
                    prov_solver,
                    prompt=combined_question,
                    context=[],
                    system_prompt=solver_system,
                    image_urls=[],
                    model=solver_model,
                )
            except Exception as e:
                emsg = str(e)
                logger.error(f"调用解题模型时出错: {emsg}", exc_info=True)
                
                # 检查是否是 JSON 解析错误
                if "Expecting value" in emsg or "JSON" in emsg:
                    prov_info = getattr(prov_solver, "provider_config", {}) or {}
                    provider_id = prov_info.get("id") or "(unknown)"
                    model_name = solver_model or prov_info.get("model_config", {}).get("model")
                    
                    hint = (
                        "❌ 模型响应解析失败（可能是 API 返回格式问题）\n"
                        f"Provider: {provider_id}\n"
                        f"Model: {model_name}\n"
                        f"错误详情: {emsg}\n\n"
                        "💡 可能的原因:\n"
                        "1. deepseek-reasoner 等推理模型可能返回特殊格式\n"
                        "2. API 返回了错误响应而非正常的聊天完成\n"
                        "3. 网络问题导致响应不完整\n\n"
                        "🔧 建议:\n"
                        "- 尝试切换到 deepseek-chat 等标准模型\n"
                        "- 检查 API key 和网络连接\n"
                        "- 查看 AstrBot 日志获取完整错误信息"
                    )
                    yield event.plain_result(hint)
                    return
                
                if "resource_not_found_error" in emsg or "Not found the model" in emsg:
                    prov_info = getattr(prov_solver, "provider_config", {}) or {}
                    model_hint = solver_model or prov_info.get("model_config", {}).get("model")
                    api_base = prov_info.get("api_base")
                    provider_id = prov_info.get("id") or "(unknown)"
                    hint = (
                        "❌ 解题模型不可用：当前 Provider 未找到该模型或无权限。\n"
                        f"Provider: {provider_id}\nModel: {model_hint}\nAPI Base: {api_base}\n"
                        "请在插件配置中正确设置 solver_provider_id/solver_model，或切换会话 Provider。"
                    )
                    yield event.plain_result(hint)
                    return
                raise

            solver_text = solver_resp.completion_text if solver_resp else ""
            logger.info("Markdown solver output (first 1000 chars): %s", solver_text[:1000])

            if not solver_text:
                yield event.plain_result("❌ 解题模型未返回任何内容。")
                return

            yield event.plain_result("获取完毕，开始渲染...")

            # 6. 不做任何转义，直接传递给模板
            # marked.js 会自动转义代码块中的 HTML 字符（如 <iostream>）
            # Jinja2 注释标记 {# #} 在实际内容中极少出现，暂不处理
            
            # 7. 构建 HTML 渲染数据
            html_data = {
                "question": combined_question,
                "content": solver_text,  # 直接使用原始文本
            }

            # 8. 使用 Star.html_render 或本地渲染生成图片并返回
            prefer_local = bool((self.config or {}).get("prefer_local_render", False))
            local_scale = int((self.config or {}).get("local_device_scale", 2) or 2)

            try:
                final_tpl, _katex_css, _katex_js, _autorender_js, _marked_js = self._build_template()

                html_data_with_assets = {
                    **html_data,
                    "KATEX_CSS": _katex_css,
                    "KATEX_JS": _katex_js,
                    "AUTORENDER_JS": _autorender_js,
                    "MARKED_JS": _marked_js,
                }

                async def do_remote():
                    return await self.html_render(
                        final_tpl,
                        html_data_with_assets,
                        options={
                            "full_page": True,
                            "type": "png",
                            "scale": "device",
                        },
                    )

                async def do_local():
                    html_str = Template(final_tpl).render(**html_data_with_assets)
                    return await self._render_locally(html_str, device_scale=local_scale, full_page=True)

                if prefer_local:
                    try:
                        path = await do_local()
                        yield event.image_result(path)
                    except Exception:
                        logger.exception("本地渲染失败，尝试远端渲染...")
                        url = await do_remote()
                        yield event.image_result(url)
                else:
                    try:
                        url = await do_remote()
                        yield event.image_result(url)
                    except Exception:
                        logger.exception("远端渲染失败，尝试本地渲染...")
                        path = await do_local()
                        yield event.image_result(path)
            except Exception:
                logger.exception("渲染全部失败，退回为文本结果")
                yield event.plain_result(f"题目：\n{combined_question}\n\n{solver_text}")

        except Exception as e:
            logger.exception("处理 /g 指令出错")
            yield event.plain_result(f"发生错误: {e}")

    async def terminate(self):
        logger.info("astrbot_teacher 卸载")
