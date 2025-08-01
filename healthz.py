from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", "3000")))
