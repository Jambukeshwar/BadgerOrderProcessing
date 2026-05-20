from simple_salesforce import Salesforce
import json
import os
import subprocess
import pandas as pd
from dotenv import load_dotenv
from utils.logger import Logger

load_dotenv('.env.local')

logger = Logger().get_logger()


def _sf_via_cli(org_alias: str) -> Salesforce:
    """Get a Salesforce session using the SF CLI — no username/password needed."""
    cmd = f'sf org display --target-org {org_alias} --json'
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f'SF CLI failed: {result.stderr.strip()}')
    data = json.loads(result.stdout)
    r = data.get('result', {})
    access_token = r.get('accessToken')
    instance_url = r.get('instanceUrl')
    if not access_token:
        raise RuntimeError('SF CLI returned no accessToken — run: sf org login web --alias sf-prod')
    return Salesforce(instance_url=instance_url, session_id=access_token)


class SalesforceManagement(object):
    """Salesforce Management for Bulk and Apex operations using SF CLI auth."""

    def __init__(self, environment: str) -> None:
        logger.info(f'Start | Login salesforce environment: | {environment}')
        org_alias = os.environ.get('SF_ORG_ALIAS', 'cwc-prod')
        try:
            self.sf = _sf_via_cli(org_alias)
            logger.info(f'Login to Salesforce OK (SF CLI) | environment: {environment}')
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