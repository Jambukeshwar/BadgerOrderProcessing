from pydantic import BaseModel
from typing import List

class s3File(BaseModel):
    keyFileName: str
    pathFile   : str
    fileName   : str
    pathresponse: str


class s3Setting(BaseModel):
    awsAccessKey : str
    awsSecretKey : str 
    awsRegion    : str
    awsToken     : str
    bucketname   : str
    s3files      : List[s3File]


