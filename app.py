import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)

from kvitkova_crm import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5055) 