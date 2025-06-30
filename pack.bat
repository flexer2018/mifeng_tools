@echo off
set PYTHONPATH=D:\venv\qttools\Scripts\python.exe

nuitka ^
    --standalone ^
    --enable-plugin=pyqt5 ^
    --windows-icon-from-ico=runke128.ico ^
    --include-data-file="ffmpeg=ffmpeg" ^
    --include-data-file="cookies=cookies" ^
    --include-data-file="config.ini=." ^
    --output-dir=dist ^
    main_window.py