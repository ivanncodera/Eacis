import os
p = os.path.join('eacis','static','assets','products')
if os.path.isdir(p):
    files = sorted([f for f in os.listdir(p) if os.path.isfile(os.path.join(p,f))])
    for f in files:
        print(f)
else:
    print('assets dir missing:', p)
