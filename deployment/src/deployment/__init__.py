from typing import Optional
from urllib.parse import urlparse
import numpy as np
import pandas as pd

def get_data(data_url: str) -> pd.DataFrame:
    """
    TODO: Move to deployment.utils or similar
    
    Function to download data from a public URL and return it as a pandas DataFrame.
    
    NOTE: Do not parse dates to avoid xcom serialization issues. Needs to be 
          done within each task.
    """
    # Read the CSV file from the URL
    df = pd.read_csv(data_url, index_col=0)
    
    return df

def extract_url_components(url: str) -> tuple[str, str]:
    # TODO: Move to deployment.utils or similar
    
    domain = urlparse(url).netloc
    share_id = urlparse(url).path.split('/')[-1]
    
    return domain, share_id

def build_file_url(
    file_id: str, 
    ext: str, 
    url: Optional[str] = None, 
    domain: Optional[str] = None, 
    share_id: Optional[str] = None
) -> str:
    """
    TODO: Move to deployment.utils or similar
    
    Builds a URL for accessing a file on a webdav server.
    If a full URL is provided, it extracts the domain and share_id from it.
    If only domain and share_id are provided, it constructs the URL accordingly.
    If share_id is None, it assumes the file is being uploaded to webdav.
    """
    
    assert (url is not None) or (domain is not None), \
        "Either a full URL or both domain and share_id must be provided."
    if url is not None:
        domain, share_id = extract_url_components(url)
        
    if share_id is None: # When uploading to webdav
        return f"https://{domain}/public.php/webdav/{file_id}.{ext}"
    else: # When downloading from webdav
        return f"https://{domain}/public.php/dav/files/{share_id}/{file_id}.{ext}"

