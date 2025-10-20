from flask import Flask, request, jsonify
import aiohttp
import asyncio
import logging
from urllib.parse import parse_qs, urlparse

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Working Cookies
cookies = {
    'PANWEB': '1',
    '__bid_n': '197112bc411de5993a4207',
    '__stripe_mid': 'a6c0c66c-7539-4870-8522-e7b144b9d478bed8fb',
    'ndus': 'Y2cfn3MteHuiQN6wECay4fagha_iyT7m6UtHN-g9',
    'csrfToken': 'HkaYarrjxKRRVLt7n2GvDlin',
    'browserid': 'yD0VvgPjxgUxkxUuahNSktehNoQuNZMkIH3SWF9GzVgjgKur7tInph-VFw8=',
    'lang': 'en',
    'ndut_fmt': 'F221B11F4DD53955F804D33D6F5EBA57E79A6335A4198A6B700D0816E375AE49',
    '__stripe_sid': 'e6c30455-9f9e-42b0-b7d7-d73f7f41d9c907a34e',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Accept': '*/*',
    'Connection': 'keep-alive',
}


def find_between(string, start, end):
    """Extract substring between start and end markers"""
    try:
        start_index = string.find(start)
        if start_index == -1:
            return ""
        start_index += len(start)
        end_index = string.find(end, start_index)
        if end_index == -1:
            return ""
        return string[start_index:end_index]
    except Exception as e:
        logging.error(f"Error in find_between: {e}")
        return ""


async def fetch_download_link_async(url):
    """Fetch download links for TeraBox files (API version 1)"""
    try:
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            async with session.get(url) as response1:
                response1.raise_for_status()
                response_data = await response1.text()
                js_token = find_between(response_data, 'fn%28%22', '%22%29')
                log_id = find_between(response_data, 'dp-logid=', '&')

                if not js_token or not log_id:
                    logging.error(f"Failed to extract jsToken or logid. jsToken: {js_token}, logid: {log_id}")
                    return None

                request_url = str(response1.url)
                if 'surl=' not in request_url:
                    logging.error(f"No surl found in URL: {request_url}")
                    return None
                    
                surl = request_url.split('surl=')[1]
                params = {
                    'app_id': '250528',
                    'web': '1',
                    'channel': 'dubox',
                    'clienttype': '0',
                    'jsToken': js_token,
                    'dplogid': log_id,
                    'page': '1',
                    'num': '20',
                    'order': 'time',
                    'desc': '1',
                    'site_referer': request_url,
                    'shorturl': surl,
                    'root': '1'
                }

                async with session.get('https://www.1024tera.com/share/list', params=params) as response2:
                    response_data2 = await response2.json()
                    
                    if 'list' not in response_data2:
                        logging.error(f"No 'list' in response: {response_data2}")
                        return None

                    if not response_data2['list']:
                        logging.error("Empty list in response")
                        return None

                    if response_data2['list'][0].get('isdir') == "1":
                        params.update({
                            'dir': response_data2['list'][0]['path'],
                            'order': 'asc',
                            'by': 'name',
                            'dplogid': log_id
                        })
                        params.pop('desc')
                        params.pop('root')

                        async with session.get('https://www.1024tera.com/share/list', params=params) as response3:
                            response_data3 = await response3.json()
                            
                            if 'list' not in response_data3:
                                logging.error(f"No 'list' in directory response: {response_data3}")
                                return None
                            return response_data3['list']
                    
                    return response_data2['list']
    except Exception as e:
        logging.error(f"Error fetching download link: {e}", exc_info=True)
        return None


def extract_thumbnail_dimensions(url: str) -> str:
    """Extract dimensions from thumbnail URL's size parameter"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        size_param = params.get('size', [''])[0]
        
        # Extract numbers from size format like c360_u270
        if size_param:
            parts = size_param.replace('c', '').split('_u')
            if len(parts) == 2:
                return f"{parts[0]}x{parts[1]}"
    except Exception as e:
        logging.error(f"Error extracting thumbnail dimensions: {e}")
    return "original"


async def get_formatted_size_async(size_bytes):
    """Convert bytes to human-readable format"""
    try:
        size_bytes = int(size_bytes)
        size = size_bytes / (1024 * 1024) if size_bytes >= 1024 * 1024 else (
            size_bytes / 1024 if size_bytes >= 1024 else size_bytes
        )
        unit = "MB" if size_bytes >= 1024 * 1024 else ("KB" if size_bytes >= 1024 else "bytes")
        return f"{size:.2f} {unit}"
    except Exception as e:
        logging.error(f"Error getting formatted size: {e}")
        return "0 bytes"


async def format_message(link_data):
    """Format file data with thumbnails"""
    try:
        thumbnails = {}
        if 'thumbs' in link_data and isinstance(link_data['thumbs'], dict):
            for key, url in link_data['thumbs'].items():
                if url:  # Skip empty URLs
                    dimensions = extract_thumbnail_dimensions(url)
                    thumbnails[dimensions] = url
        
        file_name = link_data.get("server_filename", "Unknown")
        file_size = await get_formatted_size_async(link_data.get("size", 0))
        
        # Safe access to dlink - check if it exists
        download_link = link_data.get("dlink")
        if not download_link:
            # Try alternative fields
            download_link = link_data.get("download_url") or link_data.get("url") or link_data.get("path", "N/A")
        
        sk = {
            'Title': file_name,
            'Size': file_size,
            'Direct Download Link': download_link,
            'Thumbnails': thumbnails,
            'fs_id': link_data.get('fs_id')  # Add fs_id for reference
        }
        return sk
    except Exception as e:
        logging.error(f"Error formatting message: {e}", exc_info=True)
        return None


async def fetch_download_link_async2(url):
    """Fetch download links with direct URLs (API version 2)"""
    try:
        async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
            async with session.get(url) as response1:
                response1.raise_for_status()
                response_data = await response1.text()
                
                # Extract jsToken & logid
                js_token = find_between(response_data, 'fn%28%22', '%22%29')
                log_id = find_between(response_data, 'dp-logid=', '&')

                if not js_token or not log_id:
                    logging.error(f"Failed to extract jsToken or logid. jsToken: {js_token}, logid: {log_id}")
                    return None

                request_url = str(response1.url)
                if 'surl=' not in request_url:
                    logging.error(f"No surl found in URL: {request_url}")
                    return None
                    
                surl = request_url.split('surl=')[1]

                params = {
                    'app_id': '250528',
                    'web': '1',
                    'channel': 'dubox',
                    'clienttype': '0',
                    'jsToken': js_token,
                    'dplogid': log_id,
                    'page': '1',
                    'num': '20',
                    'order': 'time',
                    'desc': '1',
                    'site_referer': request_url,
                    'shorturl': surl,
                    'root': '1'
                }

                async with session.get('https://www.1024tera.com/share/list', params=params) as response2:
                    response_data2 = await response2.json()

                    if 'list' not in response_data2:
                        logging.error(f"No 'list' in response: {response_data2}")
                        return None

                    files = response_data2['list']
                    
                    if not files:
                        logging.error("Empty files list")
                        return None

                    # If it's a directory, fetch contents
                    if files[0].get('isdir') == "1":
                        params.update({
                            'dir': files[0]['path'],
                            'order': 'asc',
                            'by': 'name',
                            'dplogid': log_id
                        })
                        params.pop('desc')
                        params.pop('root')

                        async with session.get('https://www.1024tera.com/share/list', params=params) as response3:
                            response_data3 = await response3.json()
                            if 'list' not in response_data3:
                                logging.error(f"No 'list' in directory response: {response_data3}")
                                return None
                            files = response_data3['list']

                    # Fetch direct download links for each file
                    file_data = []
                    for file in files:
                        # Safe access to dlink field
                        dlink = file.get("dlink")
                        
                        if not dlink:
                            # Log and try alternative fields
                            logging.warning(f"No dlink for file: {file.get('server_filename', 'unknown')}")
                            dlink = file.get("download_url") or file.get("url") or file.get("path")
                        
                        direct_download_url = None
                        if dlink:
                            try:
                                async with session.head(dlink, headers=headers, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10)) as direct_link_response:
                                    direct_download_url = direct_link_response.headers.get("location")
                                    if not direct_download_url:
                                        direct_download_url = dlink
                            except Exception as e:
                                logging.error(f"Error fetching direct link: {e}")
                                direct_download_url = dlink
                        else:
                            logging.warning(f"No download link available for {file.get('server_filename', 'unknown')}")

                        # Safe thumbnail access
                        thumb = None
                        if isinstance(file.get("thumbs"), dict):
                            thumb = file.get("thumbs", {}).get("url3")
                        
                        if not thumb:
                            thumb = "https://default_thumbnail.png"

                        file_info = {
                            "file_name": file.get("server_filename", "Unknown"),
                            "link": dlink,
                            "direct_link": direct_download_url,
                            "thumb": thumb,
                            "size": await get_formatted_size_async(file.get("size", 0)),
                            "sizebytes": file.get("size", 0),
                            "fs_id": file.get("fs_id"),
                            "path": file.get("path")
                        }
                        file_data.append(file_info)

                    return file_data

    except Exception as e:
        logging.error(f"Error in fetch_download_link_async2: {e}", exc_info=True)
        return None


@app.route('/')
def hello_world():
    """Root endpoint - API status"""
    response = {
        'status': 'success',
        'message': 'Working Fully',
        'Contact': '@GuyXD'
    }
    return jsonify(response)


@app.route(rule='/api', methods=['GET'])
async def Api():
    """API v1 - Extract TeraBox file info with thumbnails"""
    url = request.args.get('url', 'No URL Provided')
    try:
        logging.info(f"Received request for URL: {url}")
        link_data = await fetch_download_link_async(url)
        
        if link_data:
            tasks = [format_message(item) for item in link_data]
            formatted_message = await asyncio.gather(*tasks)
            # Filter out None values
            formatted_message = [msg for msg in formatted_message if msg is not None]
            logging.info(f"Formatted message count: {len(formatted_message)}")
        else:
            formatted_message = None
        
        response = {
            'ShortLink': url,
            'Extracted Info': formatted_message,
            'status': 'success' if formatted_message else 'error',
            'message': 'Data extracted successfully' if formatted_message else 'Failed to extract data'
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred in /api: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e), 'Link': url})


@app.route(rule='/api2', methods=['GET'])
async def Api2():
    """API v2 - Extract TeraBox file info with direct download links"""
    url = request.args.get('url', 'No URL Provided')
    try:
        logging.info(f"Received request for URL: {url}")

        link_data = await fetch_download_link_async2(url)

        if link_data:
            response = {
                'ShortLink': url,
                'Extracted Files': link_data,
                'status': 'success',
                'message': 'Data extracted successfully'
            }
        else:
            response = {
                'status': 'error',
                'message': 'No files found or API structure changed',
                'ShortLink': url
            }

        return jsonify(response)

    except Exception as e:
        logging.error(f"An error occurred in /api2: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e), 'Link': url})


@app.route(rule='/help', methods=['GET'])
def help():
    """Help endpoint - API usage documentation"""
    try:
        response = {
            'Info': "There is Only one Way to Use This as Show Below",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Example2': 'https://teraboxx.vercel.app/api2?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Note': 'If you get errors, the TeraBox API structure may have changed. Check logs for details.'
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred in /help: {e}")
        response = {
            'Info': "There is Only one Way to Use This as Show Below",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Example2': 'https://teraboxx.vercel.app/api2?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA'
        }
        return jsonify(response)


# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
