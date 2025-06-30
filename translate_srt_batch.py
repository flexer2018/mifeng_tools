import os
import re
import time
from pathlib import Path

# 已有配置
LLM_BASE_URL = "http://192.168.100.190:10802/v1"
LLM_MODEL = "Qwen3-8B"

from openai import OpenAI

llm_client = OpenAI(
    api_key="sk-YB5OayyI6WE0SbkNPjNlL2qmu2cODuoSDZI9o5dqXVTGSGLu",
    base_url=LLM_BASE_URL,
)

def call_llm_api(prompt, batch_texts):
    """
    批量调用 LLM 模型接口
    :param prompt: 提示词模板
    :param batch_texts: 多条西班牙语句子组成的列表
    :return: 翻译后的中文句子列表，与输入顺序一致
    """
    # 构造输入内容：编号 + 原文
    input_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(batch_texts)])

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": input_text.strip()}
    ]

    try:
        completion = llm_client.chat.completions.create(
            model=LLM_MODEL,
            stream=False,
            messages=messages,
            temperature=0.3
        )
        response = completion.choices[0].message.content.strip()
        print("Raw LLM Response:\n", response)
        
        # 使用正则提取所有翻译结果（支持格式：数字. 中文）
        translated_lines = re.findall(r'\d+\.\s*(.+)', response)
        
        # 如果提取失败，尝试按换行分割
        if not translated_lines:
            translated_lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        return translated_lines[:len(batch_texts)]  # 保证数量对齐

    except Exception as e:
        print(f"API error: {e}")
        return ["[TRANSLATION_FAILED]"] * len(batch_texts)


def parse_srt(file_path):
    """
    解析 SRT 文件内容
    返回一个包含 (index, start_time, end_time, text) 的列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    entries = []
    for match in matches:
        index, start, end, text = match
        text = text.strip().replace('\n', ' ')
        entries.append((index, start, end, text))
    return entries


def load_progress(temp_file):
    """
    加载已翻译的部分条目
    """
    if not os.path.exists(temp_file):
        return set()
    with open(temp_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    translated_indices = set()
    i = 0
    while i < len(lines):
        if '--> ' in lines[i + 1]:
            idx_line = lines[i - 1].strip() if i > 0 else ''
            if idx_line.isdigit():
                translated_indices.add(idx_line)
            i += 4
        else:
            i += 1
    return translated_indices


def translate_in_batches(entries, prompt_template, temp_file, batch_size=20):
    """
    分批次翻译字幕条目，每批 batch_size 句合并成一次请求
    """
    all_indices = {entry[0] for entry in entries}
    already_translated = load_progress(temp_file)
    remaining_entries = [e for e in entries if e[0] not in already_translated]

    total = len(remaining_entries)
    print(f"Total sentences to translate: {total}")

    for i in range(0, total, batch_size):
        batch = remaining_entries[i:i + batch_size]
        batch_texts = [entry[3] for entry in batch]

        print(f"\nTranslating batch {i // batch_size + 1}: {len(batch)} sentences")
        translations = call_llm_api(prompt_template, batch_texts)

        # 对齐并写入临时文件
        translated_batch = []
        for j, entry in enumerate(batch):
            index, start, end, _ = entry
            translation = translations[j] if j < len(translations) else "[TRANSLATION_FAILED]"
            translated_batch.append((index, start, end, translation))

        write_temp_file(translated_batch, temp_file)
        print(f"Saved batch {i // batch_size + 1} to {temp_file}")
        time.sleep(0.1)

    print("All batches processed.")


def write_temp_file(translated_entries, temp_file):
    """
    将当前翻译结果追加写入临时文件
    """
    mode = 'a' if os.path.exists(temp_file) else 'w'
    with open(temp_file, mode, encoding='utf-8') as f:
        for entry in translated_entries:
            index, start, end, translation = entry
            f.write(f"{index}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{translation}\n\n")


def merge_temp_to_final(temp_file, output_file, all_entries):
    """
    合并临时文件与所有条目，确保顺序正确
    """
    translated_dict = {}
    if os.path.exists(temp_file):
        entries = parse_srt(temp_file)
        for entry in entries:
            index, start, end, translation = entry
            translated_dict[index] = translation

    final_output = []
    for entry in all_entries:
        index, start, end, text = entry
        translation = translated_dict.get(index, "[MISSING]")
        final_output.append((index, start, end, translation))

    write_translated_srt(final_output, output_file)
    print(f"Final output written to {output_file}")


def write_translated_srt(translated_entries, output_path):
    """
    将翻译后的内容写入新的 SRT 文件
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in translated_entries:
            index, start, end, translation = entry
            f.write(f"{index}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{translation}\n\n")


def main():
    input_srt = "Rzc0PnbSGb0.srt"       # 输入的西班牙语字幕文件
    output_srt = "Rzc0PnbSGb0_translated_zh_batch.srt" # 输出的中文翻译字幕文件
    temp_file = "temp_progress_batch.srt"   # 临时保存的翻译进度文件

    # 提示词模板
    prompt_template = (
        "你是专业的字幕翻译员。请将以下西班牙语句子准确、自然地翻译为中文。\n"
        "每句话前都有编号，请按照相同编号顺序逐行给出翻译结果，不要添加任何解释或格式。\n"
        "保持翻译简洁清晰，适合视频播放场景。\n"
        "例如：\n"
        "1. Hola\n"
        "2. ¿Cómo estás?\n"
        "-->\n"
        "1. 你好\n"
        "2. 你好吗？\n"
    )

    entries = parse_srt(input_srt)
    translate_in_batches(entries, prompt_template, temp_file, batch_size=20)
    merge_temp_to_final(temp_file, output_srt, entries)


if __name__ == "__main__":
    main()