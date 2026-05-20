from typing import List
from pydantic import BaseModel

class ProcessLog(BaseModel):
    entity : str 
    startdate : str 
    enddate : str
    s3sourcefile : str 
    processtime : int 
    
    
