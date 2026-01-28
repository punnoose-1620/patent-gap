from bs4 import BeautifulSoup
import requests

def check_content_for_runtime_errors(plain_string_content):
    if not isinstance(plain_string_content, str):
        return True # Consider non-string input as an error state or invalid content

    content_lower = plain_string_content.lower()
    error_keywords = [
        "404", "not found", "page not found", "error 404", "site not found",
        "broken link", "internal server error", "500 error", "forbidden", "access denied"
    ]

    for keyword in error_keywords:
        if keyword in content_lower:
            return True, keyword
    return False, None

def convertHtmlToString(content):
    if not isinstance(content, str):
        return ""
    soup = BeautifulSoup(content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def check_content_for_runtime_errors(plain_string_content):
    if not isinstance(plain_string_content, str):
        return True # Consider non-string input as an error state or invalid content

    content_lower = plain_string_content.lower()
    error_keywords = [
        "404", "not found", "page not found", "error 404", "site not found",
        "broken link", "internal server error", "500 error", "forbidden", "access denied"
    ]

    for keyword in error_keywords:
        if keyword in content_lower:
            return True, keyword
    return False, None

def get_content(url:str):
    try:
        response = requests.get(url, timeout=10) # Added a timeout
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        content_type = response.headers.get('Content-Type')
        body = response.text

        if (content_type is not None) and ('html' in str(content_type).lower()):
            convertedBody = html_to_string(body)
            content_type = 'Text'

            runTimeError, errorKeyword = check_content_for_runtime_errors(convertedBody)
            if(runTimeError):
                return None, None, 'Runtime Error : ' + str(errorKeyword)
            return content_type, convertedBody, None
        return content_type, body, None
    except requests.exceptions.HTTPError as http_err:
        return None, None, 'HTTP Error : ' + str(http_err)
    except requests.exceptions.ConnectionError as conn_err:
        return None, None, 'Connection Error : ' + str(conn_err)
    except requests.exceptions.Timeout as timeout_err:
        return None, None, 'Timeout Error : '+ str(timeout_err)
    except requests.exceptions.RequestException as req_err:
        return None, None, 'Request Error : '+ str(req_err)
    except Exception as e:
        return None, None, 'Unexpected Error : '+ str(e)

def parse_urls(urls:list[str]):
    contents = []
    for url in urls:
        content_type, body, error = get_content(url)
        if (error is not None):
            print("ERROR: Fetching Patent from url: ", url, "\nError: ", error, "\n\n")
        else:
            if('html' in str(content_type).lower()):
                convertedBody = html_to_string(body)
                contents.append(convertedBody)
            else:
                contents.append(body)
## Test