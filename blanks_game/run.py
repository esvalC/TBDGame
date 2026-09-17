"""Start the dev server.

    python run.py            -> http://localhost:5000
    python run.py --lan      -> also reachable from phones on your Wi-Fi
"""
import sys

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    app.run(host=host, port=5050, debug="--debug" in sys.argv)
