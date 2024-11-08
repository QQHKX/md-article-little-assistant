import os
import re
import hashlib
import shutil
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from PIL import Image, UnidentifiedImageError
from urllib.parse import urlsplit, unquote
from typing import Optional, Tuple, Dict, Set

class ImageProcessor:
    def __init__(self, output_root: str = "output"):
        """
        初始化图片处理器
        
        Args:
            output_root: 输出根目录
        """
        self.output_root = Path(output_root)
        self.setup_logging()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def setup_logging(self):
        """配置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('image_processor.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def identify_image_host(self, url: str) -> str:
        """
        识别图片主机
        
        Args:
            url: 图片URL
        
        Returns:
            str: 主机名称
        """
        hostname = urlsplit(url).hostname
        return hostname or "unknown_host"

    def download_image(self, url: str, folder_path: Path, image_name: str) -> Optional[Path]:
        """
        下载图片到指定路径
        
        Args:
            url: 图片URL
            folder_path: 保存文件夹路径
            image_name: 图片名称
        
        Returns:
            Optional[Path]: 保存的图片路径
        """
        try:
            response = self.session.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            # 从响应头获取实际文件扩展名
            content_type = response.headers.get('content-type', '')
            ext = self.get_extension_from_content_type(content_type)
            if not ext:
                ext = Path(unquote(urlsplit(url).path)).suffix or '.jpg'
            
            image_path = folder_path / f"{Path(image_name).stem}{ext}"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.logger.info(f"Downloaded: {url} -> {image_path}")
            return image_path
            
        except Exception as e:
            self.logger.error(f"Download failed: {url}, error: {str(e)}")
            return None

    def get_extension_from_content_type(self, content_type: str) -> str:
        """
        从Content-Type获取文件扩展名
        
        Args:
            content_type: HTTP响应的Content-Type
            
        Returns:
            str: 文件扩展名
        """
        content_type = content_type.lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'webp' in content_type:
            return '.webp'
        return ''

    def convert_to_jpg(self, image_path: Path) -> Path:
        """
        将图片转换为JPG格式
        
        Args:
            image_path: 原图片路径
            
        Returns:
            Path: 转换后的图片路径
        """
        try:
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    # 处理透明背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1])
                    img = background
                
                jpg_path = image_path.with_suffix('.jpg')
                img.convert("RGB").save(jpg_path, "JPEG", quality=95)
                
            image_path.unlink()  # 删除原始文件
            self.logger.info(f"Converted to JPG: {jpg_path}")
            return jpg_path
            
        except Exception as e:
            self.logger.error(f"Conversion failed: {image_path}, error: {str(e)}")
            return image_path

    def is_animated(self, image_path: Path) -> bool:
        """
        检查是否为动态图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            bool: 是否为动态图片
        """
        try:
            with Image.open(image_path) as img:
                return hasattr(img, 'is_animated') and img.is_animated
        except Exception:
            return False

    def process_markdown(self, file_path: Path) -> Tuple[str, Dict[str, Set[str]]]:
        """
        处理Markdown文件中的图片
        
        Args:
            file_path: Markdown文件路径
            
        Returns:
            Tuple[str, Dict[str, Set[str]]]: 处理后的内容和图片统计信息
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用更强大的正则表达式匹配图片链接
        image_links = set(re.findall(r'!\[([^\]]*)\]\((https?://[^\s"\']+)(?:\s+"[^"]*")?\)', content))
        self.logger.info(f"Found {len(image_links)} image links")

        # 创建临时目录
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)

        # 统计信息
        stats = {
            "successful": set(),
            "failed": set(),
            "skipped": set()
        }

        # 并发下载和处理图片
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {}
            for alt_text, url in image_links:
                future = executor.submit(self.process_single_image, url, temp_dir, alt_text)
                future_to_url[future] = (url, alt_text)

            for future in as_completed(future_to_url):
                url, alt_text = future_to_url[future]
                try:
                    result, new_path = future.result()
                    if result == "success":
                        stats["successful"].add(url)
                        # 更新图片链接
                        old_link = f'![{alt_text}]({url})'
                        new_link = f'![{alt_text}](images/{Path(new_path).name})'
                        content = content.replace(old_link, new_link)
                    elif result == "skipped":
                        stats["skipped"].add(url)
                    else:
                        stats["failed"].add(url)
                except Exception as e:
                    self.logger.error(f"Error processing {url}: {str(e)}")
                    stats["failed"].add(url)

        return content, stats

    def process_single_image(self, url: str, temp_dir: Path, alt_text: str) -> Tuple[str, Optional[str]]:
        """
        处理单个图片
        
        Args:
            url: 图片URL
            temp_dir: 临时目录
            alt_text: 图片alt文本
            
        Returns:
            Tuple[str, Optional[str]]: 处理结果和新路径
        """
        safe_filename = self.get_safe_filename(alt_text or url)
        image_path = self.download_image(url, temp_dir, safe_filename)
        
        if not image_path:
            return "failed", None
            
        if image_path.suffix.lower() != '.jpg' and not self.is_animated(image_path):
            image_path = self.convert_to_jpg(image_path)
            
        return "success", image_path.as_posix()

    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """
        生成安全的文件名
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 安全的文件名
        """
        # 移除非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制长度
        return filename[:100]

    def process_file(self, file_path: str):
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
        """
        file_path = Path(file_path)
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return

        try:
            # 处理文件内容
            content, stats = self.process_markdown(file_path)
            
            # 生成输出目录
            content_hash = hashlib.md5(content.encode()).hexdigest()
            output_dir = self.output_root / content_hash
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 移动图片文件
            if Path("temp_images").exists():
                shutil.move("temp_images", output_dir / "images")
            
            # 保存处理后的文件
            output_file = output_dir / file_path.name
            output_file.write_text(content, encoding='utf-8')
            
            # 输出统计信息
            self.logger.info(f"""
Processing completed:
- Output directory: {output_dir}
- Successfully processed: {len(stats['successful'])} images
- Skipped: {len(stats['skipped'])} images
- Failed: {len(stats['failed'])} images
            """.strip())
            
        except Exception as e:
            self.logger.error(f"Processing failed: {str(e)}")
            if Path("temp_images").exists():
                shutil.rmtree("temp_images")

def main():
    processor = ImageProcessor()
    processor.process_file("md.md")

if __name__ == "__main__":
    main()