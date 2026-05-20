from simple_salesforce import Salesforce
import os
import pandas as pd
from dotenv import load_dotenv
from utils.logger import Logger

load_dotenv('.env.local')

logger = Logger().get_logger()


class SalesforceManagement(object):
    """Salesforce Management for Bulk and Apex operations."""

    def __init__(self, environment: str) -> None:
        logger.info(f'Start | Login salesforce environment: | {environment}')
        username       = os.environ.get('SF_USERNAME', '')
        password       = os.environ.get('SF_PASSWORD', '')
        security_token = os.environ.get('SF_SECURITY_TOKEN', '')
        domain         = os.environ.get('SF_DOMAIN', 'login')
        try:
            self.sf = Salesforce(
                username=username,
                password=password,
                security_token=security_token,
                domain=domain
            )
            logger.info(f'Login to Salesforce OK | environment: {environment}')
        except Exception as e:
            logger.exception(f'Fail | Login with salesforce - {environment} | {str(e)} |')

    def upsertBulk(self,object_name, parsedata,external_id,batch_size,use_serial):
        """Invoke Update/Insert operation with Bulk API Salesforce

        Args:
            object_name (_type_): Salesforce Object Name
            parsedata (_type_): data in json formater
            external_id (_type_): External Id in Salesforce Object
            batch_size (_type_): Batch size to proccessing
            use_serial (_type_): False in Parallel or True in Serial

        Returns:
            _type_: Dataframe with Salesforce Response that contain Id
        """
        result = self.sf.bulk.__getattr__(name = object_name).upsert(data = parsedata, external_id_field = external_id, batch_size = batch_size, use_serial = use_serial)
        dfresult = pd.DataFrame(result)
        return dfresult
    def insertBulk(self,object_name, parsedata,batch_size,use_serial):
        result = self.sf.bulk.__getattr__(name = object_name).insert(data = parsedata, batch_size = batch_size, use_serial = use_serial)
        dfresult = pd.DataFrame(result)
        return dfresult
    def queryBulk(self, object_name, soql):
        result = pd.DataFrame(self.sf.bulk.__getattr__(name = object_name).query(soql))
        return result
    def deleteBulk(self, object_name : str,parsedata,batch_size):
        self.sf.bulk.__getattr__(name = object_name).delete(data = parsedata, batch_size = batch_size)
    def invokeApex(self,payload, endpoint):
        result = self.sf.apexecute(endpoint, method='POST',data=payload)
        return result