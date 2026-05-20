from schemas.migrationsetting import MigrationSetting
from schemas.requestdata import RequestData
from utils.handlermanagement import HandlerManagement
from utils.validations import Validations
import os
import time
import sys
from utils.processing import Processing
from utils.logger import Logger
from utils.regtimeproc import Regtimeproc
import json
import pandas as pd
import subprocess  # Agregado para ejecutar scripts externos

logger = Logger().get_logger()

def main():
    logger.info('Start M2M load')
    
    # Ejecutar ProcessCSV.py
    logger.info('Executing ProcessCSV.py...')
    subprocess.run(['python', 'ProcessCSV.py'], check=True)  # Llama al script ProcessCSV.py
    
    with open('config.json') as f:
        data = json.load(f)
    migrationsetting = MigrationSetting(**data)
    print(migrationsetting)
    
    handler = HandlerManagement(
        migrationsetting=migrationsetting,
        sfenvironment=migrationsetting.sfenvironment
    )
    
    billingfile = f"data/{migrationsetting.sfenvironment}Billing_Account_M2M.csv"
    suborderfile = handler.serviceaccounts(entity='order_item', billingfile=billingfile)

    suborderfile = f'log/res_suborders.csv'
    mito = handler.generateMitoresponseall(suborderfile=suborderfile)
    print('Execute mito final report')
    time.sleep(1)
    executeFile = handler.generateresponsereportprocess()

    # Ejecutar PrepRetry.py como último paso
    logger.info('Executing PrepRetry.py...')
    try:
        subprocess.run([sys.executable, 'PrepRetry.py'], check=True)
        logger.info('PrepRetry.py executed successfully.')
    except subprocess.CalledProcessError as e:
        logger.error(f'Error executing PrepRetry.py: {str(e)}')

    logger.info('This is the end ()()()')

if __name__ == '__main__':
    main()