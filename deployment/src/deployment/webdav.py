from deployment import extract_url_components
from webdav4.fsspec import WebdavFileSystem

def init_file_system(data_url: str) -> WebdavFileSystem:
    """
    Initialize the WebDAV file system with the provided data URL.
    """
    domain, share_id = extract_url_components(data_url)
    return WebdavFileSystem(
        f"https://{domain}/public.php/webdav", 
        auth=(share_id, ""),
        chunk_size=1024 * 1024 * 10,  # 10 MB
        timeout=20,  # seconds
    )