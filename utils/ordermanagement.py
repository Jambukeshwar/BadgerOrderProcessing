#import logging
import uuid
from schemas.orderpayload import Offer, ChildProduct,OrderPayload
from utils.orchesmanagement import OrchesManagement
import ast
import pandas as pd
import json
from utils.logger import Logger

#logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s',
#                    datefmt='%Y-%m-%d %H:%M:%S',
#                    level=logging.INFO)
#logger = logging.getLogger(__name__)

logger = Logger().get_logger()

class OrderManagement(object):
    def __init__(self) -> None:
        pass

    """ Get Master Orders by Business Accounts"""
    def getmasterorders(self,dforder) -> pd.DataFrame:
        # Group order for generate Business Account by Orders for Generate Master Order
        dfbusiness = dforder.groupby(['ParentId_x','order_id']).size().reset_index(name='Count')
        dfbusiness = dfbusiness.sort_values(by='Count', ascending=True)
        #Guid for each transaccion generate by Engine

        totalmasterorder = len(dfbusiness)
        uniqueid = str(uuid.uuid4())
        logger.info(f'TransactionId: {uniqueid} | Total Master Orders : {str(totalmasterorder)}')
        return dfbusiness

    def productfilters(self, item):
        if pd.isnull(item['product_attributes']):
            filtered_product_attributes={}
        else:
            try:#jfrc
               #print(f"product_attributes:Encontro campos para actualizar: {item['product_attributes']}" )
               product_attributes = ast.literal_eval(item['product_attributes'].replace("'", "\""))
               filtered_product_attributes_null = {key: value for key, value in product_attributes.items() if (value != "NULL")}
               filtered_product_attributes_empty = {key: value for key, value in filtered_product_attributes_null.items() if (value != "")}
               filtered_product_attributes = {key: value for key, value in filtered_product_attributes_empty.items() if (value != "null")}
            except Exception as e: #jfrc
               logger.exception(f'Fail | Json Attributes | {str(e)} | ')
               raise Exception(f'Fail | Json Attributes | {str(e)} | ')
        return filtered_product_attributes
    
    def fields_to_update(self, item):
        if pd.isnull(item['fieldstoupdate']):
            filtered_product_fields={}
        else:
            try:#jfrc
                product_attributes = ast.literal_eval(item['fieldstoupdate'].replace("'", "\""))
                filtered_product_fields_null = {key: value for key, value in product_attributes.items() if (value != "NULL")}
                filtered_product_fields_empty = {key: value for key, value in filtered_product_fields_null.items() if (value != "")}
                filtered_product_fields = {key: value for key, value in filtered_product_fields_empty.items() if (value != "null")}
            except Exception as e: #jfrc
                logger.exception(f'Fail | Json fields | {str(e)} | ')
                raise Exception(f'Fail | Json fields | {str(e)} | ')
        return filtered_product_fields

    """ Generate Payload for Master Order and Sub order with Order Item file """
    def payloadbybusiness(self, dforder, business, uniqueid) -> dict:
        dforder=dforder.loc[dforder['Product2Id'].notnull()] #jfrc
        dforder[['parent', 'child']] = dforder['vlocity_cmt__linenumber__c'].astype(str).str.split('.', n=1, expand=True)
        dfgroupsuborder = dforder.loc[dforder['ParentId_x'] == business['ParentId_x']].groupby(['ParentId_x','subsrptn_id']).size().reset_index(name='Count')
        logger.info(f' Total Sub Orders : {str(len(dfgroupsuborder))}')
        list_suborders = list()
        if len(dfgroupsuborder) > 0:
            for _, suborder in dfgroupsuborder.iterrows():
                print(suborder)
                for _, parent in dforder.loc[(dforder['child'] == '0') & (dforder['subsrptn_id'] == suborder['subsrptn_id']) ].iterrows():
                    print(suborder)
                    offer = Offer()
                    offer.PR_Trace_Number = uniqueid
                    offer.itemId = parent['PricebookEntryId']
                    colOracleExternal = 'subsrptn_id'
                    offer.Oracle_CRM_External_Id = (f'{parent[colOracleExternal]}')
                    offer.product2id = parent['Product2Id']
                    offer.vlocity_cmtbillingaccountid = parent['Id'] # Billing Account
                    offer.vlocity_cmtserviceaccountid = parent['id'] # Service Account
                    colFan = 'FAN_Number__c_y'
                    offer.FAN_Number__c = (f'{parent[colFan]}') # PROBAR
                    offer.attributesToUpdate = self.productfilters(parent)
                    #for assets its necesary add billing accountid
                    filtered_product_fields = self.fields_to_update(parent)
                    filtered_product_fields["vlocity_cmt__BillingAccountId__c"] = parent['Id']
                    offer.fieldsToUpdate = filtered_product_fields
                    #offer.fieldsToUpdate = self.fields_to_update(parent)
                    for _, child in dforder.loc[
                        (dforder['parent'] == parent['parent']) &
                        (dforder['child'] != '0') &
                        (dforder['subsrptn_id'] == suborder['subsrptn_id'])].iterrows():
                        childproduct = ChildProduct()
                        filtered_product_attributes = self.productfilters(child)
                        #for assets its necesary add billing accountid
                        filtered_product_fields_c = self.fields_to_update(child)
                        filtered_product_fields_c["vlocity_cmt__BillingAccountId__c"] = parent['Id']
                        filtered_product_fields = filtered_product_fields_c
                        #filtered_product_fields = self.fields_to_update(child)
                        #print(f'#####-en el child tiene: {filtered_product_fields}')
                        if pd.notnull(filtered_product_attributes) or pd.notnull(filtered_product_fields):
                            childproduct.product2id = child['Product2Id']
                            if len(filtered_product_fields) > 0:    
                                childproduct.fieldsToUpdate = filtered_product_fields
                            else:    
                                childproduct.fieldsToUpdate = {}
                                
                            if len(filtered_product_attributes) > 0:
                                childproduct.attributesToUpdate = filtered_product_attributes
                                offer.childProducts.append(childproduct)

                    list_suborders.append(offer)
            orderpayload = OrderPayload()
            orderpayload.orderName = f'OrderMasterName - {business["ParentId_x"]}'
            orderpayload.account = business['ParentId_x']
            orderpayload.offers = list_suborders
            orderpayload_dict = orderpayload.dict()
            orderpayload_strjson = json.dumps(orderpayload_dict, indent=4)
            #logger.info(orderpayload_strjson)
        return orderpayload_dict

    def getorderitem(self, dict_item) -> list:
        response = []
        last_dict = dict_item.popitem()
        business = dict_item.popitem()
        try:
            for key,value in dict_item.items():
                if key == 'MasterOrder':
                    #print(f'getorderitem-->: | {value} | --order-id-->: | {last_dict[1]} | --business-->: | {business[1]}')                
                    master_order = value
                    order_id = last_dict[1]
                    business_id = business[1]
                else:
                    #print(f'getorderitem Else-->: | {value} | --master_order-->: | {master_order} | --order_id-->: | {order_id} | --busines-->: | {business_id}')                
                    item = {
                        'MasterOrder' : master_order,
                        'order_id' : order_id,
                        'business_id' : business_id,
                        'subsrptn_id' : key,
                        'suborder_id' : value
                    }
                    response.append(item)
        except Exception as e:
            logger.exception(f'Fail | getorderitem dict_item:- {dict_item} | {str(e)} | ')
        return response

    def generateorderitemresponse(self, dict_result) -> str:
        """ Generate from PostCart Item Salesforce Response

        Args:
            dict_result (dict): dict response from Rest Salesforce

        Returns:
            str: Name of file
        """
        response = []
        if isinstance(dict_result, list):
            for dict_item in dict_result:
                res = self.getorderitem(dict_item=dict_item)
                response.append(res)
            flattened_data = [item for sublist in response for item in sublist]
            dfdata = pd.DataFrame(flattened_data)
        else:
            response = self.getorderitem(dict_item=dict_result)
            dfdata = pd.DataFrame(response)

        #print(response)
        #dfdata['status'] = 'new'
        suborderfile = f'log/res_suborders.csv'
        dfdata.to_csv(suborderfile, index=False)
        return suborderfile
    