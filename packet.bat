D:\venv\qttools\Scripts\python.exe -m PyInstaller �۷���Ƶ��������.spec --noconfirm  --clean
:: ɾ���ɵ�Ŀ���ļ��У���ѡ��
if exist dist\�۷���Ƶ��������\cookies\ (
    rmdir /s /q dist\�۷���Ƶ��������\cookies\
)
:: ����Ŀ���ļ��У���ѡ��
mkdir dist\�۷���Ƶ��������\cookies\

copy dist\�۷���Ƶ��������\_internal\cookies\ dist\�۷���Ƶ��������\cookies\

:: ͬ���� config.ini
copy /Y dist\�۷���Ƶ��������\_internal\config.ini dist\�۷���Ƶ��������\
