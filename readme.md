# 图片处理器

该项目是一个用于处理 Markdown 文件中的图片链接并下载图片的工具。它能够自动下载图片、将非 JPG 图片转换为 JPG 格式，并更新 Markdown 文件中的图片链接为本地路径。支持并发下载，提高处理效率。

## 特性

- **图片下载**: 支持从 URL 下载图片并保存到本地。
- **格式转换**: 自动将非 JPG 格式的图片转换为 JPG 格式（支持 PNG、GIF、WEBP 等）。
- **动态图片检测**: 检测 GIF 等动态图片，跳过不适合转换的格式。
- **并发下载**: 使用线程池并发处理多个图片，提高下载速度。
- **Markdown 文件处理**: 处理 Markdown 文件中的图片链接，替换为本地路径。

## 安装

1. 克隆本项目到本地：
   ```bash
   git clone https://github.com/yourusername/image-processor.git
   ```
2. 进入项目目录：
   ```bash
   cd image-processor
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用

### 1. 处理单个 Markdown 文件

```python
from image_processor import ImageProcessor

# 创建ImageProcessor实例
processor = ImageProcessor(output_root="output")

# 处理Markdown文件
processor.process_file("md.md")
```

### 2. 自动下载和转换图片

- 所有在 Markdown 文件中通过`![alt文本](图片URL)`形式的图片链接都会被下载。
- 下载的图片如果不是 JPG 格式，将会被转换为 JPG。
- 处理后的图片会被保存在`output`目录下，并且 Markdown 文件中的图片链接会被更新为本地路径。

## 配置

你可以在初始化`ImageProcessor`时自定义输出目录：

```python
processor = ImageProcessor(output_root="custom_output")
```

默认的输出目录为`output`。

## 日志

处理过程中会生成日志文件`image_processor.log`，你可以通过该文件查看处理状态和任何错误信息。

## 依赖

- `requests`：用于下载图片。
- `Pillow`：用于处理图片格式转换。
- `concurrent.futures`：用于并发下载图片。
- `pathlib`：用于路径操作。
- `re`：用于正则表达式匹配图片链接。

## 贡献

如果你有任何建议或问题，欢迎提交[issue](https://github.com/yourusername/image-processor/issues)或者直接提交 pull request。

## 开源许可

该项目使用[MIT 许可证](LICENSE)。

---

这个模板已经去除了代码框，你可以根据实际需要修改项目的链接、许可证等信息。
