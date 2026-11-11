import sys
print('EXE:', sys.executable)
print('PWD:', __import__('os').getcwd())
try:
    import app
    print('IMPORT_OK')
except Exception as exc:
    import traceback
    traceback.print_exc()
    sys.exit(1)
