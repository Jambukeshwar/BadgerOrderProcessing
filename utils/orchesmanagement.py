#import logging
import pandas as pd
from schemas.migrationsetting import MigrationSetting
from utils.sfmanagement import SalesforceManagement
from utils.logger import Logger

#logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s',
#                    datefmt='%Y-%m-%d %H:%M:%S',
#                    level=logging.INFO)
#logger = logging.getLogger(__name__)
logger = Logger().get_logger()

class OrchesManagement(object):
    def __init__(self, sf : SalesforceManagement ) -> None:
        self.sf = sf

    def getorchitembysuborder(self, dfsuborders : pd.DataFrame) -> pd.DataFrame:
        logger.info('Start |  Get Orchestration Items |')
        ids_quotes = ["'" + str(id) + "'" for id in dfsuborders['suborder_id']]
        ids = ','.join(ids_quotes)
        dfochitems = pd.DataFrame()
        # 1. Get Orchestration Items by Sub Order Ids from Salesforce
        soql = f"""
                SELECT
                Id,
                Name,
                vlocity_cmt__OrchestrationPlanId__r.vlocity_cmt__OrderId__c,
                vlocity_cmt__OrderItemId__c,
                vlocity_cmt__State__c,
                vlocity_cmt__OrchestrationPlanId__c,
                PR_Error_Description__c
                FROM vlocity_cmt__OrchestrationItem__c
                WHERE 
                vlocity_cmt__OrchestrationPlanId__r.vlocity_cmt__OrderId__c in ({ids})
                """
                
                #vlocity_cmt__OrchestrationPlanId__r.vlocity_cmt__OrderId__r.CreatedBy.name = 'Camilo Alfonso' 
                #AND vlocity_cmt__OrchestrationPlanId__r.vlocity_cmt__OrderId__r.CreatedDate > 2023-12-13T04:55:00.000+0000
        #print(f'Query orchestation: {soql}')   
        #print('leee archivo')
        #dfochitems= pd.read_csv('log/soql_orch_12122023.csv')     
        #print('Ejecuta el query')
        dfochitems = self.sf.queryBulk(object_name='vlocity_cmt__OrchestrationItem__c', soql=soql)
        print(f'Numero de registro: {len(dfochitems)}')
        if len(dfochitems) > 0:
            try:
                print('dentro del if remove attributes')
                dfochitems = dfochitems.drop(columns=['attributes'])
                print('Elimino atributos')
                # Get Order Id
                expanded_df = pd.json_normalize(dfochitems['vlocity_cmt__OrchestrationPlanId__r'])
                #print(f'Normalizado:{expanded_df}' )
                dfochitems = pd.concat([dfochitems, pd.DataFrame(dfochitems['vlocity_cmt__OrchestrationPlanId__r'].tolist())], axis=1)
                print('concateno')
                drop_cols = [c for c in ['vlocity_cmt__OrchestrationPlanId__r', 'attributes'] if c in dfochitems.columns]
                dfochitems.drop(columns=drop_cols, inplace=True)
                print('quito relaciones')
                # Rename Columns
                cols = {
                'vlocity_cmt__OrderItemId__c' : 'OrderItemId',
                'vlocity_cmt__State__c' : 'State',
                'vlocity_cmt__OrchestrationPlanId__c' : 'OrchestrationPlanId',
                'PR_Error_Description__c' : 'Error',
                'vlocity_cmt__OrderId__c' : 'OrderId'
                }
                dfochitems = dfochitems.rename(columns=cols)
            except Exception as e:
                logger.info(f"getorchitembysuborder : {str(e)}")
            print('renombro columnas')
            dfochitems['status'] = 'New'
            print('cambio el estatus')
            dfochitems.to_csv('log/res_orchitems.csv', index=False)
            print('genero el archivo')
        else:
            logger.info('Empty |  Get Orchestration Items |')

        logger.info('End |  Get Orchestration Items |')
        return dfochitems
    def transformochitems(self, dfochitems : pd.DataFrame) -> pd.DataFrame:
        """Apply business rules

        Args:
            orcitemfile (str): orchestration item file name
        """
        # Group Fatally by Order Id
        dfochitems.loc[
                (dfochitems['State'].isin(['Fatally Failed'])) |
                ((dfochitems['Name'].isin(['End(Existing)'])) & (dfochitems['State'].isin(['Completed'])))
                , 'status'
        ] = 'complete'

        dfochitems.fillna('',inplace=True)
        dfgroupbystate = dfochitems.loc[dfochitems['status'] == 'complete'].groupby([
            'OrderId',
            'Name',
            'State',
            'Error',
            'status'
        ]).size().reset_index(name='Count')

        return dfgroupbystate
    #jfrc
    def transformochitemsbreak(self, dfochitems : pd.DataFrame) -> pd.DataFrame:
        try:
            dfochitems.loc[:,'status'] = 'complete'
            print('bloquea las celdas con complete')
            #dfochitems.loc[dfochitems['OrderId'].notna(), :]
            columnas_vacias = dfochitems.columns[dfochitems.isna().any()].tolist()
            print(f'quito los vacios{columnas_vacias}')
            dfochitems.rename(columns={'vlocity_cmt__OrchestrationPlanId__r.vlocity_cmt__OrderId__c': 'OrderId'}, inplace=True)
            print(f'renobro la columna')
            dfochitems.fillna('',inplace=True)
            print(f'COLUMNS:{dfochitems.columns}')
            dfgroupbystate = dfochitems.loc[dfochitems['status'] == 'complete'].groupby([
                'OrderId',
                'Name',
                'State',
                'Error',
                'status'
            ]).size().reset_index(name='Count')
        except Exception as e:
            logger.info(f"transformochitemsbreak : {str(e)}")

        print('termino la agrupacion de complete')
        return dfgroupbystate   
    
    def processorch(self, dfsuborder : pd.DataFrame):
        #dfsuborder = pd.read_csv(suborderfile)
        df = self.getorchitembysuborder(dfsuborders=dfsuborder)
        if len(df) > 0:
            dfordercomplete = self.transformochitems(dfochitems=df)
            dfmerge = dfsuborder.merge(dfordercomplete, how='left', left_on='suborder_id', right_on='OrderId')
            dfmerge = dfmerge.drop(['OrderId'], axis=1)
            dfmerge.fillna('',inplace=True)
            #dfmerge.to_csv('log/test_merge.csv', index=False)
        else:
            logger.info('Empty |  Not found orchestration plan to process |')
            dfmerge = pd.DataFrame()
        return dfmerge
    #jfrc    
    def processorchbreak(self, dfsuborder : pd.DataFrame):
        df = self.getorchitembysuborder(dfsuborders=dfsuborder)
        print(f'retorna file{len(df)}')
        if len(df) > 0:
            
            dfordercomplete = self.transformochitemsbreak(dfochitems=df)
            dfmerge = dfsuborder.merge(dfordercomplete, how='left', left_on='suborder_id', right_on='OrderId')
            dfmerge = dfmerge.drop(['OrderId'], axis=1)
            dfmerge.fillna('',inplace=True)
            #dfmerge.to_csv('log/test_merge.csv', index=False)
        else:
            logger.info('Empty |  Not found orchestration plan to process |')
            dfmerge = pd.DataFrame()
        return dfmerge

    def transformochitemsresponse(self, dfochitems : pd.DataFrame) -> pd.DataFrame:
        """ Transform Orchestration for Mito Response

        Args:
            orcitemfile (str): orchestration item file name
        """
        logger.info('Start | transformochitemsresponse method | ')
        try:
            # astype(object) before fillna so float64 NaN cols accept '' in pandas 2.2+
            dfochitems = dfochitems.astype(object).fillna('')
            dfgroupbystate = dfochitems.loc[
                (dfochitems['Name'].isin([
                    'Create Commercial Order Aria',
                    'Create Commercial Order Matrixx',
                    'End(Existing)',
                    'Nokia Migrate (reIMSI) Line'
                    ]))
            ].groupby([
                'OrderId',
                'Name',
                'State',
                'Error'
            ]).size().reset_index(name='Count')
            print('Termino la agrupacion')
            print(f'columnas converted:{dfgroupbystate.columns}')
            print(f'dfgroupbystate group size: {len(dfgroupbystate)}')
            dfgroupbystate.to_csv('log/dfgroupbystate.csv', index=False)

            dfpivot = dfgroupbystate.pivot_table(
                index='OrderId', columns='Name',
                values=['State', 'Error'], aggfunc='first'
            )
            print('creo la pivot')
            dfpivot.columns = [f'{col[1]} {col[0]}' for col in dfpivot.columns]
            dfpivot = dfpivot.reset_index()
            rename_columns = {
                'Create Commercial Order Aria State':   'ariastatus',
                'Create Commercial Order Matrixx State':'matrixxstatus',
                'End(Existing) State':                  'orchestrationplanstatus',
                'Nokia Migrate (reIMSI) Line State':    'nokiastatus',
                'Create Commercial Order Aria Error':   'ariaerror',
                'Create Commercial Order Matrixx Error':'matrixxerror',
                'End(Existing) Error':                  'orchestrationplanerror',
                'Nokia Migrate (reIMSI) Line Error':    'nokiaerror',
            }
            dfpivot = dfpivot.rename(columns=rename_columns)
            dfpivot.to_csv('log/pivot.csv')
            return dfpivot
        except Exception as e:
            logger.info(f"transformochitemsresponse : {str(e)}")
            return pd.DataFrame()
        
    
    def getorderitembysuborder(self, dfsuborders : pd.DataFrame) -> pd.DataFrame:
        logger.info('Start |  Get Order Items by SubOrders |')
        ids_quotes = ["'" + str(id) + "'" for id in dfsuborders['suborder_id']]
        ids = ','.join(ids_quotes)
        dfochitems = pd.DataFrame()
        # 1. Get Order Items by Sub Order Ids from Salesforce
        # TO BE part the number of order to send 100 or 200 in soql
        # and reconstruct the file res_orderitemsuborders
        soql = f"""
                Select
                    id,
                    product2.Name,
                    order.Oracle_CRM_External_Id__c,
                    product2.ProductCode,
                    orderId,
                    order.vlocity_cmt__DefaultBillingAccountId__c,
                    order.vlocity_cmt__OrchestrationPlanId__c,
                    order.vlocity_cmt__DefaultBillingAccountId__r.PR_Mobile_Billing_Number__c
                From OrderItem
                WHERE OrderId in ({ids}) 
                """
        #print(f'leo el archivo')        
        #dforderitems = pd.read_csv('log/orderitemecf.csv')        
        print('Ejecuta el query de order items')
        dforderitems = self.sf.queryBulk(object_name='OrderItem', soql=soql)
        print(f'antes del if{len(dforderitems)}')
        if len(dforderitems) > 0:
            try:
                dforderitems = dforderitems.drop(columns=['attributes'])

                # Get PR_Mobile_Customer_Number__c
                dforderitems = pd.concat([dforderitems, pd.DataFrame(dforderitems['Product2'].tolist())], axis=1)
                dforderitems = pd.concat([dforderitems, pd.DataFrame(dforderitems['Order'].tolist())], axis=1)
                dforderitems = pd.concat([dforderitems, pd.DataFrame(dforderitems['vlocity_cmt__DefaultBillingAccountId__r'].tolist())], axis=1)
                drop_cols = [c for c in ['vlocity_cmt__DefaultBillingAccountId__r','Product2','Order','attributes'] if c in dforderitems.columns]
                dforderitems.drop(columns=drop_cols, inplace=True)
                dforderitems = dforderitems.drop(columns=['vlocity_cmt__DefaultBillingAccountId__c'])
                dforderitems = dforderitems.rename(columns={
                    'Id':'orderitem_id',
                    'OrderId':'orderid',
                    'Name':'productname',
                    'Oracle_CRM_External_Id__c' : 'order_id',
                    'vlocity_cmt__OrchestrationPlanId__c' : 'orchestrationplan_id',
                    'PR_Mobile_Billing_Number__c':'ban_can'
                })
                dforderitems.to_csv('log/res_orderitemsuborders.csv', index=False)
            except Exception as e:
                logger.info(f"getorderitembysuborder : {str(e)}")
        else:
            logger.info('Empty |  Get Order Items |')

        logger.info('End |  Get Order Items |')
        return dforderitems
    def readochitems(self, dfsuborder : pd.DataFrame):
        logger.info(f'Start | readochitems method  | {len(dfsuborder)}')
        df = pd.read_csv('log/res_orchitems.csv')
        if len(df) > 0:
            print(f'res_orchitems len: {len(df)}')
            dfsuborderstatus = self.transformochitemsresponse(dfochitems=df)
            dfsuborderstatus.fillna('',inplace=True)
        else:
            logger.info('Empty |  Not found orchestration plan to process |')
            dfsuborderstatus = pd.DataFrame()
        return dfsuborderstatus