from uvicorn import run

if __name__ == '__main__':
    run('app.api.routes:app', host='127.0.0.1', port=8300)
