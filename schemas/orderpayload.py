from pydantic import BaseModel, Field
from typing import List, Optional

class ChildProduct(BaseModel):
    fieldsToUpdate : Optional[dict] = None
    attributesToUpdate : Optional[dict] = None
    product2id : Optional[str] = None
    
class Offer(BaseModel):
    PR_Trace_Number : Optional[str] = None
    vlocity_cmtserviceaccountid : Optional[str] = None 
    vlocity_cmtbillingaccountid : Optional[str] = None 
    product2id : Optional[str] = None 
    itemId : Optional[str] = None 
    Oracle_CRM_External_Id : Optional[str] = None 
    FAN_Number__c : Optional[str] = None 
    fieldsToUpdate : Optional[dict] = None
    attributesToUpdate : Optional[dict] = None 
    childProducts : List[ChildProduct] = Field(default=[])
    

class OrderPayload(BaseModel):
    offers : List[Offer] = Field(default=[])
    account : Optional[str] = None
    orderName : Optional[str] = None 