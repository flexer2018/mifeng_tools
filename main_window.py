# Utf8
import os
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, QTextEdit, QFileDialog, QMessageBox, QComboBox, QLineEdit, QTabWidget

import shutil
# 在文件顶部添加 yt_dlp 导入
import yt_dlp

import os
import subprocess
import requests
import time
import re

from openai import OpenAI
import configparser

if not os.path.exists('config.ini'):
    QMessageBox.critical(None, "错误", "找不到配置文件 config.ini，请检查程序目录")
    sys.exit(1)


# 加载配置文件
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

# LLM 配置
LLM_BASE_URL = config.get('LLM', 'BASE_URL')
LLM_MODEL = config.get('LLM', 'MODEL')
LLM_API_KEY = config.get('LLM', 'API_KEY')

# ASR 配置
ASR_URL = config.get('ASR', 'URL')


llm_client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)

# 导入现有功能模块的函数
def download_ts_file(url, filename):
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Connection": "keep-alive",
        "DNT": "1",
        "Origin": "https://www.skynews.com.au",
        "Referer": "https://www.skynews.com.au/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        "sec-ch-ua": "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    try:
        response = requests.get(url, stream=True, headers=headers, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {filename}, 错误: {e}")
        return False


def resource_path(relative_path):
    """ 获取资源的绝对路径，适用于 PyInstaller 打包后的环境 """
    if getattr(sys, 'frozen', False):  # 判断是否是打包后的环境
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 示例：获取 ffmpeg 路径
# ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg.exe")

# # 示例：获取 cookies 路径
# cookies_dir = resource_path("cookies")

def extract_audio_from_video(video_file_path, audio_file_path):
    start_time = time.time()
    command = [
        r".\ffmpeg\bin\ffmpeg",
        "-i", video_file_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        # "-ac", "1",
        "-b:a", "64k",
        "-aq", "5",  # 强制 VBR 质量等级，对应约 32kbps
        audio_file_path,
        "-y"
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    end_time = time.time()
    return end_time - start_time


def recognize_audio(audio_file_path, output_format="txt", params=None):
    if params is None:
        params = {"task": "transcribe", "output": output_format}

    start_time = time.time()
    with open(audio_file_path, "rb") as audio_file:
        files = {"audio_file": audio_file}
        response = requests.post(ASR_URL, params=params, files=files)

    end_time = time.time()
    if response.status_code == 200:
        return response.text, end_time - start_time
    else:
        return {"error": response.text}, end_time - start_time
    
def call_llm_api(prompt,content):
    """
    调用 LLM 模型接口
    :param prompt: 输入文本
    :param task: 任务类型（"translation"）
    :return: LLM 的输出结果
    """
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content.replace('\n\n', '')}
    ]
    # 调用模型
    completion = llm_client.chat.completions.create(
        model=LLM_MODEL,
        # model="Qwen/Qwen3-32B",
        stream=False,
        messages=messages,
        temperature=0.5
    )
    
    print(completion)
    return completion.choices[0].message.content

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("蜜蜂-视频处理工具箱")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 添加各个功能页面
        self.video_download_tab = VideoDownloadTab()
        self.audio_extract_tab = AudioExtractTab()
        self.text_translate_tab = TextTranslateTab()
        self.summary_tab = SummaryTab()
        self.subtitle_translate_tab = SubtitleTranslateTab()
        
        self.tabs.addTab(self.video_download_tab, "视频下载")
        self.tabs.addTab(self.audio_extract_tab, "音频抽取")
        self.tabs.addTab(self.text_translate_tab, "文本转录与翻译")
        self.tabs.addTab(self.summary_tab, "内容摘要")
        self.tabs.addTab(self.subtitle_translate_tab, "字幕翻译")

        # 创建主布局
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        
        central_widget.setLayout(layout)

class VideoDownloadTab(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        # URL输入
        url_layout = QHBoxLayout()
        self.url_label = QLabel("视频URL:")
        self.url_input = QLineEdit("https://www.youtube.com/watch?v=bxv-8BA7nQM")
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)
        
        # 输出目录选择
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("保存目录:")
        self.dir_input = QLineEdit()
        self.dir_button = QPushButton("选择")
        self.dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_button)
        
        # 下载模式选择
        mode_layout = QHBoxLayout()
        
        # 视频质量选择（仅适用于yt-dlp下载）
        quality_layout = QHBoxLayout()
        self.quality_label = QLabel("视频质量:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["最好", "1080p", "720p", "480p", "360p"])
        quality_layout.addWidget(self.quality_label)
        quality_layout.addWidget(self.quality_combo)
        
        # 下载按钮
        self.download_button = QPushButton("开始下载")
        self.download_button.clicked.connect(self.start_download)
        
        # 进度条
        self.progress_bar = QProgressBar()
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # 添加到主布局
        layout.addLayout(url_layout)
        layout.addLayout(dir_layout)
        layout.addLayout(mode_layout)
        layout.addLayout(quality_layout)
        layout.addWidget(self.download_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if directory:
            self.dir_input.setText(directory)
    
    def start_download(self):
        url = self.url_input.text()
        directory = self.dir_input.text()
       
        if not url or not directory:
            QMessageBox.warning(self, "错误", "请输入URL和选择保存目录")
            return

        # 启动yt-dlp下载线程
        selected_quality = self.quality_combo.currentText() if hasattr(self, 'quality_combo') else "最好"
        self.download_thread = YTDLPDownloadThread(url, directory, selected_quality)
        
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.log_updated.connect(self.update_log)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.start()
        
        self.download_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        self.log_output.append(message)
    
    def download_finished(self, success, message):
        self.download_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "错误", message)


class YTDLPDownloadThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    def __init__(self, url, output_dir, quality="最好"):
        super(YTDLPDownloadThread, self).__init__()
        self.url = url
        self.output_dir = self.normalize_path(output_dir)
        self.quality = quality
        self.last_progress = 0
    
    def normalize_path(self, path):
        """确保路径存在并返回规范化路径"""
        norm_path = os.path.normpath(path)
        if not os.path.exists(norm_path):
            try:
                os.makedirs(norm_path)
            except Exception as e:
                print(f"创建目录失败: {norm_path}, 错误: {e}")
        return norm_path
    
    def get_cookies_file(self):
        """根据URL自动匹配cookies文件"""
        from urllib.parse import urlparse
        domain = urlparse(self.url).hostname or ""
        
        if not domain:
            return None
            
        # 构建cookies目录路径
        cookies_dir = os.path.join(os.path.dirname(sys.argv[0]), "cookies")
        
        # 构建可能的cookies文件名
        possible_filenames = [
            f"{domain}_cookies.txt",
            f"{domain.split('.')[1]}_cookies.txt",
            "youtube.com_cookies.txt",
            "bilibili.com_cookies.txt"
        ]
        
        # 查找存在的cookies文件
        for filename in possible_filenames:
            cookies_path = os.path.join(cookies_dir, filename)
            if os.path.exists(cookies_path):
                return cookies_path
                
        return None
    def get_format_selector(self):
        if self.quality == "最好":
            return None  # 默认最佳格式
        else:
            target_resolution = int(self.quality.replace('p', ''))

            def format_selector(ctx):
                formats = sorted(ctx.get('formats'), key=lambda f: (
                    f.get('height', 0) <= target_resolution,
                    f.get('vcodec') != 'none',
                    f.get('acodec') != 'none',
                    f.get('ext') == 'mp4'
                ), reverse=True)

                best_video = next((f for f in formats if f['vcodec'] != 'none' and f['acodec'] == 'none' and f.get('height', 0) <= target_resolution), None)
                if not best_video:
                    best_video = next((f for f in formats if f['vcodec'] != 'none' and f['acodec'] == 'none'), None)

                if not best_video:
                    return []

                audio_ext = {'mp4': 'm4a', 'webm': 'webm'}.get(best_video['ext'], 'webm')
                best_audio = next((f for f in formats if f['acodec'] != 'none' and f['vcodec'] == 'none' and f['ext'] == audio_ext), None)

                if best_audio:
                    return [{
                        'format_id': f"{best_video['format_id']}+{best_audio['format_id']}",
                        'ext': 'mp4',
                        'requested_formats': [best_video, best_audio],
                        'protocol': f"{best_video['protocol']}+{best_audio['protocol']}"
                    }]
                else:
                    return [best_video]

            return format_selector
    def run(self):
        try:
            script_dir = os.path.dirname(sys.argv[0])
            ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg.exe")

            if not os.path.exists(ffmpeg_path):
                raise Exception("FFmpeg未找到，请检查安装路径")

            os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

            cookies_file = self.get_cookies_file()
            if cookies_file:
                self.log_updated.emit(f"使用Cookies文件: {cookies_file}")

            # output_path = os.path.join(self.output_dir, '%(title)s.%(ext)s')
            temp_download_dir = os.path.join(self.output_dir, '_temp_download')
            self.log_updated.emit(f"保存目录{temp_download_dir}")
            os.makedirs(temp_download_dir, exist_ok=True)
            self.log_updated.emit(f"创建保存目录{temp_download_dir}完成")
            
            ydl_opts = {
                'outtmpl': os.path.join(temp_download_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [self.progress_hook],
                'format': self.get_format_selector(),
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'srt',
                'subtitleslangs': ['en', 'zh'],
                'keepvideo': False,  # 不保留中间视频文件
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
                'headers': {'Accept-Language': 'en-US,en;q=0.9'},
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_path,
            }

            if cookies_file:
                ydl_opts['cookiefile'] = cookies_file

            self.progress_updated.emit(30)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.progress_updated.emit(40)
                self.log_updated.emit("开始下载视频...")
                ydl.download([self.url])
                self.progress_updated.emit(80)

            
            # 查找 .mp4 视频文件
            video_file = None
            for filename in os.listdir(temp_download_dir):
                if filename.endswith('.mp4'):
                    video_file = os.path.join(temp_download_dir, filename)
                    break

            if not video_file:
                raise Exception("未找到下载的视频文件")

            # 构建目标路径
            base_name = os.path.splitext(os.path.basename(video_file))[0]
            # target_video_file = os.path.join(self.output_dir, f"{base_name}.mp4")

            self.log_updated.emit(f"移动动作 {video_file}...")
            # audio_file_path = os.path.join(self.output_dir, f"{base_name}.mp3")

            # 构建项目文件夹并移动文件
            project_folder_name = re.sub(r'[\\/:*?"<>|]', '_', os.path.splitext(os.path.basename(video_file))[0][:15])
            project_folder_path = os.path.join(self.output_dir, project_folder_name)
            os.makedirs(project_folder_path, exist_ok=True)
            target_video_file = os.path.join(project_folder_path, os.path.basename(video_file))
            shutil.move(video_file,target_video_file )
            self.log_updated.emit( f"视频已保存到文件夹:{project_folder_path} ") 
            temp_audio_file = os.path.join(project_folder_path, f"{base_name}.mp3")
            extract_time = extract_audio_from_video(target_video_file, temp_audio_file)            
            self.log_updated.emit( f"抽取音频已保存到文件夹: {temp_audio_file} 用时{int(extract_time)}s")              
            self.progress_updated.emit(100)
            self.finished.emit(True,'处理完成')

        except Exception as e:
            self.finished.emit(False, f"发生错误: {str(e)}")

        finally:
            try:
                if os.path.exists(temp_download_dir):
                    shutil.rmtree(temp_download_dir, ignore_errors=True)
            except Exception as e:
                self.log_updated.emit(f"清理临时目录失败: {e}")
    
    def progress_hook(self, d):
        """下载进度回调函数"""
        if d['status'] == 'downloading':
            # self.log_updated.emit(str(d))
            try:

                downloaded_percent = int(d.get('_percent', '0'))
                if downloaded_percent in ['--', '']:
                    downloaded_percent = 0
                self.progress_updated.emit(downloaded_percent)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                filename = d.get('filename', '未知文件')
                filesize= d.get('total_bytes', 0)
                
                self.log_updated.emit(f"下载进度: {downloaded_percent}%, 大小: {int(filesize/1024)}K 速度: {int(speed/1024)}KB/s, 剩余时间: {eta}")
                self.log_updated.emit(f"正在下载: {os.path.basename(filename)}")
            except Exception as e:
                self.log_updated.emit(f"进度更新失败: {e}")            
            # 提取百分比数值更新进度条

            # print(f"[DEBUG] 报错 Progress: {downloaded_percent}%")
            # time.sleep(0.2)
                
        elif d['status'] == 'finished':
            self.progress_updated.emit(99)
            self.log_updated.emit("下载完成，开始合并文件...")

    # class MyLogger:
    #     def __init__(self, log_callback):
    #         self.log_callback = log_callback
        
    #     def debug(self, msg):
    #         if msg.startswith('[debug] '):
    #             self.info(msg)
    #         else:
    #             self.info(msg)
        
    #     def info(self, msg):
    #         self.log_callback(f"信息: {msg}")
        
    #     def warning(self, msg):
    #         self.log_callback(f"警告: {msg}")
        
    #     def error(self, msg):
    #         self.log_callback(f"错误: {msg}")


class DownloadThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, base_url, output_dir, temp_folder):
        super().__init__()
        self.base_url = base_url
        self.output_dir = output_dir
        self.temp_folder = temp_folder
        self.start_segment = 0
        self.end_segment = 2300
    
    def run(self):
        try:
            # 下载所有片段
            total_segments = self.end_segment - self.start_segment + 1
            for i in range(self.start_segment, self.end_segment + 1):
                segment_url = f"{self.base_url}segment{i}.ts?pubid=5348771529001"
                filename = os.path.join(self.temp_folder, f"segment{i}.ts")
                success = download_ts_file(segment_url, filename)
                if success:
                    self.log_updated.emit(f"下载完成: {filename}")
                else:
                    self.log_updated.emit(f"下载失败: {filename}")
                
                progress = int(((i - self.start_segment) / total_segments) * 100)
                self.progress_updated.emit(progress)
            
            # 合并文件
            output_file = os.path.join(self.output_dir, "combined.ts")
            with open(output_file, 'wb') as outfile:
                for i in range(self.start_segment, self.end_segment + 1):
                    filename = os.path.join(self.temp_folder, f"segment{i}.ts")
                    if os.path.exists(filename):
                        with open(filename, 'rb') as infile:
                            outfile.write(infile.read())
                        self.log_updated.emit(f"合并文件: {filename}")
            
            # 清理临时文件
            # shutil.rmtree(self.temp_folder)
            
            self.finished.emit(True, "下载和合并完成！")
        except Exception as e:
            self.finished.emit(False, f"发生错误: {str(e)}")

class AudioExtractTab(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        # 视频文件选择
        video_layout = QHBoxLayout()
        self.video_label = QLabel("视频文件:")
        self.video_input = QLineEdit()
        self.video_button = QPushButton("选择")
        self.video_button.clicked.connect(self.select_video_file)
        video_layout.addWidget(self.video_label)
        video_layout.addWidget(self.video_input)
        video_layout.addWidget(self.video_button)
        
        # 输出目录选择
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("输出目录:")
        self.dir_input = QLineEdit()
        self.dir_button = QPushButton("选择")
        self.dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_button)
        
        # 提取按钮
        self.extract_button = QPushButton("提取音频")
        self.extract_button.clicked.connect(self.start_extract)
        
        # 进度条
        self.progress_bar = QProgressBar()
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # 添加到主布局
        layout.addLayout(video_layout)
        layout.addLayout(dir_layout)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def select_video_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", "视频文件 (*.mp4 *.avi *.mkv)")
        if file_name:
            self.video_input.setText(file_name)
    
    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.dir_input.setText(directory)
    
    def start_extract(self):
        video_file = self.video_input.text()
        output_dir = self.dir_input.text()
        
        if not video_file or not output_dir:
            QMessageBox.warning(self, "错误", "请选择视频文件和输出目录")
            return
        
        # 构建输出文件路径
        audio_file_name = os.path.splitext(os.path.basename(video_file))[0] + ".mp3"
        audio_file_path = os.path.join(output_dir, audio_file_name)
        
        # 启动音频提取线程
        self.extract_thread = ExtractThread(video_file, audio_file_path)
        self.extract_thread.progress_updated.connect(self.update_progress)
        self.extract_thread.log_updated.connect(self.update_log)
        self.extract_thread.finished.connect(self.extract_finished)
        self.extract_thread.start()
        
        self.extract_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        self.log_output.append(message)
    
    def extract_finished(self, success, message):
        self.extract_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "错误", message)

class ExtractThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, video_file, audio_file):
        super().__init__()
        self.video_file = video_file
        self.audio_file = audio_file
    
    def run(self):
        try:
            # 提取音频
            self.log_updated.emit(f"开始提取音频 from {self.video_file}...")
            self.progress_updated.emit(10)            
            # 模拟进度
            # 调用实际的音频提取函数
            self.log_updated.emit("音频编码转换中...")
            self.progress_updated.emit(20)
            extract_time = extract_audio_from_video(self.video_file, self.audio_file)
            self.progress_updated.emit(60)
            self.log_updated.emit("写入音频文件...")
            self.finished.emit(True, f"音频已成功提取到 {self.audio_file}，耗时 {extract_time:.2f} 秒")
            self.progress_updated.emit(100)
            self.log_updated.emit(f"音频已成功提取到 {self.audio_file}，耗时 {extract_time:.2f} 秒")
        except Exception as e:
            self.finished.emit(False, f"音频提取失败: {str(e)}")

class TextTranslateTab(QWidget):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # 音频文件选择
        audio_layout = QHBoxLayout()
        self.audio_label = QLabel("音频文件:")
        self.audio_input = QLineEdit()
        self.audio_button = QPushButton("选择")
        self.audio_button.clicked.connect(self.select_audio_file)
        audio_layout.addWidget(self.audio_label)
        audio_layout.addWidget(self.audio_input)
        audio_layout.addWidget(self.audio_button)

        # 输出格式选择
        format_layout = QHBoxLayout()
        self.format_label = QLabel("输出格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItem("文本格式txt", "txt")
        self.format_combo.addItem("字幕格式SRT", "srt")
        self.format_combo.addItem("字幕格式VTT", "vtt")
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)

        # 任务类型选择
        task_layout = QHBoxLayout()
        self.task_label = QLabel("任务类型:")
        self.task_combo = QComboBox()
        self.task_combo.addItem("转录 (原文识别)", "transcribe")
        self.task_combo.addItem("翻译成中文/英文", "translate")
        self.task_combo.currentIndexChanged.connect(self.toggle_language_ui)
        task_layout.addWidget(self.task_label)
        task_layout.addWidget(self.task_combo)

        # 目标语言选择（默认隐藏）
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel("目标语言:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["保持源语言", "zh (中文)", "en (英文)"])
        self.lang_combo.setEnabled(False)  # 默认禁用
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo)

        # 翻译按钮
        self.translate_button = QPushButton("开始识别")
        self.translate_button.clicked.connect(self.start_translate)

        # 进度条
        self.progress_bar = QProgressBar()

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        # 添加到主布局
        layout.addLayout(audio_layout)
        layout.addLayout(format_layout)
        layout.addLayout(task_layout)
        layout.addLayout(lang_layout)
        layout.addWidget(self.translate_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        # 保存语言控件用于切换显示
        self.lang_layout = lang_layout
        self.lang_combo_items = {
            "保持源语言": None,
            "zh (中文)": "zh",
            "en (英文)": "en"
        }
    
    def select_audio_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "音频文件 (*.mp3 *.wav *.ogg)")
        if file_name:
            self.audio_input.setText(file_name)
    
    def toggle_language_ui(self):
        selected_task = self.task_combo.currentData()
        if selected_task == "translate":
            self.lang_combo.setEnabled(True)
        else:
            self.lang_combo.setEnabled(False)
    def start_translate(self):
        audio_file = self.audio_input.text()
        output_format = self.format_combo.currentData()
        task = self.task_combo.currentData()
        language = self.lang_combo_items.get(self.lang_combo.currentText())
        if not audio_file:
            self.log_updated.emit("错误,请选择音频文件")    
            QMessageBox.warning(self, "错误", "请选择音频文件")
            return
        
        # 启动翻译线程
        self.translate_thread = TranslateThread(audio_file, output_format, task, language)
        self.translate_thread.progress_updated.connect(self.update_progress)
        self.translate_thread.log_updated.connect(self.update_log)
        self.translate_thread.finished.connect(self.translate_finished)
        self.translate_thread.start()
        self.log_updated.emit(f"将转换格式为{output_format}")
        
        self.translate_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        self.log_output.append(message)
    
    def translate_finished(self, success, message):
        self.translate_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "错误", message)

class TranslateThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, audio_file, output_format, task="transcribe", language=None):
        super().__init__()
        self.audio_file = audio_file
        self.output_format = output_format
        self.task = task
        self.language = language  # 可为 None

    def run(self):
        try:
            self.log_updated.emit(f"开始{('翻译' if self.task == 'translate' else '转录')}，目标格式: {self.output_format}")
            self.progress_updated.emit(5)

            self.log_updated.emit("连接ASR服务...")
            self.progress_updated.emit(10)
            self.log_updated.emit("上传音频文件...")
            self.progress_updated.emit(30)

            # 构建参数
            params = {
                "task": self.task,  # transcribe / translate
                "output": self.output_format
            }
            if self.task == "translate" and self.language:
                params["language"] = self.language

            # 实际调用 ASR 函数
            self.log_updated.emit("语音识别中...")
            self.progress_updated.emit(40)

            srt_content, recognize_time = recognize_audio(self.audio_file, self.output_format, params=params)

            self.progress_updated.emit(50)

            output_dir = os.path.dirname(self.audio_file)
            if self.task == "translate" and self.language:
                #翻译 加个目标语言
                txt_file_path = os.path.join(output_dir,
                                            os.path.splitext(os.path.basename(self.audio_file))[0] +
                                            f"_{self.language}.{self.output_format}")
            else:
                txt_file_path = os.path.join(output_dir,os.path.splitext(os.path.basename(self.audio_file))[0] +
                                            f".{self.output_format}")
            if isinstance(srt_content, dict) and "error" in srt_content:
                self.finished.emit(False, f"错误处理 {self.audio_file}: {srt_content['error']}")
            else:
                with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                    txt_file.write(srt_content)
                self.log_updated.emit(f"音频识别完成，结果已保存到 {txt_file_path}，耗时 {recognize_time:.2f} 秒")
                self.progress_updated.emit(100)
                self.finished.emit(True, f"识别完成，结果已保存到 {txt_file_path}")
        except Exception as e:
            self.finished.emit(False, f"音频识别失败: {str(e)}")

class SummaryTab(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        # 文本文件选择
        txt_layout = QHBoxLayout()
        self.txt_label = QLabel("文本文件:")
        self.txt_input = QLineEdit()
        self.txt_button = QPushButton("选择")
        self.txt_button.clicked.connect(self.select_txt_file)
        txt_layout.addWidget(self.txt_label)
        txt_layout.addWidget(self.txt_input)
        txt_layout.addWidget(self.txt_button)
        
        # 摘要类型选择
        type_layout = QHBoxLayout()
        self.type_label = QLabel("摘要类型:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["简洁摘要", "详细摘要", "结构化分析报告"])
        type_layout.addWidget(self.type_label)
        type_layout.addWidget(self.type_combo)
        
        # 摘要按钮
        self.summary_button = QPushButton("生成摘要")
        self.summary_button.clicked.connect(self.start_summary)
        
        # 进度条
        self.progress_bar = QProgressBar()
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        # 添加到主布局
        layout.addLayout(txt_layout)
        layout.addLayout(type_layout)
        layout.addWidget(self.summary_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)
        
        self.setLayout(layout)
    
    def select_txt_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择文本文件", "", "文本文件 (*.txt)")
        if file_name:
            self.txt_input.setText(file_name)
    
    def start_summary(self):
        txt_file = self.txt_input.text()
        summary_type = self.type_combo.currentText()
        
        if not txt_file:
            QMessageBox.warning(self, "错误", "请选择文本文件")
            return
        
        # 启动摘要线程
        self.summary_thread = SummaryThread(txt_file, summary_type)
        self.summary_thread.progress_updated.connect(self.update_progress)
        self.summary_thread.log_updated.connect(self.update_log)
        self.summary_thread.finished.connect(self.summary_finished)
        self.summary_thread.start()
        
        self.summary_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        self.log_output.append(message)
    
    def summary_finished(self, success, message):
        self.summary_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "错误", message)

class SummaryThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, txt_file, summary_type):
        super().__init__()
        self.txt_file = txt_file
        self.summary_type = summary_type
    
    def run(self):
        try:
            # 读取TXT文件内容
            self.log_updated.emit(f"读取文本文件 {self.txt_file}...")
            
            with open(self.txt_file, "r", encoding="utf-8") as file:
                content = file.read()
            
            # 构造摘要提示词
            if self.summary_type == "简洁摘要":
                prompt = "请对以下文本进行摘要总结，输出简洁的中文摘要：\n\"\""
            elif self.summary_type == "详细摘要":
                prompt = "请对以下文本进行摘要总结，输出详细的中文摘要，并梳理主要观点：\n\"\""
            else:  # 结构化分析报告
                prompt = """请对以下文本进行摘要总结，输出结构化的分析报告：
                - 输出使用markdown格式
                - 包含主要事件、时间、地点、人物、原因等要素
                - 对信息的真实性和可靠性进行评估
                - 分析信息的潜在影响
                
                \n\"\""""
            
            self.log_updated.emit(f"生成{self.summary_type}...")
            self.progress_updated.emit(10)
            self.log_updated.emit("构造摘要提示...")

            summary = call_llm_api(prompt, content)
            
            self.log_updated.emit("调用LLM模型...")
            self.progress_updated.emit(20)
            
            # 保存摘要结果
            output_dir = os.path.dirname(self.txt_file)
            summary_file_path = os.path.join(output_dir, 
                                    f"摘要_{self.summary_type}_{os.path.splitext(os.path.basename(self.txt_file))[0]}_{int(time.time())}.txt")
            
            with open(summary_file_path, "w", encoding="utf-8") as summary_file:
                summary_file.write(summary)
            
            self.log_updated.emit("处理模型输出...")
            self.progress_updated.emit(90)
            self.finished.emit(True, f"摘要完成，结果已保存到 {summary_file_path}")
            self.log_updated.emit(f"摘要完成，结果已保存到 {summary_file_path}")
            self.progress_updated.emit(100)
        except Exception as e:
            self.finished.emit(False, f"摘要生成失败: {str(e)}")

class SubtitleTranslateTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # 字幕文件选择
        srt_layout = QHBoxLayout()
        self.srt_label = QLabel("SRT 字幕文件:")
        self.srt_input = QLineEdit()
        self.srt_button = QPushButton("选择")
        self.srt_button.clicked.connect(self.select_srt_file)
        srt_layout.addWidget(self.srt_label)
        srt_layout.addWidget(self.srt_input)
        srt_layout.addWidget(self.srt_button)

        # 输出目录选择
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("输出目录:")
        self.dir_input = QLineEdit()
        self.dir_button = QPushButton("选择")
        self.dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_button)

        # 在初始化界面中增加源语言选择
        source_lang_layout = QHBoxLayout()
        self.source_lang_label = QLabel("源语言:")
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["英文", "西班牙语", "法语", "中文","日语","韩语","德语"])  # 可扩展
        source_lang_layout.addWidget(self.source_lang_label)
        source_lang_layout.addWidget(self.source_lang_combo)
        layout.addLayout(source_lang_layout)
        self.target_lang_label = QLabel("目标语言:")

        # 目标语言选择
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel("目标语言:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文", "英文"])
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo)

        # 翻译按钮
        self.translate_button = QPushButton("开始翻译")
        self.translate_button.clicked.connect(self.start_translate)

        # 进度条
        self.progress_bar = QProgressBar()

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        # 添加到主布局
        layout.addLayout(srt_layout)
        layout.addLayout(dir_layout)
        layout.addLayout(lang_layout)
        layout.addWidget(self.translate_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def select_srt_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "选择 SRT 文件", "", "SRT 文件 (*.srt)")
        if file_name:
            self.srt_input.setText(file_name)

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.dir_input.setText(directory)

    def start_translate(self):
        srt_file = self.srt_input.text()
        output_dir = self.dir_input.text()
        source_lang = self.source_lang_combo.currentText()
        target_lang = self.lang_combo.currentText()

        if not srt_file or not output_dir:
            QMessageBox.warning(self, "错误", "请选择 SRT 文件和输出目录")
            return

        # 启动翻译线程
        self.translate_thread = SubtitleTranslateThread(srt_file, output_dir, source_lang, target_lang)
        self.translate_thread.progress_updated.connect(self.update_progress)
        self.translate_thread.log_updated.connect(self.update_log)
        self.translate_thread.finished.connect(self.translate_finished)
        self.translate_thread.start()

        self.translate_button.setEnabled(False)
        self.progress_bar.setValue(0)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_log(self, message):
        self.log_output.append(message)

    def translate_finished(self, success, message):
        self.translate_button.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "错误", message)


class SubtitleTranslateThread(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, srt_file, output_dir, source_language="西班牙语", target_language="中文"):
        super().__init__()
        self.srt_file = srt_file
        self.output_dir = output_dir
        self.target_language = target_language  # "中文" 或 "英文"
        self.source_language = source_language
        self.SUPPORTED_LANGUAGES = {
            "中文": "zh",
            "英文": "en",
            "西班牙语": "es",
            "法语": "fr",
            "德语": "de",
            "日语": "ja",
            "韩语": "ko"
        }


    def build_prompt_template(self, source_lang, target_lang):
        """
        动态构建适用于不同语言对的翻译提示词
        :param source_lang: 源语言名称（中文、英文、西班牙语等）
        :param target_lang: 目标语言名称
        :return: 提示词字符串
        """
        if source_lang == target_lang:
            raise ValueError("源语言与目标语言相同，无需翻译")

        examples = {
            ("西班牙语", "中文"): [
                ("1. Hola", "1. 你好"),
                ("2. ¿Cómo estás?", "2. 你好吗？")
            ],
            ("西班牙语", "英文"): [
                ("1. Hola", "1. Hello"),
                ("2. ¿Cómo estás?", "2. How are you?")
            ],
            ("法语", "中文"): [
                ("1. Bonjour", "1. 你好"),
                ("2. Comment ça va ?", "2. 你最近怎么样？")
            ],
            ("法语", "英文"): [
                ("1. Bonjour", "1. Hello"),
                ("2. Comment ça va ?", "2. How are you?")
            ],
            ("英文", "中文"): [
                ("1. Hello", "1. 你好"),
                ("2. How are you?", "2. 你好吗？")
            ],
             # 英文 -> 中文
            ("英文", "中文"): [
                    ("1. Hello", "1. 你好"),
                    ("2. How are you?", "2. 你好吗？")
            ],
                
            # 英文 -> 日语
            ("日语", "英文"): [
                ("1. こんにちは","1. Hello"  ),
                ( "2. お元気ですか？","2. How are you?")
            ],
            # 英文 -> 韩语
            ( "韩语","英文"): [
                ("1. 안녕하세요","1. Hello"),
                ("2. 어떻게 지내세요?","2. How are you?" )
            ],
                
            # 英文 -> 德语
            ( "德语","英文"): [
                ( "1. Hallo","1. Hello",),
                ("2. Wie geht es dir?","2. How are you?")
            ],
            # 中文 -> 日语
            ( "日语","中文"): [
                ("1. こんにちは","1. 你好", ),
                ("2. 最近どうですか？","2. 你最近怎么样？")
            ],
            
            # 中文 -> 韩语
            ( "韩语","中文"): [
                ("1. 안녕하세요","1. 你好", ),
                ("2. 요즘 어떻게 지내세요?","2. 你最近怎么样？" )
            ],
        
            # 中文 -> 德语
            ("德语","中文"): [
                ("1. Hallo","1. 你好"),
                ("2. Wie geht es dir?","2. 你最近怎么样？" )
            ]
        }

        example_pair = examples.get((source_lang, target_lang))
        if not example_pair:
            raise ValueError(f"暂不支持 {source_lang} 到 {target_lang} 的翻译模板")

        example_str = "\n".join([f"{src}\n{tgt}" for src, tgt in example_pair])

        prompt_map = {
            "中文": "中文",
            "英文": "English",
            "西班牙语": "Spanish",
            "法语": "French",
            "德语": "German",
            "日语": "Japanese",
            "韩语": "Korean"
        }

        source_prompt = prompt_map.get(source_lang, source_lang)
        target_prompt = prompt_map.get(target_lang, target_lang)

        return (
            f"You are a professional subtitle translator. Please accurately and naturally translate the following {source_prompt} sentences into {target_prompt}.\n"
            f"Each sentence is prefixed with a number. Provide translations in the same order without adding any explanation or formatting.\n"
            f"Keep the translation concise and suitable for video playback.\n"
            f"For example:\n"
            f"{example_str}\n"
            "-->\n"
        )
    def run(self):
        try:
            self.log_updated.emit(f"开始翻译字幕文件: {self.srt_file}，目标语言: {self.target_language}")
            self.progress_updated.emit(10)

            import importlib.util
            spec = importlib.util.spec_from_file_location("translate_srt_batch", "translate_srt_batch.py")
            translate_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(translate_module)

            self.progress_updated.emit(30)

            input_srt = self.srt_file
            # 假设你已经获取了源语言 source_lang 和目标语言 target_lang

            source_lang_code = self.SUPPORTED_LANGUAGES.get(self.source_language, "未知语言")
            target_lang_code = self.SUPPORTED_LANGUAGES.get(self.target_language, "未知语言")

            base_name = os.path.splitext(os.path.basename(input_srt))[0]
            output_srt = os.path.join(self.output_dir, f"{base_name}_{target_lang_code}.srt")
            temp_file = os.path.join(self.output_dir, f"{base_name}_temp_progress.srt")

            if source_lang_code == "未知语言" or target_lang_code == "未知语言":
                raise ValueError("不支持的语言选择")

            # 构建提示词模板
            prompt_template = self.build_prompt_template(self.source_language, self.target_language)

            self.log_updated.emit("解析 SRT 文件...")
            entries = translate_module.parse_srt(input_srt)
            self.progress_updated.emit(40)

            self.log_updated.emit("分批次翻译字幕...")
            translate_module.translate_in_batches(entries, prompt_template, temp_file, batch_size=30)
            self.progress_updated.emit(80)

            self.log_updated.emit("合并临时文件...")
            translate_module.merge_temp_to_final(temp_file, output_srt, entries)

            self.log_updated.emit(f"翻译完成，结果已保存至: {output_srt}")
            self.progress_updated.emit(100)
            self.finished.emit(True, f"字幕翻译已完成，结果已保存至: {output_srt}")

        except Exception as e:
            self.finished.emit(False, f"字幕翻译失败: {str(e)}")

if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())