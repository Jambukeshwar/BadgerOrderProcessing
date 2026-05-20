import pandas as pd
import numpy as np
import logging
import time
import re
from utils.logger import Logger
#logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s',
#                    datefmt='%Y-%m-%d %H:%M:%S',
#                    level=logging.INFO)
#logger = logging.getLogger(__name__)
logger = Logger().get_logger()

class RulesManagement(object):
    def __init__(self) -> None:
        pass
    def applyrules(self,entity, dfsource,mappings, businessfile, billingfile, individualfile, dfdatausepurpose, subordersfile):
        if entity == 'business':
            return self.businessrules(dfsource = dfsource, mappings = mappings)
        elif entity == 'billing':
            dfbusiness = pd.read_csv(businessfile)
            dfsource = self.billingrules(dfsource = dfsource,
                                          dfbusiness = dfbusiness,
                                          mappings = mappings)
            return dfsource
        elif entity == 'service':
            dfbusiness = pd.read_csv(businessfile)
            dfsource = self.servicerules(dfsource = dfsource,
                                          dfbusiness = dfbusiness,
                                          mappings = mappings)
            return dfsource
        elif entity == 'paymentmethod':
            dfbilling = pd.read_csv(billingfile)
            dfsource = self.paymentmethodrules(dfsource = dfsource,
                                          dfbilling = dfbilling,
                                          mappings = mappings)
            return dfsource
        elif entity == 'contact':
            dfbusiness = pd.read_csv(businessfile)
            dfindividual = pd.read_csv(individualfile)
            return self.contactrules(dfsource = dfsource,
                                     mappings = mappings,
                                     dfbusiness = dfbusiness,
                                     dfindividual = dfindividual
                                    )
        elif entity == 'individual':
            return self.individualrules(dfsource = dfsource, mappings = mappings)
        elif entity == 'consent':
            dfindividual = pd.read_csv(individualfile)

            return self.consentrules(dfsource   = dfsource,
                                     dfinvidual = dfindividual,
                                     dfdatausepurpose = dfdatausepurpose,
                                     mappings = mappings)
        elif entity == 'contract':
            dfsuborders = pd.read_csv(subordersfile)
            dfsource = self.contractrules(dfsource = dfsource,
                                          dfsuborders = dfsuborders,
                                          mappings = mappings)
            return dfsource
    def businessrules(self,dfsource, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Business Rules | {str(len(dfsource))} |')
        try:
            # 1 - Clean dfcontact
            # Mapping Copy Country Account for S3 files
            dfsource['bp_country__c'] = dfsource['countryaccount__c']
            dfsource['pr_ssn__c'] = dfsource['pr_ssn__c'].astype(str)
            dfsource['billingpostalcode'] = dfsource['billingpostalcode'].astype(str)
            dfsource['shippingpostalcode'] = dfsource['shippingpostalcode'].astype(str)
            dfsource['FAN_Number__c'] = dfsource['cust_prnt_id']
            #dfsource['cust_prnt_id'] = dfsource['cust_prnt_id'].astype(str)
            #1.1 asign account ownwer
            dfowners = pd.read_csv ('log/data/OwnerId.csv')
            dfsource = pd.merge (dfsource,dfowners,left_on='cust_prnt_id',right_on='cust_prnt_id',how='left')
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            
            # Asigna el ID de Luisa Lara a todas las cuentas que no tengan un owner asignado
            dfsource['IdOwner'] = dfsource['IdOwner'].replace('', np.nan)  #replace empty values for None
            dfsource['IdOwner'] = dfsource['IdOwner'].fillna('0054X00000EWM8RQAX') #replace None for default value
            
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Business Rules | {str(e)} | ')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Business Rules| {str(len(dfsource))} | {elapsed}')
        return dfsource
    def billingrules(self,dfsource, dfbusiness, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Billing Rules | {str(len(dfsource))} | ')
        try:
            dfbusiness = dfbusiness.loc[dfbusiness['Success']== True] #jfrc
            dfsource = pd.merge(dfsource, dfbusiness, left_on='parentid', right_on='cust_prnt_id', how='inner')
            dfsource['billingpostalcode'] = dfsource['billingpostalcode'].astype(str)
            dfsource['shippingpostalcode'] = dfsource['shippingpostalcode'].astype(str)
            # 1 - Clean dfcontact
            dfsource = dfsource.drop(['parentid','billing_entity__c','RecordTypeId'], axis=1)
            dfsource['prcustomernumber'] = dfsource['pr_customer_number__c']
            dfsource['vlocity_cmt__RootAccountId__c'] = dfsource['Id']
            dfsource['name'] = dfsource['name'] + '-' + 'Billing'
            dfsource['ssp_autopayenable__c'] = dfsource['ssp_autopayenable__c'].replace({True: 'true', False: 'false'})
            # Mapping Copy Country Account for S3 files
            dfsource['countryaccount__c'] = dfsource['bp_country__c']
            dfsource['FAN_Number__c'] = dfsource['cust_prnt_id']
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            dfsource = dfsource.drop(['cust_prnt_id'], axis=1)

            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Billing Rules | {str(e)} |')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Billing Rules| {str(len(dfsource))} | {elapsed}')
        return dfsource
    def servicerules(self,dfsource, dfbusiness, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Service Rules | {str(len(dfsource))} |')
        dfbusiness = dfbusiness.loc[dfbusiness['Success']== True] #jfrc
        dfsource = pd.merge(dfsource, dfbusiness, left_on='parentid', right_on='Oracle_CRM_External_ID__c', how='left')
        # 1 - Clean dfcontact
        dfsource = dfsource.drop(['parentid'], axis=1)
        dfsource['vlocity_cmt__RootAccountId__c'] = dfsource['id']
        dfsource['name'] = dfsource['name'] + ' - ' + 'Service'
        # 2 - Mapping fixed columns
        dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
        dfsource = dfsource.drop(['Oracle_CRM_External_ID__c'], axis=1)
        dfsource.fillna('',inplace=True)
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Service Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def paymentmethodrules(self,dfsource, dfbilling, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Payment Method Rules | {str(len(dfsource))} |')
        try:
            dfbilling = dfbilling.loc[dfbilling['Success']== True] #jfrc
            dfsource = pd.merge(dfsource, dfbilling, left_on='vlocity_cmt__accountid__c', right_on='Oracle_CRM_External_ID__c', how='inner')
            # 1 - Clean dfcontact
            dfsource = dfsource.drop(['Oracle_CRM_External_ID__c','ParentId','Success','Created','Errors','RecordTypeId'], axis=1)
            dfsource = dfsource.rename(columns={'Id' : 'billingid'})
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Payment Method Rules | {str(e)} |')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Payment Method Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def contactrules(self,dfsource, dfbusiness,dfindividual, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Contact Rules | {str(len(dfsource))} |')
        try:
            # 0 - Prepare Data
            dfbusiness = dfbusiness.loc[dfbusiness['Success']== True] #jfrc
            dfbusiness =  dfbusiness[['cust_prnt_id','Id', 'OwnerId']]
            dfbusiness = dfbusiness.rename(columns = {'Id' : 'businessaccountid'})

            dfindividual = dfindividual[['individual_id','Id']]
            dfindividual = dfindividual.rename(columns = {'Id' : 'individualid'})

            dfsource = pd.merge(dfsource, dfbusiness, left_on='cust_prnt_id', right_on='cust_prnt_id', how='inner')
            dfsource = pd.merge(dfsource, dfindividual, left_on='contact_id', right_on='individual_id', how='inner')

            # 1 - Clean dfcontact
            #dfsource = dfsource.drop(['Oracle_CRM_External_ID__c'], axis=1)
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            # Email Validation
            dfsource['email'] = dfsource['email'].apply(self.check_email)
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Contact Rules | {str(e)} |')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Contact Rules Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def individualrules(self,dfsource, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Individual Rules | {str(len(dfsource))} |')
        try:
            # 1 - Clean dfcontact
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Individual Rules | {str(e)} |')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Individual Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def consentrules(self,dfsource,dfinvidual,dfdatausepurpose,mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Consent Rules | {str(len(dfsource))} |')
        try:

            dfinvidual = dfinvidual.drop(['Success','Created','Errors'], axis=1)
            # 1 - Clean dfcontact
            dfsource = pd.merge(dfsource, dfinvidual,
                                left_on='party_id',
                                right_on='individual_id',
                                how='inner')


            dfsource = pd.merge(dfsource, dfdatausepurpose,
                                left_on='DataUsePurposeId',
                                right_on='datausepurpose',
                                how='inner')
            dfsource = dfsource.rename(columns={'Id' : 'partyid'})
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Consent Rules | {str(e)} |')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Consent Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def contractrules(self,dfsource,dfsuborders,mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Contract Rules | {str(len(dfsource))} |')
        try:
            # 0 - Group Order Item
            dfsuborders = dfsuborders.groupby(['order_id','MasterOrder','business_id']).size().reset_index(name='Count')
            dfsuborders = dfsuborders.sort_values(by='Count', ascending=True)
            # 1 - Clean dfcontact
            dfsource = pd.merge(dfsource,dfsuborders, left_on='order_id', right_on='order_id', how='inner')
            # 2 - Mapping fixed columns
            dfsource = self.mappingcolumns(mapping = mappings, dfsource = dfsource)
            dfsource.fillna('',inplace=True)
        except Exception as e:
            logger.exception(f'Fail | Contract Rules | {str(e)} |')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Contract Rules | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def mappingcolumns(self, mapping,dfsource) ->pd.DataFrame:
        for col, value in mapping.items():
            dfsource[col] = value
        return dfsource
    def check_email(self, email : str) -> str:
        pattern =  r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if re.match(pattern, email):
            return email
        else:
            return ''