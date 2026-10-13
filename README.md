# wechat-pdf-rescue

> 你在小程序里只能预览前几页，但完整的 PDF 其实早就躺在硬盘的缓存里了——本工具把它捞出来。

从微信（macOS）小程序 webview 的 HTTP 缓存中提取完整 PDF 文件。

> **一句话原理**：小程序里用 web-view / pdf.js 预览文档时，即使前端只允许你看前几页，
> 完整的 PDF 通常已经通过 HTTP 缓存落盘到本地。本工具直接扫描这些缓存，
> 按 PDF 魔数（`%PDF` … `%%EOF`）切出原始字节流，还原完整文件。

## 特性

- 零依赖：仅使用 Python 标准库，无需 `pip install` 任何东西
- 单文件：一个脚本搞定，复制即用
- 自动识别：从缓存响应头中提取来源 URL，并以其作为输出文件名
- 去重：按 MD5 去重，同一份文件不会重复输出

## 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | macOS |
| 微信 | 4.x（Radium 运行时）；旧版 3.x 路径已作为兜底包含 |
| Python | 3.6+ |

> 注意：终端可能需要**完全磁盘访问权限**才能读取其他 App 的容器目录，详见下文「已知限制」。

## 使用方法

```bash
# 输出到当前目录下的 ./wx_extracted
python3 wx_extract_pdf.py

# 指定输出目录
python3 wx_extract_pdf.py -o ~/Desktop/extracted_pdfs
```

每次运行会扫描全部缓存文件并输出去重后的结果。

## 输出说明

每提取一个文件，终端会打印：

```
[1] ./wx_extracted/example.pdf
    来源 URL : https://.../example.pdf
    大小     : 10,377,369 字节
    页数     : /Count=92  页对象=92
    MD5      : 96b4274be207b0d532dc2e1648c01566
    缓存位置 : /Users/xxx/Library/Containers/com.tencent.xinWeChat/.../090c9d6b4a9e48c3_0
```

- **文件名**：优先取来源 URL 中的原始文件名；无法识别时用 `document.pdf`
- **页数**：`/Count` 是 PDF 页树声明的页数，`页对象` 是正则统计到的页对象个数，两者通常一致

## 工作原理

微信 4.x 的小程序运行时叫 **Radium**，其 webview 使用 Chromium 的 **Simple Cache** 格式：

```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/
  └── radium/web/profiles/<profile>/Cache/Cache_Data/<hash>_0
```

每个缓存数据文件的内容为 `[响应头][响应体]`。PDF 响应体以 `%PDF` 开头、
以 `%%EOF` 结尾，脚本按这两个魔数切片即可还原原始文件，
并从前部的响应头中提取来源 URL。

## 已知限制

1. **权限静默失败**（最常见）
   若终端没有读取 `~/Library/Containers/` 的权限，macOS 会静默拦截，
   `glob` 返回空列表，脚本只提示「未找到 PDF」而**不会报错**。
   解决方法：系统设置 → 隐私与安全性 → 完全磁盘访问权限 →
   勾选你使用的终端 App（Terminal / iTerm / VS Code），然后**重启终端**。

2. **缓存时效性**
   必须先在微信中真正打开过该文档的预览，缓存里才有数据；
   清理过微信缓存后数据即消失，需要重新打开一次。

3. **超大文件可能截断**
   Chromium Simple Cache 对超大响应会拆分为 `<hash>_0 / _1 / _2` 等多个数据文件，
   本脚本目前只读取 `_0`。极大文件可能出现后半部分缺失
   （表现为能打开但页数明显偏少）。

## 免责声明

- 本工具仅读取**已经下发到你本机缓存**的数据，用于个人归档；
  不涉及破解、绕过认证、爬取远程内容等行为。
- 提取出的文档版权归原作者所有，请勿用于传播或商业用途。
- 本项目与腾讯 / 微信官方无关，仅供学习交流。

## License

[MIT](./LICENSE)
