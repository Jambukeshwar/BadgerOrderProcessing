import json
import pandas as pd
from utils.sfmanagement import SalesforceManagement
from utils.rulesmanagement import RulesManagement
from utils.ordermanagement import OrderManagement
from utils.orchesmanagement import OrchesManagement
from schemas.migrationsetting import MigrationSetting
import requests
from datetime import datetime
import time
import os
import uuid
from schemas.orderpayload import Offer, ChildProduct,OrderPayload
from utils.logger import Logger
#import boto3
from utils.regtimeproc import Regtimeproc

#logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s',
#                    datefmt='%Y-%m-%d %H:%M:%S',
#                    level=logging.INFO)
#logger = logging.getLogger(__name__)

logger = Logger().get_logger()

class Processing(object):
    def __init__(self, migrationsetting : MigrationSetting, sf : SalesforceManagement) -> None:
        self.migrationsetting = migrationsetting
        self.sf = sf
        self.rulemanagement = RulesManagement()
        #logger.info(migrationsetting)
        with open(f'rulesmappings/mappings.json', 'r') as file:
            self.mappings = json.load(file)
        #self.dflogs = pd.DataFrame()
        self.aws_access_key = None
        self.aws_secret_access = None
        if(self.migrationsetting.awsenvironment== 'qasales'):
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_QA')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_QA')
        elif(self.migrationsetting.awsenvironment== 'dev'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_DEV')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_DEV')
        elif(self.migrationsetting.awsenvironment== 'uatsfdc'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_UAT')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_UAT')
        elif(self.migrationsetting.awsenvironment== 'prod'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY')
        self.mitoresponse = os.environ.get('AWS_RESPONSE_MITO_STATIC')
    def startmigrationentity(self,entity, businessfile , billingfile , individualfile, suborderfile):
        st = time.time()
        # Get Mappings
        rulemapping = self.getentitymapping(entity = entity)
        # 1. Read Data from S3
        dfdata = self.reads3file(entity = entity)
        logger.info(f'Start | {entity} | # {str(len(dfdata))}')
        # 2. Tranform rules
        dfdatausepurpose = pd.DataFrame()
        if entity == 'consent':
            # Query Get DataUsePurpose
            soql = "SELECT Id, Name from DataUsePurpose"
            dfdatausepurpose  = self.sf.queryBulk(soql=soql, object_name='DataUsePurpose')
            dfdatausepurpose = dfdatausepurpose.drop(columns=['attributes'])
            dfdatausepurpose = dfdatausepurpose.rename(columns={'Id':'datausepurpose_id','Name' : 'datausepurpose'})


        dfdata = self.rulemanagement.applyrules(
            entity = entity,
            dfsource = dfdata,
            businessfile = businessfile,
            billingfile = billingfile,
            individualfile = individualfile,
            dfdatausepurpose = dfdatausepurpose,
            subordersfile = suborderfile,
            mappings = rulemapping['fixedmapping']
        )
       
        # 3. Mapping
        if rulemapping['operation'] == 'insert':
            dfsource = self.processmapping(
                dfsource = dfdata,
                mappings = rulemapping['mapping']
            )
            # 4. Salesforce Bulk
            dfresult = self.uploadtosf(
                operation  = rulemapping['operation'],
                batchsize  = rulemapping['batchsize'],
                objectname = rulemapping['objectname'],
                externalid = rulemapping['externalid'],
                dfsource   = dfsource
            )
            del dfsource
        elif rulemapping['operation'] == 'upsert':
            dfdata = self.processmapping(
                dfsource = dfdata,
                mappings = rulemapping['mapping']
            )
            
            # 4. Salesforce Bulk
            dfresult = self.uploadtosf(
                operation  = rulemapping['operation'],
                batchsize  = rulemapping['batchsize'],
                objectname = rulemapping['objectname'],
                externalid = rulemapping['externalid'],
                dfsource   = dfdata
            )
        # Post Processing
        dfdata = self.postprocess(
            dfsource = dfdata,
            dfresult = dfresult,
            mappings = rulemapping['postmapping']
        )
        # 5. s3  Responses
        file_response= self.saveslog3file(
            dfdata = dfdata,
            entity = entity
        )
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))

        # 6. Check Errors
        #register Log
        """
        try:
            reg_time_proc = Regtimeproc()
            reg_time_proc.registrar_valores(proc_name='startmigrationentity', start_date='', end_date='', method_name='Business',elapsetTime=elapsed,recordsAffected=str(len(dfdata)))    
            reg_time_proc.print_Results_table()
        except Exception as e:
            logger.exception(f'ya se rompio esta cosa por:|| {str(e)}  ')
        """
        logger.info(f'Finish | {entity} | # {str(len(dfdata))} | {elapsed}')
        del dfdata
        del dfresult
        return f'{file_response}'
    def gets3file(self, entity):
        return next((file for file in self.migrationsetting.s3files if file.entity == entity), None)
    
    def reads3file(self, entity:str) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Read S3 from AWS - {entity} |  |')
        s3file = self.gets3file(entity = entity)
        sourcepath = s3file.sourcepath
        filename = s3file.filename
        bucketname = self.migrationsetting.bucketname
        try:
            #Load s3 Data
            file_name = f'{filename}'
            if entity == 'business' or entity == 'billing':
                dfdata = pd.read_csv(
                    f"s3://{bucketname}/{sourcepath}{file_name}",
                    storage_options={
                        "key" : self.aws_access_key,
                        "secret" : self.aws_secret_access
                    }, dtype={'billingpostalcode':str,'shippingpostalcode':str,'pr_consumerpinnumber__c':str}
                )
            elif entity == 'paymentmethod':
                dfdata = pd.read_csv(
                    f"s3://{bucketname}/{sourcepath}{file_name}",
                    storage_options={
                        "key" : self.aws_access_key,
                        "secret" : self.aws_secret_access
                    }, dtype={'vlocity_cmt__expirationyear__c':str,'vlocity_cmt__expirationyear__c':str}
                )   
            else:
                dfdata = pd.read_csv(
                    f"{sourcepath}{file_name}"
                )
        except Exception as e:
            logger.exception(f'Fail | Read S3 from AWS - {entity} | {str(e)} | ')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Read S3 from AWS - {entity} | {str(len(dfdata))} | {elapsed}')
        return dfdata
    def getentitymapping(self, entity):
        for rule in self.mappings['rules']:
            if rule['entity'] == entity:
                return rule
    def saveslog3file(self,dfdata, entity : str):
        st = time.time()
        logger.info(f'Start | Save S3 from AWS - {entity}| {str(len(dfdata))} |')
        try:
            s3file = self.gets3file(entity=entity)
            targetpath = s3file.targetpath
            logpath = s3file.logpath
            filename = 'res_' + s3file.filename
            bucketname = self.migrationsetting.bucketname
                
            today_ts = pd.Timestamp.today()
            dfdata.to_csv(f'{logpath}/{filename}', index=False)
            dfdata['CreatedDate'] = today_ts
            dfdata['CreatedBy'] = os.getenv('SALESFORCE_USER')
            if not bucketname or not self.aws_access_key:
                logger.info(f'Skip | S3 upload — no bucket/credentials configured |')
            else:
                if entity == 'billing':
                    print('Remove Fan Nmber column for response billing')
                    dfdata = dfdata.drop('FAN_Number__c', axis=1)
                dfdata.to_csv(
                    f"s3://{bucketname}/{targetpath}{filename}",
                    storage_options={
                        "key" : self.aws_access_key,
                        "secret" : self.aws_secret_access
                    }, index=False
                )
        except Exception as e:
            logger.exception(f'Fail | Save S3 from AWS - {entity} | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Save S3 from AWS - {entity} | {str(len(dfdata))} |{elapsed}')
        del dfdata
        return f'{logpath}/{filename}'
    def processmapping(self, dfsource, mappings):
        st = time.time()
        logger.info(f'Start | Mapping - |{str(len(dfsource))}|')
        # Data Preparing
        dfsource = dfsource.rename(columns=mappings)
        columns_to_keep = list(mappings.values())
        dfsource = dfsource[columns_to_keep]
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Mapping | {str(len(dfsource))} | {elapsed}')
        return dfsource
    def uploadtosf(self,operation,batchsize,objectname,externalid,dfsource) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Upload Salesforce - {objectname} - {operation}| {str(len(dfsource))} |')
        try:

            
            if dfsource.empty:
                raise ValueError("data frame vacio")



            parsedata = json.loads(dfsource.to_json(orient='records'))
            if operation == 'upsert':
                dfresult = self.processbulkupsert(
                    batchsize = int(batchsize),
                    objectname = objectname,
                    parsedata = parsedata,
                    externalid = externalid
                )

            if operation == 'insert':
                dfresult = self.processbulkinsert(
                    batchsize = int(batchsize),
                    objectname = objectname,
                    parsedata = parsedata
                )
        except Exception as e:
            logger.exception(f'Fail | Upload Salesforce | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Upload Salesforce | {str(len(dfresult))} | {elapsed}')
        return dfresult
    def processbulkinsert(self, batchsize, objectname, parsedata) -> pd.DataFrame:
        # Bulk V 1
        dfresult = self.sf.insertBulk(
            object_name = objectname,
            parsedata = parsedata,
            batch_size = batchsize,
            use_serial = False
        )
        return dfresult
    def processbulkupsert(self, batchsize, objectname, parsedata, externalid) -> pd.DataFrame:
        # Bulk V 1
        dfresult = self.sf.upsertBulk(
            object_name = objectname,
            parsedata = parsedata,
            batch_size = batchsize,
            external_id = externalid,
            use_serial = False
        )
        return dfresult
    def postprocess(self, dfsource, dfresult, mappings) -> pd.DataFrame:
        st = time.time()
        logger.info(f'Start | Post Process | {str(len(dfsource))} |')
        try:
            dfsource = dfsource.merge(dfresult, left_index=True, right_index=True)
            # Data Preparing
            dfsource = dfsource.rename(columns=mappings)
            columns_to_keep = list(mappings.values())
            dfsource = dfsource[columns_to_keep]
        except Exception as e:
            logger.exception(f'Fail | Save S3 from AWS | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Post Process | {str(len(dfresult))} | {elapsed}')
        return dfsource
    def createservice(self,entity:str,billingfile:str) -> str:
        """Create Service Accounts for Master Orders and Sub Orders

        Args:
            entity (str): entity object
            billingfile (str): name of bililngfile

        Returns:
            str: name of order item response
        """
        # Get PriceBookEntry
        st = time.time()
        logger.info(f'Start | Orders Creations - PostCart -SubmitOrder| |')
        soql = "Select Id, ProductCode, Product2Id FROM PricebookEntry where Pricebook2.Name = 'LCPR B2B' and IsActive = true "
        dfproducts  = self.sf.queryBulk(soql=soql, object_name='PricebookEntry')
        dfproducts = dfproducts.drop(columns=['attributes'])
        dfproducts = dfproducts.rename(columns={'Id':'PricebookEntryId'})
        dfbilling = pd.read_csv(billingfile)
        dfbilling = dfbilling.loc[dfbilling['Success']== True] #jfrc
        dfbilling = dfbilling.rename(columns= {'Oracle_CRM_External_ID__c' : 'PR_Customer_Number__c'})

        dforder = self.reads3file(entity = entity)
        dforder.to_csv('log/order_item.csv')
        dforder = pd.merge(dforder, dfproducts, left_on='product2id', right_on='ProductCode', how='left')
        print('merge accounts')
        dforder = pd.merge(dforder, dfbilling,
                           left_on='vlocity_cmt__billingaccountid__c',
                           right_on='PR_Customer_Number__c',
                           how='inner')
        
        print(dforder)
        print('Filter only Bundles')
        # Filter only Bundles
        dforderbundle = dforder.loc[dforder['vlocity_cmt__linenumber__c'].isin([1.00,2.00,3.00,4.00,5.00,6.00,7.00])]
        # Group by for Generate Services Accounts
        print('Group Orders')
        dfordergroup = dforderbundle.groupby(
            ['subsrptn_id',
             #'vlocity_cmt__linenumber__c',
             'ParentId',
             'vlocity_cmt__billingaccountid__c',
             'FAN_Number__c']).size().reset_index(name='Count')
        
        #dfordergroup.to_csv('log/OrderMerge.csv')
        # Prepare Data for Create Service Accounts
        dfsource = dfordergroup
        print(dfsource)
        mapping = {'vlocity_cmt__billingaccountid__c' : 'Oracle_CRM_External_ID__c'} # vlocity_cmt__BillingAccountId__c
        dfsource = dfsource.rename(columns= mapping)
        
        dfsource['Oracle_CRM_External_ID__c'] = dfsource['Oracle_CRM_External_ID__c'] +  dfsource['subsrptn_id']
        dfsource['Name'] = dfsource['Oracle_CRM_External_ID__c'].astype(str) + '- M2M'
        dfsource['CurrencyIsoCode'] = 'USD'
        dfsource['RecordTypeId'] = '0120h000000iA7yAAE'
        #dfsource['RecordTypeId'] = '0127d000001Zjx7AAC'
        dfsource['CountryAccount__c'] = 'Puerto Rico'
        dfsource['BP_Country__c'] = 'Puerto Rico'
        dfsource['BillingCountry'] = 'Puerto Rico'
        dfsource['Billing_Entity__c'] = 'PR'
        dfsource['vlocity_cmt__Status__c'] = 'Active'
        #dfsource['Segment__c'] = 'B2B'
        dfsource['MSISDN__c'] = '1'+dfsource['subsrptn_id'].astype(str)  #jfrc 
        dfsource['vlocity_cmt__AccountPaymentType__c'] = 'Postpaid'
        dfsource = dfsource[[
            'Oracle_CRM_External_ID__c',
            'Name',
            'CountryAccount__c',
            #'BP_Country__c',
            'BillingCountry',
            'Billing_Entity__c',
            'CurrencyIsoCode',
            'RecordTypeId',
            'vlocity_cmt__AccountPaymentType__c',
            'vlocity_cmt__Status__c',
            'ParentId',
            #'Segment__c',
            'MSISDN__c',
            'FAN_Number__c'
            ]]
        print(dfsource)
        dfsource.to_csv('log/preSAveService.csv')
        print('Create Service Accounts')
        dfresult =  self.uploadtosf(operation='upsert',
                                    batchsize=50,
                                    externalid='Oracle_CRM_External_ID__c',
                                    objectname='Account',
                                    dfsource = dfsource

        )
        dfresult.to_csv('log/srv_created.csv', index=False)
        #def updateServiceSegment(self,accFile):
        st = time.time()
        logger.info(f'Start | Update Segmentc__c for Accounts  | |')
        response = []
        payload_list = []
        updates = []
        try:
            dfresult = pd.read_csv('log/srv_created.csv')
            dfresult = dfresult.loc[dfresult['success']== True] #jfrc
            print(f'hector:{dfresult}')
            if len(dfresult) > 0:
                for index, row in dfresult.iterrows():
                    update_data = {
                        'Id': row['id'],
                        'Segment__c' :'B2B',
                        'Customer_Sub_Type__c' :'Wholesale/M2M',
                    }
                    updates.append(update_data)
                dict_result = self.sf.upsertBulk('Account',updates,'Id',200,False)
                logger.info(f'END Update Segment Account-  ||')
            else:
                logger.info(f'Error update segment in  account - file its Empty ||')
        except Exception as e:
            logger.exception(f'Fail | updateAccountSegment update Account segment Invoke | {str(e)} | ')
            elapsed_time = time.time() - st
            elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
            logger.info(f'End | updateAccountSegment update Account segment Invoke |  | {elapsed}')    
          
           
        dfsource = dfsource.merge(dfresult, left_index=True, right_index=True)
        print('create key service')
        dforder['serviceid'] =  dforder['vlocity_cmt__billingaccountid__c'] + dforder['subsrptn_id']

        dforder = pd.merge(dforder,
                           dfsource,
                           left_on='serviceid',
                           right_on='Oracle_CRM_External_ID__c',
                           how='inner')
        print('creae service response')
        file_response = f'log/dforder.csv'
        dforder.to_csv(file_response, index=False)

        print('Init orders')
        #batch_size_orders = 10
        batch_size_orders = 1
        order_management = OrderManagement()
        response = []
        dfresult = pd.DataFrame()
        file_response = ''
        if len(dforder) > 0:
            logger.info(f'Start | <<</>>> Order Generate Payload |')
            dfmasterorders = order_management.getmasterorders(dforder=dforder)
            dfmasterorders = dfmasterorders.drop_duplicates(subset=['ParentId_x'])
            dfmasterorders.reset_index(drop=True, inplace=True)

            file_response = f'log/dfmasterordersHeaders.csv'
            dfmasterorders.to_csv(file_response, index=False)

            for i, business in dfmasterorders.iterrows():
                #print(f' master number row: | {i}')
                uniqueid = str(uuid.uuid4())
                df_suborders = dforder.loc[dforder['ParentId_x'] == business['ParentId_x'] ]
                #print('antes de crear el grupo de subordenes')
                dfgroupsuborder = df_suborders.loc[df_suborders['ParentId_x'] == business['ParentId_x']].groupby(['ParentId_x','subsrptn_id']).size().reset_index(name='Count')
                logger.info(f' Total Sub Orders nuevas : {str(len(dfgroupsuborder))}')
                
                #print(f'valores organizados:{dfgroupsuborder}')
                #dforderNew = pd.DataFrame()
                dtcolumns = 'subsrptn_id' #dfgroupsuborder.columns
                dfsordersforpayload = pd.DataFrame(columns=['subsrptn_id'])
                for o, dfsordersjf in dfgroupsuborder.iterrows():
                    dfsordersforpayload.loc[len(dfsordersforpayload)] = dfsordersjf['subsrptn_id'] 
                    #print(f'PAYLOD DIVIDIDO contador || {o} - ||{len(dfsordersforpayload)}')
                    if (o + 1) % batch_size_orders == 0 or o == len(dfgroupsuborder) - 1:                    
                        filename = f'log/suborders{o}.csv'
                        dfsordersforpayload.to_csv(filename, index=False)
                        #try:
                        #df_subordersSend = df_suborders.loc[df_suborders['subsrptn_id'] == dfsordersforpayload['subsrptn_id']]
                        df_subordersSend = df_suborders[df_suborders['subsrptn_id'].isin(dfsordersforpayload['subsrptn_id'])]
                        print(f'ordenes a enviar filtradas -->{len(df_subordersSend)}')
                        dict_payload = order_management.payloadbybusiness(dforder=df_subordersSend,business=business,uniqueid=uniqueid)
                        with open('log/payloadjson.json', 'a') as file:
                            json.dump(dict_payload, file)
                        time.sleep(3)
                        logger.info(f'Invoque Apex ws CreateOrderJst ')
                        
                        dict_result = self.sf.invokeApex(payload=dict_payload, endpoint='CreateOrderJst/createMasterOrderAndSubOrder/') #Ajuste de Jaceck
                        #--SIM SWAP--
                        #dict_result = self.sf.invokeApex(payload=dict_payload, endpoint='CreateOrderJstss/createMasterOrderAndSubOrder/') #Ajuste de Juan
                        logger.info(f'Apex Response | <</>> {dict_result}')
                        if len(dict_result) > 0:
                            dict_result['businessid'] = business['ParentId_x']
                            dict_result['order_id'] = business['order_id']
                            response.append(dict_result)
                        dfsordersforpayload = dfsordersforpayload.drop(dfsordersforpayload.index)    
                        
                            
                        #    print(f' payload: {dict_payload}')
                        #except Exception as e:
                        #    print(f'error || {str(e)}')

            time.sleep(45)
            logger.info(f'End   |  Order Generate Payload |')
            logger.info(f'Start |  Create data for Contracts |')
            if len(response) > 0:
                file_response = order_management.generateorderitemresponse(dict_result=response)
                ##register file into aws directory
                #print(f'Upload- {file_response} to s3 directory')
                #self.uploadfiletos3(file_response,'order_item')
                    
            logger.info(f'Start |  In Development |')
            logger.info(f'End |  Create data for Contracts |')
            #save payload file in s3
            #logger.info(f'start | copy payload file to s3  |')
            #self.uploadfiletos3(logfilename='payloadjson.txt' ,entity='order_item')
            #logger.info(f'end | file payloadjson copied |')
        else:
            logger.info(f'Fail Empty | Empty Master Orders Check Billing vs Order Item |')
        logger.info(f'End | Post Orders | ')
        return file_response

    def createAriaMatrix(self):
        st = time.time()
        payload = ''
        logger.info(f'Start | Aria - Matrix Integration| |')
        try:
            dfresult = self.sf.invokeApex(payload=payload, endpoint='AriaMatrixInvoker/InvokeMethod')
        except Exception as e:
            logger.exception(f'Fail | Aria - Matrix Integration | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Aria - Matrix Integration |  | {elapsed}')
        return dfresult

    """ Invoke Aria Account Creation - Step 1 """
    def invokeariaaccountcreation(self,billingfile, batch):
        st = time.time()
        logger.info(f'Start | Aria Account Creation Invoke | |')
        response = []
        dfresult = pd.DataFrame()
        file_response = ''
        try:
            dfbilling = pd.read_csv(billingfile)
            dfbilling = dfbilling.loc[dfbilling['Success']== True] #jfrc
            vipname = 'eq_AriaAccountCreation_in'
            endpoint = f'vlocity_cmt/v1/integrationprocedure/{vipname}'
            for i, billing in dfbilling.iterrows():
                payload ={
                    "BillingAccountId" : billing['Id'],
                    "BillingCountryCode" : "PR"
                }
                dict_result = self.sf.invokeApex(payload=payload, endpoint=endpoint)
                for key in dict_result:
                    payload[key] = dict_result[key]
                response.append(payload)
            dfresult = pd.DataFrame(response)
            file_response = f'log/step01_ariaaccountcreation.csv'
            dfresult.to_csv(file_response, index=False)

        except Exception as e:
            logger.exception(f'Fail | Aria Account Creation Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Aria Account Creation Invoke |  | {elapsed}')
        return file_response

    """ Invoke Aria Payment Method - Step 2 """
    def invokeariapaymentmethod(self,billingfile, batch):
        st = time.time()
        logger.info(f'Start | Aria Payment Method Invoke | |')
        response = []
        dfresult = pd.DataFrame()
        file_response = ''
        try:
            dfbilling = pd.read_csv(billingfile)
            dfbilling = dfbilling.loc[dfbilling['Success']== True] #jfrc
            #dfbilling = dfbilling.loc[dfbilling['IsError'] == False]
            if len(dfbilling) > 0:
                vipname = 'eq_AriaPaymentMethod_in'
                endpoint = f'vlocity_cmt/v1/integrationprocedure/{vipname}'
                for i, billing in dfbilling.iterrows():
                    payload ={
                        "BillingAccountId" : billing['Id'],
                        "BillingCountryCode" : 'PR'
                    }
                    dict_result = self.sf.invokeApex(payload=payload, endpoint=endpoint)
                    for key in dict_result:
                        payload[key] = dict_result[key]
                    response.append(payload)

                dfresult = pd.DataFrame(response)
                file_response = f'log/step02_ariapaymentmethod.csv'
                dfresult.to_csv(file_response, index=False)
            else:
                logger.info(f'Error Empty | Aria Payment Method Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | Aria Payment Method Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Aria Payment Method Invoke |  | {elapsed}')
        return file_response

    """ Invoke Aria Update Payment Method - Step 3 """
    def invokeariaupdatepaymentmethod(self,billingfile, batch):
        st = time.time()
        logger.info(f'Start | Aria Update Payment Method Invoke | |')
        response = []
        try:
            dfbilling = pd.read_csv(billingfile)
            dfbilling = dfbilling.loc[dfbilling['IsError']== False] #jfrc
           # dfbilling = dfbilling.loc[dfbilling['IsError'] == False]
            if len(dfbilling) > 0:
                dfbilling = dfbilling.drop(columns={'IsError'})
                vipname = 'eq_AriaUpdatePaymentMethod_in'
                endpoint = f'vlocity_cmt/v1/integrationprocedure/{vipname}'
                for i, billing in dfbilling.iterrows():
                    payload ={
                        "BillingAccountId" : billing['BillingAccountId'],
                        "BillingCountryCode" : billing['BillingCountryCode']
                    }
                    dict_result = self.sf.invokeApex(payload=payload, endpoint=endpoint)
                    for key in dict_result:
                        payload[key] = dict_result[key]
                    response.append(payload)

                dfresult = pd.DataFrame(response)
                file_response = f'log/step03_ariaupdatepaymentmethod.csv'
                dfresult.to_csv(file_response, index=False)
            else:
                logger.info(f'Error Step 2 - Empty | Aria Update Payment Method Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | Aria Update Payment Method Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Aria Update Payment Method Invoke |  | {elapsed}')
        return response

    """ Invoke Matrixx Customer Creation - Step 1 """
    def invokematrixxcustomercreation(self,businessfile, batch):
        st = time.time()
        logger.info(f'Start | Matrixx Customer Creation Invoke | |')
        response = []
        try:
            dfbusiness = pd.read_csv(businessfile)
            dfbusiness =dfbusiness.loc[dfbusiness['Success']== True] #jfrc
            if len(dfbusiness) > 0:
                vipname = 'eq_MatrixxCustomerCreation_in'
                endpoint = f'vlocity_cmt/v1/integrationprocedure/{vipname}'
                for i, business in dfbusiness.iterrows():
                    payload ={
                        "AccountId" : business['Id'],
                        "BillingCountryCode" : 'PR'
                    }
                    dict_result = self.sf.invokeApex(payload=payload, endpoint=endpoint)
                    for key in dict_result:
                        payload[key] = dict_result[key]
                    response.append(payload)

                dfresult = pd.DataFrame(response)
                file_response = f'log/step01_matrixxcustomercreation.csv'
                dfresult.to_csv(file_response, index=False)
            else:
                logger.info(f'Error Step 1 - Empty | Matrixx Customer Creation Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | Matrixx Customer Creation Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Matrixx Customer Creation Invoke |  | {elapsed}')
        return response

    """ Invoke Matrixx Account Creation - Step 2 """
    def invokematrixxaccountcreation(self,billingfile, batch):
        st = time.time()
        logger.info(f'Start | Matrixx Account Creation Invoke | |')
        response = []
        try:
            dfbilling = pd.read_csv(billingfile)
            dfbilling = dfbilling.loc[dfbilling['Success']== True] #jfrc
            if len(dfbilling) > 0:
                vipname = 'eq_MatrixxAccountCreation_in'
                endpoint = f'vlocity_cmt/v1/integrationprocedure/{vipname}'
                for i, billing in dfbilling.iterrows():
                    payload ={
                        "BillingAccountId" : billing['Id'],
                        "BillingCountryCode" : 'PR'
                    }
                    dict_result = self.sf.invokeApex(payload=payload, endpoint=endpoint)
                    for key in dict_result:
                        payload[key] = dict_result[key]
                    response.append(payload)

                dfresult = pd.DataFrame(response)
                file_response = f'log/step02_matrixxaccountcreation.csv'
                dfresult.to_csv(file_response, index=False)
            else:
                logger.info(f'Error Step 2 - Empty | Matrixx Account Creation Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | Matrixx Account Creation Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Matrixx Account Creation Invoke |  | {elapsed}')
        return response

    """ CREATE BANCAN BUSINESS """
    def createBanCanBusiness(self,businessfile):
        st = time.time()
        logger.info(f'Start | BanCan Business Account Creation Invoke | |')
        response = []
        payload_list = []
        batch_size = 100
        try:
            dfbusiness = pd.read_csv(businessfile)
            dfbusiness = dfbusiness.loc[dfbusiness['Success']== True] #jfrc
            if len(dfbusiness) > 0:
                for i, business in dfbusiness.iterrows():
                    payload_list.append(business['Id'])
                    payload = {
                            "currentList": payload_list
                    }
                    if (i + 1) % batch_size == 0 or i == len(dfbusiness) - 1:
                        dict_result = self.sf.invokeApex(payload=payload, endpoint='BanCanInvoker/InvokeBanCan')
                        dfresult = pd.DataFrame.from_dict(data=dict_result, orient='index', columns=['bancan'])
                        dfresult = dfresult.reset_index()
                        dfresult = dfresult.rename(columns={'index': 'businessid'})
                        payload_list = []
                        file_path = 'log/banCanBusiness.csv'
                        if os.path.exists(file_path):
                            existing_columns = pd.read_csv(file_path, nrows=0).columns
                            if 'businessid' not in existing_columns or 'bancan' not in existing_columns:
                               dfresult.to_csv(file_path, mode='a', header=False, index=False)
                        else:
                            dfresult.to_csv(file_path, index=False)   
            else:
                logger.info(f'Error BanCan Business creation - Empty |  createBanCanBusiness Account Creation Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | createBanCanBusiness Account Creation Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | createBanCanBusiness Account Creation Invoke |  | {elapsed}')
        return response

    def createBanCanBilling(self,billingfile):
        st = time.time()
        logger.info(f'Start | BanCan Billing Account Creation Invoke | |')
        response = []
        payload_list = []
        batch_size = 100
        try:
            dfbillings = pd.read_csv(billingfile)
            dfbillings = dfbillings.loc[dfbillings['Success']== True] #jfrc
            print(f'numero de cuentas:{len(dfbillings)}')
            if len(dfbillings) > 0:
                for i, billing in dfbillings.iterrows():
                    #payload_list = dfbillings['Id'].tolist()
                    payload_list.append(billing['Id'])
                    payload = {
                            "currentList": payload_list
                    }
                    print(f'Payload enviado {payload}')
                    print(f'operacion batch || {(i + 1) % batch_size}')
                    print(f'longitud billings longitud|| {len(dfbillings)} || menos uno: {len(dfbillings) - 1}')
                    if (i + 1) % batch_size == 0 or i == len(dfbillings) - 1:
                        dict_result = self.sf.invokeApex(payload=payload, endpoint='BanCanInvoker/InvokeBanCan')
                        print(dict_result)
                        dfresult = pd.DataFrame.from_dict(data=dict_result, orient='index', columns=['bancan'])
                        dfresult = dfresult.reset_index()
                        dfresult = dfresult.rename(columns={'index': 'billingid'})
                        payload_list = []
                        file_path = 'log/banCanBilling.csv'
                        if os.path.exists(file_path):
                            with open(file_path, 'r') as file:
                                first_line = file.readline()

                            if 'billingid,bancan' not in first_line:
                                dfresult.to_csv(file_path, mode='a', header=False, index=False)
                        else:
                            dfresult.to_csv(file_path, index=False)   
            else:
                logger.info(f'Error BanCan Billing creation - Empty |  createBanCanBilling Account Creation Invoke | |')
        except Exception as e:
            logger.exception(f'Fail | createBanCanBilling Account Creation Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | createBanCanBilling Account Creation Invoke |  | {elapsed}')
        return response
    def updateAccountSegment(self,accFile):
        st = time.time()
        logger.info(f'Start | Update Segmentc__c for Accounts  | |')
        response = []
        payload_list = []
        updates = []
        try:
            dfbillings = pd.read_csv(accFile)
            dfbillings = dfbillings.loc[dfbillings['Success']== True] #jfrc
            if len(dfbillings) > 0:
                for index, row in dfbillings.iterrows():
                    update_data = {
                        'Id': row['Id'],
                        'Segment__c' :'B2B',
                    }
                    updates.append(update_data)
                dict_result = self.sf.upsertBulk('Account',updates,'Id',200,False)
                logger.info(f'END Update Segment Account-  ||')
            else:
                logger.info(f'Error update segment in  account - file its Empty ||')
        except Exception as e:
            logger.exception(f'Fail | updateAccountSegment update Account segment Invoke | {str(e)} | ')
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | updateAccountSegment update Account segment Invoke |  | {elapsed}')
        return response

    def generaremitoresponse(self)->str:
        """ Generate Response to Mito this method connect with Endpoint Mito

        Returns:
            str: Response Ok or Fail 
        """
        st = time.time()
        logger.info(f'Start | Generate Mito   | |')
        bucketname = self.migrationsetting.bucketname
        url_aws = f's3://{bucketname}/'

        business = self.gets3file('business')
        billing = self.gets3file('billing')
        paymentmethod = self.gets3file('paymentmethod')
        individual = self.gets3file('individual')
        contact = self.gets3file('contact')
        contract = self.gets3file('contract')
        orderitem = self.gets3file('order_item')
        cust_type = "b2b"
        environ = self.migrationsetting.sfenvironment
        res = '' 

        try:

            resstr = 'res_'
            url_response =  f'{self.mitoresponse}/{self.migrationsetting.mitobasepath}/sf-response-b2b'
            payload = {
                "account" : {
                    "s3_path" : f'{url_aws}{business.targetpath}{resstr}{business.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"account"
                },
                "billing" : {
                    "s3_path" : f'{url_aws}{billing.targetpath}{resstr}{billing.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"billing"
                },
                "contact" : {
                    "s3_path" : f'{url_aws}{contact.targetpath}{resstr}{contact.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"contact"
                },
                "individual" : {
                    "s3_path" : f'{url_aws}{individual.targetpath}{resstr}{individual.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"individual"
                },
                "payment" : {
                    "s3_path" : f'{url_aws}{paymentmethod.targetpath}{resstr}{paymentmethod.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"payment"
                },
                "contract" : {
                    "s3_path" : f'{url_aws}{contract.targetpath}{resstr}{contract.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"contract"
                },
                "order_item" : {
                    "s3_path" : f'{url_aws}{orderitem.targetpath}{resstr}{orderitem.filename}',
                    "env" : environ,
                    "cust_type" : cust_type,
                    "entity":"orderitem"
                }
            }

            logger.info(f'Payload | Generate Mito  | {payload}')
            header = {
                "Content-Type" : "application/json"
            }
            response = requests.get(url=url_response, headers=header, json=payload)
            if response.status_code == 200:
                logger.info(f'Complete | Generate Mito  | {response.json()}')
                res = 'Completed'
            else:
                logger.info(f'Error | Generate Mito  | {response.status_code} | {response.text}')
                res = 'Error'
        except Exception as e:
            logger.exception(f'Fail | Generate Mito | {str(e)} | ')
            res = 'Fail'
        
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Generate Mito   |  | {elapsed}')
        return res

    def generateordermitoresponse(self, suborderfile : str):
        print('wait for running...')
        #time.sleep(220) ------------------JFRC

        orcmgt = OrchesManagement(sf=self.sf)
        dfsuborders = pd.read_csv(suborderfile)
        dfomsuborders = dfsuborders.copy() # Mantiene una copia de SubOrder
        #dfsobreak = dfsuborders.copy() # Mantiene una copia de SubOrder
        ciclebrokeprocess = 2
        currentcicle =0
        while not dfsuborders.empty:
            logger.info(f'Current cicle: {currentcicle}')
            
            if (currentcicle >= ciclebrokeprocess): 
                #before break, get pendind task
                #print('-------entro al if principal-----')
                #dfsuborders = orcmgt.processorchbreak(dfsuborder=dfsuborders)
                break
            else:
                dfsuborders = orcmgt.processorch(dfsuborder=dfsuborders)
                
            print(f'values orch:{len(dfsuborders)}')    
            if len(dfsuborders) > 0:
                for _,row in dfsuborders.loc[dfsuborders['status'] == 'complete'].iterrows():
                    dfomsuborders.loc[
                    (dfomsuborders['suborder_id'] == row['suborder_id'])
                    , ['status','State','Name','Error']] = [row['status'], row['State'], row['Name'], row['Error']]
                dfsuborders = dfsuborders.loc[dfsuborders['status'] == '']
                dfsuborders = dfsuborders[['MasterOrder','order_id','business_id','subsrptn_id','suborder_id']]
                logger.info(f'Orchestration Plan Pending to Process: | {len(dfsuborders)}')
                logger.info(f'Orchestration Plan waiting .... | {dfsuborders}')
                #time.sleep(120)
                time.sleep(2)
                logger.info(f'Orchestration Plan start ')
            else:
                logger.info(f'End ')
            currentcicle +=1
            
        print(f'generate file:res_omsuborders {len(dfomsuborders)}')
        dfomsuborders.to_csv('log/res_omsuborders.csv', index=False)
        # Mito Response
        # 1. Transform Orch Status by SubOrders
        print(f'Start filtered ||')
        dftrans = orcmgt.readochitems(dfsuborder=dfomsuborders)
        print(f'filtered || {len(dftrans)}')
        
        if len(dftrans) > 0:
            dforderitems = orcmgt.getorderitembysuborder(dfsuborders=dfomsuborders)
            dfmerge = dforderitems.merge(dftrans,how='inner',left_on='orderid', right_on='OrderId')
            dfmerge.to_csv('log/mitoorderitemresponse.csv', index=False)
            self.saveslog3file(dfdata=dfmerge,entity='order_item') 
        else:
            logger.info(f'Empy Status for Aria & Matrix Check Orchestration Plan ')
        logger.info(f'No more Orchestrations Plan found.. ')

######JFRC ADD S3 Retriver Files
    def gets3filetocsv(self,entity):
        st = time.time()
        logger.info(f'--INICIA LA GENERACION DEL ARCHIVO--| {entity}')
        s3file = self.gets3file(entity = entity)
        dfdata = self.reads3file(entity = entity)
        filename = 's3_' + s3file.filename
        dfdata.to_csv(f'log/aws/{filename}', index=False)
        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'Finish | {entity} | # {str(len(dfdata))} | {elapsed}')
    
    
    #-----------AWS Operations------------    
    def getOrderFilesinDirectory(self):    
        bucketname = self.migrationsetting.bucketname
        s3file = next((file for file in self.migrationsetting.s3files if file.entity == 'order_item'), None)
        sourcepath = s3file.sourcepath
        s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key, aws_secret_access_key=self.aws_secret_access)
        print(f'el bucket: ||{bucketname}')
        print(f'el path: ||{sourcepath}')
        try:
            objects = s3.list_objects_v2(Bucket=bucketname, Prefix=sourcepath)
            file_Name_list = [objects['Key'] for objects in objects.get('Contents', [])]
            for archivo in file_Name_list:
                print(archivo)        
        except Exception as e:
           print(f'Fail | Read S3 from AWS - | {str(e)} | ')        
        return file_Name_list
    
    def uploadfilestos3(self):
        localdirectory = '/log'
        bucketname = self.migrationsetting.bucketname
        s3file = next((file for file in self.migrationsetting.s3files if file.entity == 'order_item'), None)
        sourcepath = s3file.sourcepath
        targetpath = s3file.targetpath
        s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key, aws_secret_access_key=self.aws_secret_access)
        print(f'el bucket: ||{bucketname}')
        print(f'el path: ||{sourcepath}')
        actualdate = datetime.now().strftime('%Y_%m_%d')
        # Nombre de la carpeta con la fecha
        logdirectory = f'{targetpath}/log/{actualdate}/'
        try:
            s3.put_object(Bucket=bucketname, Key=(logdirectory))  
            
            # Obtener la lista de archivos locales en la carpeta /log
            loglocalfiles = [f for f in os.listdir(localdirectory) if os.path.isfile(os.path.join(localdirectory, f))]
 
            for local_file in loglocalfiles:
                ruta_local_completa = os.path.join(localdirectory, local_file)
                clave_en_s3 = os.path.join(logdirectory, local_file)
            
            logger.info(f'Log_files: log files copied to s3 ')
        except Exception as e:
            logger.info(f'Fail | Copy log files from local to S3- | {str(e)} | ')

###save file to s3
    def uploadfiletos3(self, logfilename,entity):
        #carpeta de order
        bucketname = self.migrationsetting.bucketname
        s3file = next((file for file in self.migrationsetting.s3files if file.entity == entity), None)
        sourcepath = s3file.sourcepath
        targetpath = s3file.targetpath
        s3 = boto3.client('s3', aws_access_key_id=self.aws_access_key, aws_secret_access_key=self.aws_secret_access)
        print(f'- bucket: ||{bucketname}')
        print(f'-path: ||{sourcepath}')
        print(f'-logfile: ||{logfilename}')
        readfile = f'log/{logfilename}'
        actualdate = datetime.now().strftime('%Y_%m_%d')
        # Nombre de la carpeta con la fecha
        s3endpath = f'{bucketname}/{targetpath}{logfilename}_{actualdate}/'
        try:
            print(f'file to copy: ||{s3endpath}')
            s3.upload_file(readfile, bucketname, s3endpath)
            logger.info(f'Log_files: log files {s3endpath} copied to s3 ')
        except Exception as e:
            logger.info(f'Fail | Copy log files from local to S3- | {str(e)} | ')
            
###Generate response report
    def generateresponsereport(self):
        logger.info(f'Start | generateresponsereport ||')
        s3file = self.gets3file(entity = 'order_item')
        filename = s3file.filename
        targetpath = s3file.targetpath
        bucketname = self.migrationsetting.bucketname
        sourcepath = s3file.sourcepath
        
        oi_columns = [        
                        'order_item_id',
                        'prnt_order_item_id',
                        'order_id',
                        'subsrptn_id',
                        'product2id'
                        ]

        resoi_columns = [        
                        'orderitem_id',
                        'order_id',  #remover la columna antes del merge
                        'productname',
                        'ProductCode',
                        'orchestrationplan_id',
                        'ban_can',
                        'OrderId',
                        'ariastatus',
                        'matrixxstatus',
                        'orchestrationplanstatus',
                        'Nokia Migrate (reIMSI) Line State',
                        'ariaerror',
                        'matrixxerror',
                        'orchestrationplanerror',
                        'Nokia Migrate (reIMSI) Line Error'
                        ]            
        
        report_columns=['order_item_id',
                        'prnt_order_item_id',
                        'order_id',
                        'orderitem_id',
                        'productname',
                        'ProductCode',
                        'subsrptn_id',
                        'orchestrationplan_id',
                        'ban_can',
                        'OrderId',#rename 'OrderId' 
                        'ariastatus',
                        'matrixxstatus',
                        'orchestrationplanstatus',
                        'Nokia Migrate (reIMSI) Line State',
                        'ariaerror',
                        'matrixxerror',
                        'orchestrationplanerror',
                        'Nokia Migrate (reIMSI) Line Error']

        #nombre del archivo: new_res_Filename
        #dejarlo en: targetpath = "targetpath": "Salesforce/Customer_Feed_b2b/sf_response/cust_order_item/load/"
        
        #Read order Item File
        try:
            df_orderitem = pd.read_csv('log/order_item.csv', usecols=oi_columns, na_values='', keep_default_na=False)
            df_orderitem['key'] = df_orderitem['product2id'].astype(str) + df_orderitem['subsrptn_id'].astype(str)
            print(f'el order_item || {df_orderitem}')
            # Read res order item file — not all orchestration columns exist in every run
            dfres_orderitem = pd.read_csv(f'log/res_{filename}', na_values='', keep_default_na=False)
            optional_orch_cols = [
                'ariastatus', 'matrixxstatus', 'orchestrationplanstatus',
                'Nokia Migrate (reIMSI) Line State',
                'ariaerror', 'matrixxerror', 'orchestrationplanerror',
                'Nokia Migrate (reIMSI) Line Error'
            ]
            for col in optional_orch_cols:
                if col not in dfres_orderitem.columns:
                    dfres_orderitem[col] = ''
            required_cols = ['orderitem_id', 'order_id', 'productname', 'ProductCode',
                             'orchestrationplan_id', 'ban_can', 'OrderId']
            keep_cols = [c for c in required_cols + optional_orch_cols if c in dfres_orderitem.columns]
            dfres_orderitem = dfres_orderitem[keep_cols]
            dfres_orderitem['key'] = dfres_orderitem['ProductCode'].astype(str) + dfres_orderitem['order_id'].astype(str)
            dfres_orderitem = dfres_orderitem.fillna(0)
            dfres_orderitem.rename(columns={'order_id': 'ordidremove'}, inplace=True)
        except Exception as e:
            logger.info(f"Error merge files an generate response: {str(e)}")
            dfres_orderitem = None

        try:
            if dfres_orderitem is None:
                raise ValueError("res order item file could not be loaded")
            # Only keep report_columns that actually exist after tolerant load
            available_report_cols = [c for c in report_columns if c in list(df_orderitem.columns) + list(dfres_orderitem.columns) + ['key']]
            df_order_merge = pd.merge(df_orderitem, dfres_orderitem, on='key')
            final_cols = [c for c in report_columns if c in df_order_merge.columns]
            df_order_merge = df_order_merge[final_cols]
            df_order_merge.rename(columns={'OrderId': 'sf_order_id'}, inplace=True)
            resut_file = f'log/new_res_{filename}'
            df_order_merge.to_csv(resut_file, index=False)
            logger.info(f'end generate mito file response process — saved to {resut_file}')
        except Exception as e:
            logger.info(f"Error merge files or upload in s3: {str(e)}")

        logger.info(f'end generate mito file response process')
        
    def generateordermitoresponseall(self, suborderfile : str):
        print('wait for running...')
        import pathlib
        pathlib.Path('log/res_orchitems.csv').unlink(missing_ok=True)

        orcmgt = OrchesManagement(sf=self.sf)
        
        dfsuborders = pd.read_csv(suborderfile)
        dfomsuborders = dfsuborders.copy() # Mantiene una copia de SubOrder
        dfsuborders = orcmgt.processorchbreak(dfsuborder=dfsuborders)
       
        print(f'values orch:{len(dfsuborders)}')    
        if len(dfsuborders) > 0:
            print('inicia ciclo armado va a recorrer')
            try:
                for _,row in dfsuborders.iterrows():
                    dfomsuborders.loc[
                    (dfomsuborders['suborder_id'] == row['suborder_id'])
                    , ['status','State','Name','Error']] = [row['status'], row['State'], row['Name'], row['Error']]
            except Exception as e:
                logger.info(f"ciclo armado: {str(e)}")
        
        else:
            logger.info(f'End ')
            
        print(f'generate file:res_omsuborders {len(dfomsuborders)}')
        dfomsuborders.to_csv('log/res_omsuborders.csv', index=False)
        # Mito Response
        # 1. Transform Orch Status by SubOrders
        
        #dfomsuborders = pd.read_csv('log/res_omsuborders.csv')
        
        print(f'Start filtered ||')
        dftrans = orcmgt.readochitems(dfsuborder=dfomsuborders)
        print(f'filtered || {len(dftrans)}')
        
        if len(dftrans) > 0:
            print('Entro al if para generar el response')
            dforderitems = orcmgt.getorderitembysuborder(dfsuborders=dfomsuborders)
            try:
                print(f'Columnas de dforderitems{dforderitems.columns}')
                print('---------------------------------------------')
                print(f'Columnas de dftrans{dftrans.columns}')
                
                dfmerge = dforderitems.merge(dftrans,how='inner',left_on='orderid', right_on='OrderId')
                dfmerge.to_csv('log/mitoorderitemresponse.csv', index=False)
                self.saveslog3file(dfdata=dfmerge,entity='order_item') 
            except Exception as e:
                logger.info(f"response: {str(e)}")
        else:
            logger.info(f'Empy Status for Aria & Matrix Check Orchestration Plan ')
        
        logger.info(f'No more Orchestrations Plan found.. ')        

    def gets3filepayloadpath(self,entity):
        return self.gets3file(entity = entity)
 