"""
USPTO Patent File Wrapper API Client
Based on: https://data.uspto.gov/swagger/index.html
API Documentation: https://catalog.data.gov/dataset/open-data-portal-odp-patent-file-wrapper-pfw-api-search-application-data-continuity-docume

This module provides functions to interact with the USPTO Patent File Wrapper API,
including search, application data, continuity, documents, transactions, and more.

IMPORTANT: An API key is REQUIRED to use this API. To obtain an API key:
1. Create a USPTO.gov account at https://www.uspto.gov/
2. Log in to the API Key Manager at https://account.uspto.gov/api-manager/
3. Request an API key for the Patent File Wrapper API service
"""

import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode


class USPTOAPIError(Exception):
    """Custom exception for USPTO API errors."""
    pass


class MissingAPIKeyError(USPTOAPIError):
    """Exception raised when API key is missing."""
    pass


class USPTOPatentAPI:
    """Client for USPTO Patent File Wrapper API."""
    
    BASE_URL = "https://data.uspto.gov/apis/patent-file-wrapper"
    
    def __init__(self, api_key: Optional[str] = None, require_api_key: bool = True):
        """
        Initialize the USPTO Patent API client.
        
        Args:
            api_key: API key for authentication (REQUIRED for USPTO API)
            require_api_key: If True, raises error when API key is missing. 
                           If False, allows initialization but will fail on API calls.
                           
        Raises:
            MissingAPIKeyError: If require_api_key is True and api_key is None or empty
            
        Note:
            An API key is REQUIRED to use the USPTO Patent File Wrapper API.
            Get your API key at: https://account.uspto.gov/api-manager/
        """
        if require_api_key and (not api_key or not api_key.strip()):
            raise MissingAPIKeyError(
                "API key is required to use the USPTO Patent File Wrapper API.\n"
                "To obtain an API key:\n"
                "1. Create a USPTO.gov account at https://www.uspto.gov/\n"
                "2. Log in to the API Key Manager at https://account.uspto.gov/api-manager/\n"
                "3. Request an API key for the Patent File Wrapper API service\n"
                "Then initialize with: USPTOPatentAPI(api_key='your-api-key')"
            )
        
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            # USPTO API typically uses X-API-Key header, but may also use other methods
            self.session.headers.update({"X-API-Key": api_key})
            # Alternative: Some APIs use Authorization header
            # self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Make a request to the API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            
        Returns:
            JSON response as dictionary
            
        Raises:
            MissingAPIKeyError: If API key is missing
            USPTOAPIError: If the API request fails
            requests.RequestException: If the HTTP request fails
        """
        # Validate API key before making request
        if not self.api_key or not self.api_key.strip():
            raise MissingAPIKeyError(
                "API key is required to make API requests.\n"
                "Get your API key at: https://account.uspto.gov/api-manager/\n"
                "Then initialize with: USPTOPatentAPI(api_key='your-api-key')"
            )
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            else:
                response = self.session.request(method, url, json=params)
            
            response.raise_for_status()
            
            # Handle different response types
            try:
                return response.json()
            except ValueError:
                # If response is not JSON, return text
                return {"content": response.text, "status_code": response.status_code}
                
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors
            if e.response.status_code == 401:
                raise USPTOAPIError(
                    f"Authentication failed. Please check your API key.\n"
                    f"Status: {e.response.status_code}\n"
                    f"Response: {e.response.text}"
                )
            elif e.response.status_code == 403:
                raise USPTOAPIError(
                    f"Access forbidden. Your API key may not have permission for this endpoint.\n"
                    f"Status: {e.response.status_code}\n"
                    f"Response: {e.response.text}"
                )
            elif e.response.status_code == 429:
                raise USPTOAPIError(
                    f"Rate limit exceeded. Please wait before making more requests.\n"
                    f"Status: {e.response.status_code}"
                )
            else:
                raise USPTOAPIError(
                    f"API request failed with status {e.response.status_code}.\n"
                    f"Response: {e.response.text}"
                )
        except requests.exceptions.RequestException as e:
            raise USPTOAPIError(f"Network error: {str(e)}")
    
    def search_patents(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Conduct a search of all patent application bibliographic/front page 
        and patent relevant data fields.
        
        This endpoint searches across multiple patents or applications.
        You can use multiple search terms, such as "Patented AND Abandoned".
        You can use any combination of the 100+ data attributes available.
        
        Args:
            query: Search query string (e.g., "Utility", "Patented AND Abandoned")
            filters: Additional filters as dictionary
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            
        Returns:
            Dictionary containing search results
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> results = api.search_patents("Utility", limit=10)
        """
        params = {"q": query}
        
        if filters:
            params.update(filters)
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        
        return self._make_request("search", params=params)
    
    def get_application_data(self, application_number: str) -> Dict[str, Any]:
        """
        Get key bibliographic information found on the front page of granted 
        patents and published patent applications.
        
        Use this endpoint when you want application data for a specific patent 
        application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing application data
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> data = api.get_application_data("12345678")
        """
        return self._make_request(
            "application-data",
            params={"applicationNumber": application_number}
        )
    
    def get_continuity_data(self, application_number: str) -> Dict[str, Any]:
        """
        Get continuity details for the patent, including parent and/or child 
        continuity data.
        
        Continuity Data includes Parent Continuity Data and Child Continuity Data.
        Use this endpoint when you want continuity data for a specific patent 
        application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing continuity data
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> continuity = api.get_continuity_data("12345678")
        """
        return self._make_request(
            "continuity",
            params={"applicationNumber": application_number}
        )
    
    def get_documents(
        self, 
        application_number: str,
        document_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get details on documents attached to the patent application, as well as 
        options for downloading the documents.
        
        This includes documents under all codes (Examiner's Amendment Communication, 
        Printer Rush, IDS Filed, Application is Now Complete, PTA 36 months).
        Use this endpoint when you want documents related to a specific patent 
        application whose application number you know.
        
        Args:
            application_number: The patent application number
            document_code: Optional filter by document code
            
        Returns:
            Dictionary containing document information and download options
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> documents = api.get_documents("12345678")
        """
        params = {"applicationNumber": application_number}
        if document_code:
            params["documentCode"] = document_code
        
        return self._make_request("documents", params=params)
    
    def download_document(
        self, 
        application_number: str,
        document_id: str,
        save_path: Optional[str] = None
    ) -> bytes:
        """
        Download a specific document from a patent application.
        
        Args:
            application_number: The patent application number
            document_id: The document ID to download
            save_path: Optional path to save the file. If None, returns bytes.
            
        Returns:
            Document content as bytes (if save_path is None)
            
        Raises:
            MissingAPIKeyError: If API key is missing
            USPTOAPIError: If the download fails
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-api-key")
            >>> content = api.download_document("12345678", "doc123")
        """
        # Validate API key
        if not self.api_key or not self.api_key.strip():
            raise MissingAPIKeyError(
                "API key is required to download documents.\n"
                "Get your API key at: https://account.uspto.gov/api-manager/"
            )
        
        # This endpoint structure may need adjustment based on actual API
        try:
            response = self.session.get(
                f"{self.BASE_URL}/documents/{application_number}/{document_id}/download"
            )
            response.raise_for_status()
            
            content = response.content
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(content)
            
            return content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise USPTOAPIError(
                    f"Authentication failed. Please check your API key.\n"
                    f"Status: {e.response.status_code}"
                )
            raise USPTOAPIError(f"Failed to download document: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise USPTOAPIError(f"Network error while downloading: {str(e)}")
    
    def get_transactions(
        self, 
        application_number: str,
        transaction_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get additional information concerning the transaction activity that has 
        occurred for each patent application.
        
        This includes details on the date of the transaction, code (Examiner's 
        Amendment Communication, Printer Rush, IDS Filed, Application is Now 
        Complete, PTA 36 months), and transaction description.
        Use this endpoint when you want transaction data related to a specific 
        patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            transaction_code: Optional filter by transaction code
            
        Returns:
            Dictionary containing transaction data
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> transactions = api.get_transactions("12345678")
        """
        params = {"applicationNumber": application_number}
        if transaction_code:
            params["transactionCode"] = transaction_code
        
        return self._make_request("transactions", params=params)
    
    def get_patent_term_adjustment(self, application_number: str) -> Dict[str, Any]:
        """
        Get additional information concerning the patent term adjustment that has 
        occurred for each patent.
        
        Use this endpoint when you want patent term adjustment data related to a 
        specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing patent term adjustment data
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> pta = api.get_patent_term_adjustment("12345678")
        """
        return self._make_request(
            "patent-term-adjustment",
            params={"applicationNumber": application_number}
        )
    
    def get_attorney_agent_info(self, application_number: str) -> Dict[str, Any]:
        """
        Get additional information concerning the attorney/agent related to a patent, 
        including the associated attorney/agent's address.
        
        Use this endpoint when you want address and attorney/agent information related 
        to a specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing attorney/agent information and address
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> attorney_info = api.get_attorney_agent_info("12345678")
        """
        return self._make_request(
            "attorney-agent",
            params={"applicationNumber": application_number}
        )
    
    def get_assignments(self, application_number: str) -> Dict[str, Any]:
        """
        Get additional information concerning the assignments of each patent.
        
        Use this endpoint when you want assignments data related to a specific 
        patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing assignment/ownership information
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> assignments = api.get_assignments("12345678")
        """
        return self._make_request(
            "assignments",
            params={"applicationNumber": application_number}
        )
    
    def get_foreign_priority(self, application_number: str) -> Dict[str, Any]:
        """
        Get additional information concerning the foreign priority related to each patent.
        
        Use this endpoint when you want foreign priority information related to a 
        specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing foreign priority information
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> foreign_priority = api.get_foreign_priority("12345678")
        """
        return self._make_request(
            "foreign-priority",
            params={"applicationNumber": application_number}
        )
    
    def get_complete_patent_info(self, application_number: str) -> Dict[str, Any]:
        """
        Get all available information for a patent application by combining 
        multiple endpoints.
        
        This is a convenience method that fetches:
        - Application data
        - Continuity data
        - Documents
        - Transactions
        - Patent term adjustment
        - Attorney/agent information
        - Assignments
        - Foreign priority
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing all patent information
            
        Example:
            >>> api = USPTOPatentAPI()
            >>> complete_info = api.get_complete_patent_info("12345678")
        """
        return {
            "application_data": self.get_application_data(application_number),
            "continuity": self.get_continuity_data(application_number),
            "documents": self.get_documents(application_number),
            "transactions": self.get_transactions(application_number),
            "patent_term_adjustment": self.get_patent_term_adjustment(application_number),
            "attorney_agent": self.get_attorney_agent_info(application_number),
            "assignments": self.get_assignments(application_number),
            "foreign_priority": self.get_foreign_priority(application_number)
        }


# Convenience functions for direct usage without instantiating the class
def search_patents(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to search patents without instantiating the class.
    
    Args:
        query: Search query string
        filters: Additional filters as dictionary
        limit: Maximum number of results to return
        offset: Number of results to skip
        api_key: API key (REQUIRED - get at https://account.uspto.gov/api-manager/)
        
    Returns:
        Dictionary containing search results
        
    Raises:
        MissingAPIKeyError: If API key is not provided
        
    Example:
        >>> results = search_patents("Utility", api_key="your-api-key", limit=10)
    """
    if not api_key:
        raise MissingAPIKeyError(
            "API key is required. Get your API key at: https://account.uspto.gov/api-manager/"
        )
    api = USPTOPatentAPI(api_key=api_key)
    return api.search_patents(query, filters, limit, offset)


def get_patent_application_data(
    application_number: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to get application data without instantiating the class.
    
    Args:
        application_number: The patent application number
        api_key: API key (REQUIRED - get at https://account.uspto.gov/api-manager/)
        
    Returns:
        Dictionary containing application data
        
    Raises:
        MissingAPIKeyError: If API key is not provided
        
    Example:
        >>> data = get_patent_application_data("12345678", api_key="your-api-key")
    """
    if not api_key:
        raise MissingAPIKeyError(
            "API key is required. Get your API key at: https://account.uspto.gov/api-manager/"
        )
    api = USPTOPatentAPI(api_key=api_key)
    return api.get_application_data(application_number)

