import sys
p='eacis/app.py'
start=int(sys.argv[1]) if len(sys.argv)>1 else 1
end=int(sys.argv[2]) if len(sys.argv)>2 else start
with open(p,'rb') as f:
    data=f.read()
# decode with utf-8, replace errors
s=data.decode('utf-8',errors='replace').splitlines()
for i in range(start-1,min(end,len(s))):
    line=s[i]
    # show visible whitespace
    vis=line.replace('\t','<TAB>').replace(' ','·')
    print(f"{i+1:5d}: {vis!s}")
    # also show repr for debugging
    print('    repr:',repr(line))
