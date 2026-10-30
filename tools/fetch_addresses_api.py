#!/usr/bin/env python
"""Fetch the customer addresses API endpoint from local dev server."""
import urllib.request, urllib.error, json

def main():
    url = 'http://127.0.0.1:5000/customer/addresses/api'
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read().decode('utf-8')
            print('status', resp.status)
            try:
                print(json.loads(data))
            except Exception:
                print(data[:200])
    except urllib.error.HTTPError as he:
        print('HTTPError', he.code)
        try:
            print(he.read().decode('utf-8')[:1000])
        except Exception:
            pass
    except Exception as e:
        print('Request failed:', e)

if __name__ == '__main__':
    main()
