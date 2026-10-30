import sys
p = 'eacis/app.py'
start = 3200
end = 3340
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(start-1, min(end, len(lines))):
    line = lines[i].rstrip('\n')
    leading = len(line) - len(line.lstrip(' '))
    print(f"{i+1:5d} {leading:3d} |{line}")
