from main import setup_db, app as application

setup_db()

if __name__ == "__main__":
    application.run(port=8080)
