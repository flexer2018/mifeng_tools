D:\venv\qttools\Scripts\python.exe -m PyInstaller 蜜蜂视频处理工具箱.spec --noconfirm  --clean
:: 删除旧的目标文件夹（可选）
if exist dist\蜜蜂视频处理工具箱\cookies\ (
    rmdir /s /q dist\蜜蜂视频处理工具箱\cookies\
)
:: 创建目标文件夹（可选）
mkdir dist\蜜蜂视频处理工具箱\cookies\

copy dist\蜜蜂视频处理工具箱\_internal\cookies\ dist\蜜蜂视频处理工具箱\cookies\

:: 同理复制 config.ini
copy /Y dist\蜜蜂视频处理工具箱\_internal\config.ini dist\蜜蜂视频处理工具箱\
