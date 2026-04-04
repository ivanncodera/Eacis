import os
from eacis.app import create_app
port = int(os.environ.get('PORT','5001'))
app = create_app()
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=port)
