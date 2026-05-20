import json
import pandas as pd
from utils.sfmanagement import SalesforceManagement
from schemas.requestdata import RequestData
#import logging
from datetime import datetime
#import paramiko
import os
from utils.logger import Logger
#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

logger = Logger().get_logger()

class DataManagement(object):
    def __init__(self) -> None:
        pass

    def generateCsvtoFtp(self, requestdata : RequestData):
        # 1 - Create Query 

        fields = requestdata.setting.query.fields
        objectname = requestdata.setting.query.object
        conditions = requestdata.setting.query.conditions
        soql = f'SELECT {fields} FROM {objectname} WHERE {conditions} LIMIT 100'
        # 2 - Query Salesforce
        sf = SalesforceManagement(environment = requestdata.environment.name)
        dfdata = self.sf.queryBulk(object_name = objectname, soql = soql)
        if len(dfdata) > 0: 
            dfdata = dfdata.drop(columns=['attributes'])
            #Mappings 
            dfdata = dfdata.rename(columns = requestdata.setting.mappings)
            columns_to_keep = list(requestdata.setting.mappings.values())
            dfdata = dfdata[columns_to_keep]
            current_date = datetime.now()
            file_name = f'sample_{current_date.strftime("%Y%m%d")}.csv'
            local_path = f'data/{file_name}'
            remote_path = f'{requestdata.setting.ftpSetup.remoteFolder}{file_name}'
            dfdata.to_csv(local_path, index = False)
            del dfdata
            # Create an SFTP client object
            #ssh_client = paramiko.SSHClient()
            #ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy)

            #ssh_client.load_system_host_keys()
            #ssh_client.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())

            #response = {'Post - Generate Csv FTP': 'Completed'}
            #try:

            #    ssh_client.connect (hostname = requestdata.setting.ftpSetup.serverName,
             #                       port     = int(requestdata.setting.ftpSetup.port), 
             #                       username = requestdata.setting.ftpSetup.userName, 
             #                       password = requestdata.setting.ftpSetup.password)
             #   sftp = ssh_client.open_sftp() 
                # Upload the local file to the remote server
                
             #   sftp.put(localpath=local_path, remotepath=remote_path)
             #   os.remove(local_path)

            #except paramiko.AuthenticationException:
            #    response = {'SFTP - Authentication Error': 'Error'}

            #except paramiko.SSHException as ssh_err:
            #    response = {'SSH - Connection Error': 'Error'}

            #finally:
            #    try:
                    # Cerrar la conexión SFTP
             #       sftp.close()
             #   except NameError:
             #       pass

                # Cerrar la conexión SSH
             #   ssh_client.close()

