from flask import Flask, request, jsonify
import os
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
    start_index = string.find(start) + len(start)
    end_index = string.find(end, start_index)
    return string[start_index:end_index]


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
                    return None

                request_url = str(response1.url)
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
                        return None

                    if response_data2['list'][0]['isdir'] == "1":
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
                                return None
                            return response_data3['list']
                    
                    return response_data2['list']
    except aiohttp.ClientResponseError as e:
        print(f"Error fetching download link: {e}")
        return None


def extract_thumbnail_dimensions(url: str) -> str:
    """Extract dimensions from thumbnail URL's size parameter"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    size_param = params.get('size', [''])[0]
    
    # Extract numbers from size format like c360_u270
    if size_param:
        parts = size_param.replace('c', '').split('_u')
        if len(parts) == 2:
            return f"{parts[0]}x{parts[1]}"
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
        print(f"Error getting formatted size: {e}")
        return None


async def format_message(link_data):
    """Format file data with thumbnails"""
    thumbnails = {}
    if 'thumbs' in link_data:
        for key, url in link_data['thumbs'].items():
            if url:  # Skip empty URLs
                dimensions = extract_thumbnail_dimensions(url)
                thumbnails[dimensions] = url
    
    file_name = link_data["server_filename"]
    file_size = await get_formatted_size_async(link_data["size"])
    download_link = link_data["dlink"]
    
    sk = {
        'Title': file_name,
        'Size': file_size,
        'Direct Download Link': download_link,
        'Thumbnails': thumbnails
    }
    return sk


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
                    return None

                request_url = str(response1.url)
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
                        return None

                    files = response_data2['list']

                    # If it's a directory, fetch contents
                    if files[0]['isdir'] == "1":
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
                                return None
                            files = response_data3['list']

                    # Fetch direct download links for each file
                    file_data = []
                    for file in files:
                        async with session.head(file["dlink"], headers=headers) as direct_link_response:
                            direct_download_url = direct_link_response.headers.get("location")

                        file_info = {
                            "file_name": file.get("server_filename"),
                            "link": file.get("dlink"),
                            "direct_link": direct_download_url,  # Extracted direct download link
                            "thumb": file.get("thumbs", {}).get("url3", "https://default_thumbnail.png"),
                            "size": await get_formatted_size_async(file.get("size", 0)),
                            "sizebytes": file.get("size", 0),
                        }
                        file_data.append(file_info)

                    return file_data

    except aiohttp.ClientResponseError as e:
        print(f"Error fetching download link: {e}")
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
    try:
        url = request.args.get('url', 'No URL Provided')
        logging.info(f"Received request for URL: {url}")
        link_data = await fetch_download_link_async(url)
        
        if link_data:
            tasks = [format_message(item) for item in link_data]
            formatted_message = await asyncio.gather(*tasks)
            logging.info(f"Formatted message: {formatted_message}")
        else:
            formatted_message = None
        
        response = {
            'ShortLink': url,
            'Extracted Info': formatted_message,
            'status': 'success'
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({'status': 'error', 'message': str(e), 'Link': url})


@app.route(rule='/api2', methods=['GET'])
async def Api2():
    """API v2 - Extract TeraBox file info with direct download links"""
    try:
        url = request.args.get('url', 'No URL Provided')
        logging.info(f"Received request for URL: {url}")

        link_data = await fetch_download_link_async2(url)

        if link_data:
            response = {
                'ShortLink': url,
                'Extracted Files': link_data,
                'status': 'success'
            }
        else:
            response = {
                'status': 'error',
                'message': 'No files found',
                'ShortLink': url
            }

        return jsonify(response)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({'status': 'error', 'message': str(e), 'Link': url})


@app.route(rule='/help', methods=['GET'])
async def help():
    """Help endpoint - API usage documentation"""
    try:
        response = {
            'Info': "There is Only one Way to Use This as Show Below",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Example2': 'https://teraboxx.vercel.app/api2?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA'
        }
        return jsonify(response)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        response = {
            'Info': "There is Only one Way to Use This as Show Below",
            'Example': 'https://teraboxx.vercel.app/api?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA',
            'Example2': 'https://teraboxx.vercel.app/api2?url=https://terafileshare.com/s/1_1SzMvaPkqZ-yWokFCrKyA'
        }
        return jsonify(response)


# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
