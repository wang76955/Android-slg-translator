import zipfile, os

base = r'C:\Users\王运\Documents\文件翻译\apk-work\com.slgtranslator.app-base.apk'
unsigned = r'C:\Users\王运\Documents\文件翻译\apk-work\slg-fixed4-unsigned.apk'
patched_dex = r'C:\Users\王运\Documents\文件翻译\apk-work\extracted\classes6.dex'
patched_js = r'C:\Users\王运\Documents\文件翻译\apk-work\extracted\assets\public\assets\index-CJtfdHOF.js'

with open(patched_dex, 'rb') as f:
    new_dex = f.read()
with open(patched_js, 'rb') as f:
    new_js = f.read()

# First, check what compression base APK uses for resources.arsc
with zipfile.ZipFile(base, 'r') as zin:
    for item in zin.infolist():
        if item.filename == 'resources.arsc':
            print('Base resources.arsc compress_type: ' + str(item.compress_type))

# Build new zip - store uncompressed any file that was stored uncompressed in original
with zipfile.ZipFile(base, 'r') as zin:
    with zipfile.ZipFile(unsigned, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            
            # Determine compression
            needs_store = False
            if item.filename == 'resources.arsc':
                needs_store = True  # Must be uncompressed for Android R+
            
            if item.filename == 'classes6.dex':
                data = new_dex
                needs_store = True  # DEX should be stored
                print('Replaced: classes6.dex (' + str(len(new_dex)) + ' bytes)')
            elif item.filename == 'assets/public/assets/index-CJtfdHOF.js':
                data = new_js
                print('Replaced: ' + item.filename + ' (' + str(len(new_js)) + ' bytes)')
            
            new_info = zipfile.ZipInfo(item.filename, date_time=(2026, 6, 9, 12, 0, 0))
            new_info.compress_type = zipfile.ZIP_STORED if needs_store else zipfile.ZIP_DEFLATED
            new_info.external_attr = item.external_attr
            zout.writestr(new_info, data)

print('Done')
