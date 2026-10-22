from flask import Flask
app = Flask(__name__)

@app.get('/')
def index():
    return 'ReelFlow server online'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
