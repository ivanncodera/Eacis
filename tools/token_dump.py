import tokenize, io
p='eacis/services/otp_service.py'
with open(p,'rb') as f:
    b=f.read()

for tok in tokenize.tokenize(io.BytesIO(b).readline):
    if tok.start[0] >= 288 and tok.start[0] <= 312:
        print(tok)
