import pandas as pd
from datetime import datetime
#import paramiko
import os
import time
from utils.logger import Logger
from utils.sfmanagement import SalesforceManagement
from schemas.migrationsetting import MigrationSetting
from prettytable import PrettyTable
import re

logger = Logger().get_logger()

class Validations(object):
    def __init__(self,migrationsetting : MigrationSetting) -> None:
        self.migrationsetting = migrationsetting
        if(self.migrationsetting.awsenvironment== 'qasales'):
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_QA')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_QA')
        elif(self.migrationsetting.awsenvironment== 'dev'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_DEV')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_DEV')
        elif(self.migrationsetting.awsenvironment== 'uat'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY_UAT')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY_UAT')
        elif(self.migrationsetting.awsenvironment== 'prod'):            
            self.aws_access_key = os.environ.get('AWS_ACCESS_KEY')
            self.aws_secret_access = os.environ.get('AWS_SECRET_KEY')        
        pass

    def retrieveSalesforceAccountPicklistalues(self):
        dfdataresult_all = pd.DataFrame()
        sPicklistOptions =['Type','CW_Account_Type__c']
        in_clause = "', '".join(sPicklistOptions)
        objectname='EntityParticle'
        soql = f"SELECT Id, EntityDefinitionId, QualifiedAPIName, FieldDefinitionId FROM EntityParticle WHERE EntityDefinition.QualifiedApiName ='Account' and QualifiedApiName in('{in_clause}')"
        sf = SalesforceManagement(environment = self.migrationsetting.sfenvironment)
        #dfdata = sf.queryBulk(object_name = objectname, soql = soql)
        dfdata = pd.DataFrame(sf.queryBulk(objectname,soql))
        try:
            #print(f'ya termino la conexion y el resultado es:{dfdata}')
            
            for index, row in dfdata.iterrows():
                #print(f"Index: {index} || {row.FieldDefinitionId}")
                picklistSoql = f"SELECT EntityParticle.Name,value FROM PicklistValueInfo Where EntityParticleId='{row.FieldDefinitionId}' and IsActive =true"
                #print(f'el query es: {picklistSoql}')
                dfdataresult = pd.DataFrame(sf.queryBulk('PicklistValueInfo',picklistSoql))
                #print(f'Valores del picklist:{row.FieldDefinitionId}|| {dfdataresult}')
                dfdataresult_all = pd.concat([dfdataresult_all, dfdataresult])
        except Exception as e:
            print(f'Fail | {e} ')
        
        print('termino los querys')
        return dfdataresult_all
        
  #Validate files to load      
    def getresultvalidatefile(self,entity):
        # Obtener los archivos
        # validar dataframes con registros
        # validar columnas requeridas en cada archivo
        # validar el tipo de dato de columnas requeridas
        # Validar en las direcciones el country (evaluar si alguno es US)
        # comparar entre archivos que esten relacionados

        # Picklist values definitions
        
        picklistdata = self.retrieveSalesforceAccountPicklistalues() 
        valor_filtrado = 'Type'
        print(f'columnas:{picklistdata.columns}')
        try:
            picklistdata_filtrado = picklistdata[picklistdata['EntityParticle'] == valor_filtrado] ####AQUI VOY FILTRANDO LOS VALORES DE LOS PICKLIST
            print(f'{picklistdata_filtrado}')
        except Exception as e:
            print(f'Fail | {e} ')
        #lista_valores = picklistdata[['col2', 'col3']].values.tolist()
        
        #print(f'resultado de las piclist || {picklistdata}')
        valid_states = ['PR', 'VI']
        valid_c_sub_type =['SOHO/Small','LE/CE','Government','Wholesale']
        valid_cw_type =['Business VIP','CWC International','Diaspora','Enterprise','Government','Hospitality & BPO','Key Accounts','Large','Managed Business','Medium','Networks Colombia','No Target','Partner','Power Resiliency Program','Private','Regional Corporate','Regional Finance','Residential','Small','SMB','SME','Strategic','Pymes','B2B','Wholesale']
        
        business_validations = {
                                #'cust_prnt_id': {},
                                #'currencyisocode': {},
                                #'name': {},
                                #'vlocity_cmt__accountpaymenttype__c': {},
                                'phone': {'min_length': 11, 'data_type': str, 'required': True},
                                'cw_account_type__c': {'allowed_values': valid_cw_type},
                                #'type': {},
                                #'billingcity': {},
                                #'billingcountry': {},
                                'billingstate': {'max_length': 2, 'data_type': str, 'allowed_values': valid_states ,'required': True},
                                #'billingstreet': {},
                                'billingpostalcode': {'min_length': 7, 'data_type': str,'required': True},
                                #'country_of_origin__c': {},
                                #'countryaccount__c': {},
                                #'numberofemployees': {},
                                #'employee_range__c': {},
                                #'shippingcity': {},
                                'shippingcountry': {'data_type': str, 'required': True, 'allowed_values': ['Puerto Rico']},
                                'shippingstate': {'max_length': 2, 'data_type': str, 'allowed_values': valid_states ,'required': True},
                                #'shippingstreetv': {},
                                #'shippingpostalcode': {},
                                #'vlocity_cmt__status__c': {},
                                #'pr_customer_number__c': {},
                                #'customer_type__c': {},
                                #'customer_sub_type__c': {},
                                #'mig_date': {},
                                'verificationstatus__c': {'allowed_values': ['Verified'],'required': True},
                                #'pr_consumerpinnumber__c': {},
                                #'industry': {},
                                'vlocity_cmt__taxid__c': {'min_length': 9, 'required': True}
                                #'pr_ssn__c': {},
                                #'vlocity_cmt__customersincedate__c': {},
                                #'vlocity_cmt__primarycontactid__c': {}
                              }



        billing_validations = {
                                #'cust_prnt_id': {},
                                #'currencyisocode': {},
                                #'name': {},
                                #'vlocity_cmt__accountpaymenttype__c': {},
                                'phone': {'min_length': 11, 'data_type': str, 'required': True},
                                #'cw_account_type__c': {},
                                'type': {'allowed_values': valid_c_sub_type},
                                #'billingcity': {},
                                #'billingcountry': {},
                                'billingstate': {'max_length': 2, 'data_type': str, 'allowed_values': valid_states ,'required': True},
                                #'billingstreet': {},
                                'billingpostalcode': {'min_length': 11, 'data_type': str,'required': True},
                                #'country_of_origin__c': {},
                                #'countryaccount__c': {},
                                #'numberofemployees': {},
                                #'employee_range__c': {},
                                #'shippingcity': {},
                                'shippingcountry': {'data_type': str, 'required': True, 'allowed_values': ['Puerto Rico']},
                                'shippingstate': {'max_length': 2, 'data_type': str, 'allowed_values': valid_states ,'required': True},
                                #'shippingstreet': {},
                                #'shippingpostalcode': {},
                                #'vlocity_cmt__status__c': {},
                                #'pr_customer_number__c': {},
                                'customer_type__c': {'allowed_values': valid_c_sub_type}
                                #'customer_sub_type__c': {},
                                #'mig_date': {},
                                #'verificationstatus__c': {},
                                #'pr_consumerpinnumber__c': {},
                                #'industry': {},
                                #'vlocity_cmt__taxid__c': {},
                                #'pr_ssn__c': {},
                                #'vlocity_cmt__customersincedate__c': {},
                                #'vlocity_cmt__primarycontactid__c': {},
                              }
        
        
        smessage =''
        resultValidation ='End validation'
        logger.info(f'--Get s3 Files---')
        # step 1 get files from S3
        try:
           dfdata_business = self.reads3file(entity = 'business')
        except Exception as e:
            self.logger.exception(f'Fail | Read S3 from AWS - business | |{e} ')
               
        try:
            dfdata_billing = self.reads3file(entity = 'billing')
        except Exception as e:
            self.logger.exception(f'Fail | Read S3 from AWS - billing | |{e} ')

        #try:
        #    dfdata_paymentmethods = self.reads3file(entity = 'paymentmethod')
        #except Exception as e:
        #    self.logger.exception(f'Fail | Read S3 from AWS - payment method | |{e} ')
            
        #dfdata_individual = self.reads3file(entity = 'individual')
        #dfdata_contact = self.reads3file(entity = 'contact')
        #dfdata_consent = self.reads3file(entity = 'consent')
        #dfdata_contract = self.reads3file(entity = 'contract')
        #dfdata_order_item = self.reads3file(entity = 'order_item')
        
        
        logger.info(f'File:Billings # of Records:{len(dfdata_billing)}')
        #logger.info(f'File:Payment methods # of Records:{len(dfdata_paymentmethods)}')
        
        
        logger.info(f'---Step 2 validate files rows---')
        # Step 2 validate rows in files (not Empty)
        if len(dfdata_business) == 0:
            logger.info(f'Business file is empty')
            #exit(1)
        else:    
            logger.info(f'Business file have {len(dfdata_business)} record(s)')
            fileBusiness = self.validateFileCharacteristics(objvalidations=business_validations ,df=dfdata_business)
            logger.info(f'End Validation biling data types{fileBusiness}')
            
        if len(dfdata_billing) == 0:
            logger.info(f'Billing file is empty')
            #exit(1)
        else:    
            logger.info(f'Billing file have {len(dfdata_billing)} record(s)')
            fileBilling = self.validateFileCharacteristics(objvalidations=billing_validations ,df=dfdata_billing)
            logger.info(f'End Validation biling data types{fileBilling}')
            

        return resultValidation

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
            #dfdata = pd.read_csv(f'{sourcepath}{file_name}')
            dfdata = pd.read_csv(
                f"s3://{bucketname}/{sourcepath}{file_name}",
                storage_options={
                    "key" : self.aws_access_key,
                    "secret" : self.aws_secret_access
                },
            )
        except Exception as e:
            logger.exception(f'Fail | Read S3 from AWS - {entity} | {str(e)} | ')

        elapsed_time = time.time() - st
        elapsed = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        logger.info(f'End | Read S3 from AWS - {entity} | {str(len(dfdata))} | {elapsed}')
        return dfdata


    def validateFileCharacteristics(self, objvalidations, df:pd.DataFrame):
        endProcess ='End'
        validationResult = True
            #validate file characteristics
        tipos_de_datos = df.dtypes
        print("Tipos de datos de todas las columnas:")
        print(tipos_de_datos)
        for column, rules in objvalidations.items():
            max_length = rules.get('max_length', None)
            min_length = rules.get('min_length', None)
            data_type = rules['data_type']
            allowed_values = rules.get('allowed_values', None)
            
            if min_length is not None:
                if not df[column].apply(lambda x: len(str(x)) >= min_length).all():
                    logger.info(f'La columna "{column}" contiene valores con una longitud menor a {min_length}')
                    invalid_rows = df[~df[column].apply(lambda x: len(str(x)) >= min_length)]
                    if not invalid_rows.empty:
                       logger.info(invalid_rows)
                    validationResult = False
            
            if max_length is not None:
                if not df[column].apply(lambda x: len(str(x)) <= max_length).all():
                    logger.info(f'La columna "{column}" contiene valores con una longitud superior a {max_length}')
                    validationResult = False

            if data_type is not None:
                if not df[column].apply(lambda x: isinstance(x, data_type)).all():
                    logger.info(f'La columna "{column}" contiene valores que no son del tipo {data_type}')
                    validationResult = False

            if allowed_values is not None:
                if not df[column].apply(lambda x: x in allowed_values).all():
                    logger.info(f'La columna "{column}" contiene valores no permitidos')
                    validationResult = False

        logger.info(f'Validation Complete')
            
        return (f'endProcess: result: {validationResult}')
    
    def validatebusinessfile(self):
        return 'nada'
    
    def validatebillingfile(self):
        return 'nada'
    
    def validatecontactfile(self):    
        return 'nada'
    
    def validateSubordersfile(self):
        #validar que los atributos esten completos
        pattern = r"'[^']+'"
        # Especifica la columna que quieres validar
        columna_a_validar = 'nombre_de_la_columna'  # Reemplaza 'nombre_de_la_columna' con el nombre de la columna que deseas validar
        # Lista para almacenar los elementos que no cumplen con la condición
        elementos_no_cumplen = []

        archivo_csv = 'ruta_del_archivo.csv'  # Reemplaza 'ruta_del_archivo.csv' con la ruta de tu archivo CSV
        df = pd.read_csv(archivo_csv)
        
        # Itera sobre los elementos de la columna y valida si cada uno está encerrado en comillas simples
        for valor in df[columna_a_validar]:
            # Busca todos los elementos que coincidan con el patrón en el valor actual
            matches = re.findall(pattern, valor)
            # Verifica si el número de elementos encontrados es igual al número total de elementos en el valor
            if len(matches) != len(re.split(r',\s*', valor)):
                elementos_no_cumplen.append(valor)

        if elementos_no_cumplen:
            print(f"Elementos en la columna '{columna_a_validar}' que no están encerrados en comillas simples:")
            for elemento in elementos_no_cumplen:
                print(elemento)
        else:
            print(f"Cada elemento en la columna '{columna_a_validar}' está encerrado en comillas simples.")

        return 'nada'