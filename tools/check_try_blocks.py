#!/usr/bin/env python3
import sys
s=open('eacis/app.py','r',encoding='utf-8').read().splitlines()
stack=[]
problems=[]
for i,line in enumerate(s, start=1):
    stripped=line.lstrip(" \t")
    indent=len(line)-len(stripped)
    if stripped.startswith('try:'):
        stack.append((i,indent))
    elif stripped.startswith('except') or stripped.startswith('finally'):
        # try to match same-indent try
        if stack and stack[-1][1]==indent:
            stack.pop()
        else:
            found=False
            for j in range(len(stack)-1,-1,-1):
                if stack[j][1]==indent:
                    stack.pop(j)
                    found=True
                    break
            if not found:
                problems.append((i, 'unexpected except/finally', indent))

if problems:
    print('Unexpected except/finally blocks:')
    for p in problems:
        print(p)
if stack:
    print('Unmatched try blocks remain:')
    for ln,ind in stack:
        print('try at line', ln, 'indent', ind)
if not problems and not stack:
    print('No unpaired try/except/finally blocks found')
