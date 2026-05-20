from pydantic import BaseModel
from typing import List, Optional

# recibe lo que se manda del postman
class S3Files(BaseModel): 
    entity : str 
    filename : str
    sourcepath : str
    targetpath : str 
    logpath : str
    errorpath : str 

class MigrationSetting(BaseModel):
    optionload :str 
    bucketname : str 
    mitobasepath : str
    sfenvironment:str
    awsenvironment:str 
    s3files : List[S3Files]
    #otherenv: Optional[SFOtherEnvironmenth] = None
    
    """class SFOtherEnvironmenth(BaseModel): 
    awskey : str 
    awstoken : str
    sfuser : str
    sfpassword : str 
    sfenvironment : str  
"""    
