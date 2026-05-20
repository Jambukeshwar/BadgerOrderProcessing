import logging
import sys

class Logger:
    # Configurar controladores de registro una vez
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s | %(message)s',datefmt='%Y-%m-%d %H:%M:%S',)
    
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)
    
    file_handler = logging.FileHandler('log/trackFile_log.txt')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
    def get_logger(self):
        return self.logger