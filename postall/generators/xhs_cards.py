#!/usr/bin/env python3
"""
小红书卡片生成器
PostAll 集成版本

用法:
    from postall.generators.xhs_cards import generate_xhs_cards
    generate_xhs_cards(
        wechat_md_path="/path/to/wechat_content.md",
        cover_image_path="/path/to/image.png",
        output_dir="/path/to/xhs-cards/",
        cover_title="标题文字"
    )
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import re
import random

# 卡片尺寸 3:4 比例
CARD_WIDTH = 900
CARD_HEIGHT = 1200

# 边距
MARGIN_LEFT = 80
MARGIN_RIGHT = 80
MARGIN_TOP = 120
MARGIN_BOTTOM = 120
CONTENT_WIDTH = CARD_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

# PostAll 暖色调配色
BG_COLOR = "#FDF6EE"
TEXT_COLOR = "#2D2D2D"
ACCENT_COLOR = "#E07B54"
SECONDARY_COLOR = "#8B7355"
HIGHLIGHT_BG = "#FEF0E5"

# 装饰色块颜色
DECOR_COLORS = ["#F4A460", "#E8956A", "#D4886A", "#C9A87C", "#E6C4A8"]

# 标签条颜色
LABEL_BG = "#FDF5E8"
LABEL_SHADOW = "#D4C4B0"

# 字体路径
FONT_PATHS_BOLD = [
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
FONT_PATHS_REGULAR = [
    "/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
FONT_HANDWRITE_PATH = "/usr/share/fonts/custom/LXGWWenKai-Regular.ttf"

def _load_font(bold=False, size=36):
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def _load_handwrite_font(size=72):
    try:
        return ImageFont.truetype(FONT_HANDWRITE_PATH, size)
    except:
        return _load_font(bold=True, size=size)

# 预加载字体
FONT_SECTION = _load_font(bold=True, size=36)
FONT_BODY = _load_font(bold=False, size=28)
FONT_BOLD = _load_font(bold=True, size=28)
FONT_SMALL = _load_font(bold=False, size=22)
FONT_COVER = _load_handwrite_font(72)

def _get_char_width(draw, char, font):
    bbox = draw.textbbox((0, 0), char, font=font)
    return bbox[2] - bbox[0]

def _wrap_text_to_lines(draw, text, font, max_width):
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph.strip():
            lines.append('')
            continue
        current_line = ''
        current_width = 0
        for char in paragraph:
            char_width = _get_char_width(draw, char, font)
            if current_width + char_width > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
                current_width = char_width
            else:
                current_line += char
                current_width += char_width
        if current_line:
            lines.append(current_line)
    return lines

def _draw_decorations(draw, card_num):
    random.seed(card_num * 42)
    
    color1 = random.choice(DECOR_COLORS)
    draw.polygon([(0, 0), (180, 0), (0, 140)], fill=color1)
    
    color2 = random.choice(DECOR_COLORS)
    draw.polygon([(CARD_WIDTH, 0), (CARD_WIDTH - 120, 0), (CARD_WIDTH, 90)], fill=color2)
    
    color3 = random.choice(DECOR_COLORS)
    draw.polygon([(CARD_WIDTH, CARD_HEIGHT), (CARD_WIDTH - 200, CARD_HEIGHT), (CARD_WIDTH, CARD_HEIGHT - 160)], fill=color3)
    
    color4 = random.choice(DECOR_COLORS)
    draw.polygon([(0, CARD_HEIGHT), (100, CARD_HEIGHT), (0, CARD_HEIGHT - 80)], fill=color4)

def _draw_bold_text(draw, text, x, y, font, fill):
    """模拟粗体"""
    for ox, oy in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2)]:
        draw.text((x + ox, y + oy), text, font=font, fill=fill)

def _draw_label_strip(draw, text, center_x, y, font):
    """绘制纸带标签"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    padding_x, padding_y = 40, 18
    strip_width = text_width + padding_x * 2 + 10
    strip_height = text_height + padding_y * 2
    
    strip_x = center_x - strip_width // 2
    strip_y = y
    
    # 阴影
    draw.rectangle(
        [(strip_x + 6, strip_y + 6), (strip_x + strip_width + 6, strip_y + strip_height + 6)],
        fill=LABEL_SHADOW
    )
    # 标签条
    draw.rectangle(
        [(strip_x, strip_y), (strip_x + strip_width, strip_y + strip_height)],
        fill=LABEL_BG, outline='#C9B89D', width=2
    )
    # 粗体文字
    _draw_bold_text(draw, text, strip_x + padding_x, strip_y + padding_y - 10, font, '#3D3D3D')
    
    return strip_height + 20

def _extract_body_content(content):
    """提取正文，去除 metadata 和 Image Prompt"""
    lines = content.split('\n')
    body_lines = []
    in_body = False
    skip_image_prompt = False
    found_first_content = False
    
    skip_patterns = [
        r'^\*\*Post Type:\*\*', r'^\*\*Theme:\*\*', r'^\*\*Day:\*\*',
        r'^\*\*Generated:\*\*', r'^\*\*Posting Time:\*\*', r'^\*\*Content Pillar:\*\*',
        r'^## WeChat Article', r'^### Image Prompt', r'^🤖', r'^📚', r'^---$',
    ]
    
    for line in lines:
        stripped = line.strip()
        
        if '### Image Prompt' in stripped or 'Image Prompt' in stripped:
            skip_image_prompt = True
            continue
        if skip_image_prompt:
            continue
        
        skip = any(re.match(p, stripped) for p in skip_patterns)
        if skip:
            continue
        
        # 跳过纯英文长段落
        if stripped and len(stripped) > 50:
            eng = sum(1 for c in stripped if c.isascii() and c.isalpha())
            total = sum(1 for c in stripped if c.isalpha())
            if total > 0 and eng / total > 0.8:
                continue
        
        # 检测正文开始：# 标题 或者第一个非空内容行
        if stripped.startswith('# ') and not stripped.startswith('## '):
            in_body = True
        elif not in_body and stripped and not found_first_content:
            # 如果没有 # 标题，从第一个非空内容行开始（跳过 metadata 后）
            # 检查是否是普通中文段落（不是 metadata）
            if not stripped.startswith('**') and not stripped.startswith('#'):
                in_body = True
                found_first_content = True
        
        if in_body:
            body_lines.append(line)
    
    return '\n'.join(body_lines)

def _parse_content_to_elements(content):
    elements = []
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped:
            elements.append(('space', ''))
        elif stripped.startswith('# ') and not stripped.startswith('## '):
            continue
        elif stripped.startswith('### '):
            elements.append(('section', stripped[4:]))
        elif stripped.startswith('**') and stripped.endswith('**'):
            elements.append(('bold', stripped.strip('*')))
        elif stripped.startswith('- ') or stripped.startswith('• '):
            elements.append(('bullet', stripped.lstrip('-• ')))
        elif re.match(r'^\d+\.\s', stripped):
            elements.append(('numbered', stripped))
        else:
            elements.append(('text', stripped))
    return elements

def _render_elements_to_cards(elements):
    cards_data = []
    current_card = []
    current_y = MARGIN_TOP
    max_y = CARD_HEIGHT - MARGIN_BOTTOM
    
    temp_img = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(temp_img)
    
    line_height_body = 42
    line_height_section = 52
    
    for elem_type, elem_text in elements:
        if elem_type == 'space':
            needed_height = 18
        elif elem_type == 'section':
            lines = _wrap_text_to_lines(draw, elem_text, FONT_SECTION, CONTENT_WIDTH)
            needed_height = len(lines) * line_height_section + 35
        elif elem_type == 'bold':
            lines = _wrap_text_to_lines(draw, elem_text, FONT_BOLD, CONTENT_WIDTH - 20)
            needed_height = len(lines) * line_height_body + 20
        elif elem_type == 'bullet':
            lines = _wrap_text_to_lines(draw, elem_text, FONT_BODY, CONTENT_WIDTH - 28)
            needed_height = len(lines) * line_height_body + 10
        elif elem_type == 'numbered':
            lines = _wrap_text_to_lines(draw, elem_text, FONT_BODY, CONTENT_WIDTH)
            needed_height = len(lines) * line_height_body + 10
        else:  # text
            if not elem_text:
                continue
            lines = _wrap_text_to_lines(draw, elem_text, FONT_BODY, CONTENT_WIDTH)
            needed_height = len(lines) * line_height_body + 14
        
        if elem_type != 'space':
            if current_y + needed_height > max_y and current_card:
                cards_data.append(current_card)
                current_card = []
                current_y = MARGIN_TOP
            current_card.append((elem_type, lines if elem_type != 'space' else '', needed_height))
        else:
            current_card.append((elem_type, '', needed_height))
        
        current_y += needed_height
    
    if current_card:
        cards_data.append(current_card)
    
    return cards_data

def _create_content_card(card_elements, card_num, total_cards):
    card = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(card)
    
    _draw_decorations(draw, card_num)
    
    # 卡片编号
    num_text = f"{card_num}/{total_cards}"
    bbox = draw.textbbox((0, 0), num_text, font=FONT_SMALL)
    draw.text((CARD_WIDTH - MARGIN_RIGHT - (bbox[2] - bbox[0]) + 10, MARGIN_TOP - 35),
              num_text, font=FONT_SMALL, fill=SECONDARY_COLOR)
    
    y = MARGIN_TOP
    line_height_body = 42
    line_height_section = 52
    
    for elem_type, lines_or_text, height in card_elements:
        if elem_type == 'space':
            y += 18
        elif elem_type == 'section':
            if y > MARGIN_TOP + 30:
                draw.rectangle([(MARGIN_LEFT, y - 8), (CARD_WIDTH - MARGIN_RIGHT, y - 6)], fill="#E8D5C4")
            y += 12
            for line in lines_or_text:
                draw.text((MARGIN_LEFT, y), line, font=FONT_SECTION, fill=ACCENT_COLOR)
                y += line_height_section
            y += 18
        elif elem_type == 'bold':
            box_height = len(lines_or_text) * line_height_body + 16
            draw.rectangle([(MARGIN_LEFT - 12, y - 8), (CARD_WIDTH - MARGIN_RIGHT + 12, y + box_height - 8)], fill=HIGHLIGHT_BG)
            draw.rectangle([(MARGIN_LEFT - 12, y - 8), (MARGIN_LEFT - 6, y + box_height - 8)], fill=ACCENT_COLOR)
            for line in lines_or_text:
                draw.text((MARGIN_LEFT + 5, y), line, font=FONT_BOLD, fill=TEXT_COLOR)
                y += line_height_body
            y += 18
        elif elem_type == 'bullet':
            draw.ellipse([(MARGIN_LEFT, y + 12), (MARGIN_LEFT + 10, y + 22)], fill=ACCENT_COLOR)
            for line in lines_or_text:
                draw.text((MARGIN_LEFT + 28, y), line, font=FONT_BODY, fill=TEXT_COLOR)
                y += line_height_body
            y += 6
        elif elem_type == 'numbered':
            for line in lines_or_text:
                draw.text((MARGIN_LEFT, y), line, font=FONT_BODY, fill=TEXT_COLOR)
                y += line_height_body
            y += 6
        else:  # text
            for line in lines_or_text:
                draw.text((MARGIN_LEFT, y), line, font=FONT_BODY, fill=TEXT_COLOR)
                y += line_height_body
            y += 10
    
    return card

def _create_cover_card(image_path, title):
    """创建封面 - 纸带标签风格"""
    img = Image.open(image_path)
    
    # 裁剪 3:4
    img_ratio = img.width / img.height
    target_ratio = CARD_WIDTH / CARD_HEIGHT
    if img_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))
    
    img = img.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    
    # 分行（每行约6-8个字）
    lines = []
    current = ""
    for char in title:
        current += char
        if len(current) >= 7:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    
    # 绘制标签条
    y = CARD_HEIGHT - len(lines) * 100 - 80
    center_x = CARD_WIDTH // 2
    
    for i, line in enumerate(lines):
        offset = [-20, 15, -8, 10][i % 4]
        height = _draw_label_strip(draw, line, center_x + offset, y, FONT_COVER)
        y += height
    
    return img

def generate_xhs_cards(wechat_md_path, cover_image_path, output_dir, cover_title):
    """
    生成小红书卡片
    
    Args:
        wechat_md_path: 微信文章 markdown 文件路径
        cover_image_path: 封面配图路径
        output_dir: 输出目录
        cover_title: 封面标题文字
    
    Returns:
        dict: {"success": bool, "total_cards": int, "output_dir": str}
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取微信文章
        with open(wechat_md_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        
        # 提取正文
        body_content = _extract_body_content(raw_content)
        elements = _parse_content_to_elements(body_content)
        cards_data = _render_elements_to_cards(elements)
        total_cards = len(cards_data) + 1
        
        # 生成封面
        cover = _create_cover_card(cover_image_path, cover_title)
        cover.save(output_dir / "card_01_cover.png")
        
        # 生成内容卡片
        for i, card_elements in enumerate(cards_data, start=2):
            card = _create_content_card(card_elements, i, total_cards)
            card.save(output_dir / f"card_{i:02d}.png")
        
        return {
            "success": True,
            "total_cards": total_cards,
            "output_dir": str(output_dir)
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def extract_title_from_wechat(wechat_md_path):
    """从微信文章中提取标题"""
    with open(wechat_md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 尝试从 # 标题提取
    match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # 尝试从 ## WeChat Article - 标题 提取
    match = re.search(r'## WeChat Article - (.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    return "小红书文章"

if __name__ == "__main__":
    # 测试
    result = generate_xhs_cards(
        wechat_md_path="/opt/postall/projects/tar/output/single_topics/knowledge_business/wechat-posts/wechat_content.md",
        cover_image_path="/opt/postall/projects/tar/output/single_topics/knowledge_business/image.png",
        output_dir="/tmp/xhs_test",
        cover_title="把知识变成百万生意的5种模式"
    )
    print(result)
