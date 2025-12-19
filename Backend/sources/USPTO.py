"""
USPTO Patent File Wrapper API Client
Based on: https://data.uspto.gov/swagger/index.html
API Documentation: https://developer.uspto.gov/api-catalog

This module provides functions to interact with the USPTO Open Data Portal (ODP) API,
including search, application data, continuity, documents, transactions, and more.

IMPORTANT: An API key is REQUIRED to use this API. To obtain an API key:
1. Create a USPTO.gov account at https://www.uspto.gov/
2. Log in to the API Key Manager at https://account.uspto.gov/api-manager/
3. Request an API key for the Patent File Wrapper API service

API Base URL: https://api.uspto.gov/api/v1
Authentication: X-API-KEY header
"""
import json
import requests
from datetime import datetime
from typing import Dict, Optional, Any

class USPTOAPIError(Exception):
    """Custom exception for USPTO API errors."""
    pass


class MissingAPIKeyError(USPTOAPIError):
    """Exception raised when API key is missing."""
    pass


class USPTOPatentAPI:
    """Client for USPTO Open Data Portal (ODP) Patent API."""
    
    BASE_URL = "https://api.uspto.gov/api/v1"

    def processAddress(self, address: dict) -> dict:
        """
        Process an address dictionary into a formatted string.
        """
        address['addressLineText'] = ''
        if 'nameLineOneText' in address.keys():
            address['addressLineText'] = address.pop('nameLineOneText', '')
        if 'nameLineTwoText' in address.keys():
            if address['addressLineText'] != '':
                address['addressLineText'] = address['addressLineText'] + ',' + address.pop('nameLineTwoText', '')
            else:
                address['addressLineText'] = address.pop('nameLineTwoText', '')
        address['addressLineText'] = address['addressLineText'].strip()
        return address
    
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
            # USPTO API uses X-API-KEY header (case-insensitive, but using exact format from docs)
            self.session.headers.update({"X-API-KEY": api_key})
    
    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Make a request to the API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters (for GET requests)
            json_data: JSON body data (for POST requests)
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
            elif method.upper() == "POST":
                response = self.session.post(url, json=json_data, params=params)
            else:
                response = self.session.request(method, url, json=json_data, params=params)
            
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
        query: str = None,
        search_request: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        use_post: bool = False
    ) -> Dict[str, Any]:
        """
        Search patent applications by supplying query parameter or JSON request.
        
        This endpoint searches across multiple patents or applications.
        You can use multiple search terms, such as "Patented AND Abandoned".
        You can use any combination of the 100+ data attributes available.
        
        Args:
            query: Search query string (e.g., "Utility", "Patented AND Abandoned")
                  For GET requests, this becomes the 'q' parameter
            search_request: Full search request dictionary for POST requests.
                          If provided, this takes precedence over query parameter.
                          Example: {"q": "applicationMetaData.applicationTypeLabelName:Utility"}
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)
            use_post: If True, uses POST with JSON body. If False, uses GET with query params.
            
        Returns:
            Dictionary containing search results
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> # GET request
            >>> results = api.search_patents("Utility", limit=10)
            >>> # POST request
            >>> results = api.search_patents(search_request={"q": "applicationMetaData.applicationTypeLabelName:Utility"}, use_post=True)
        """
        endpoint = "patent/applications/search"
        
        if use_post or search_request:
            # Use POST with JSON body
            if search_request:
                json_data = search_request
            else:
                json_data = {}
                if query:
                    json_data["q"] = query
                if limit:
                    json_data["limit"] = limit
                if offset:
                    json_data["offset"] = offset
            
            return self._make_request(endpoint, json_data=json_data, method="POST")
        else:
            # Use GET with query parameters
            params = {}
            if query:
                params["q"] = query
            if limit:
                params["limit"] = limit
            if offset:
                params["offset"] = offset
            
            return self._make_request(endpoint, params=params, method="GET")
    
    def get_application_data(self, application_number: str) -> Dict[str, Any]:
        """
        Get patent application data for a provided application number.
        
        Use this endpoint when you want application data for a specific patent 
        application whose application number you know.
        
        Args:
            application_number: The patent application number (e.g., "14412875")
            
        Returns:
            Dictionary containing application data
            |->count: number
            |->patentFileWrapperDataBag: list of dictionary
            |  |->grantDocumentMetaData: dictionary
            |  |  |->productIdentifier: string
            |  |  |->zipFileName: string
            |  |  |->fileCreateDateTime: datetime (YYYY-MM-DDTHH:MM:SS.ss)
            |  |  |->xmlFileName: string
            |  |  |->fileLocationURI: url as string
            |  |->eventDataBag: list of dictionary
            |  |  |->eventCode: string
            |  |  |->eventDescriptionText: string
            |  |  |->eventDate: date (YYYY-MM-DD)
            |  |->patentTermAdjustmentData: dictionary
            |  |  |->applicantDayDelayQuantity: number
            |  |  |->overlappingDayQuantity: number
            |  |  |->ipOfficeAdjustmentDelayQuantity: number
            |  |  |->cDelayQuantity: number
            |  |  |->adjustmentTotalQuantity: number
            |  |  |->bDelayQuantity: number
            |  |  |->nonOverlappingDayDelayQuantity: number
            |  |  |->aDelayQuantity: number
            |  |  |->patentTermAdjustmentHistoryDataBag: list of dictionary
            |  |  |  |->applicantDayDelayQuantity: number
            |  |  |  |->eventDescriptionText: string
            |  |  |  |->eventSequenceNumber: number with decimals
            |  |  |  |->originatingEventSequenceNumber: number with decimals
            |  |  |  |->ptaPTECode: string
            |  |  |  |->ipOfficeDayDelayQuantity: number
            |  |  |  |->eventDate: date (YYYY-MM-DD)
            |  |->assignmentBag: list of dictionary
            |  |  |->assignmentDocumentLocationURI: url as string
            |  |  |->assignmentReceivedDate: date (YYYY-MM-DD)
            |  |  |->reelAndFrameNumber: string (number/number)
            |  |  |->frameNumber: number
            |  |  |->assignmentRecordedDate: date (YYYY-MM-DD)
            |  |  |->conveyanceText: string
            |  |  |->imageAvailableStatusCode: boolean
            |  |  |->assigneeBag: list of dictionary
            |  |  |  |->assigneeAddress: dictionary
            |  |  |  |  |->cityName: string
            |  |  |  |  |->countryOrStateCode: string
            |  |  |  |  |->postalCode: string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->addressLineOneText: string
            |  |  |  |->assigneeNameText: string
            |  |  |->assignmentMailedDate: date (YYYY-MM-DD)
            |  |  |->reelNumber: number
            |  |  |->correspondenceAddress: dictionary
            |  |  |  |->addressLineOneText: string
            |  |  |  |->correspondentNameText: string
            |  |  |  |->addressLineTwoText: string
            |  |  |->assignorBag: list of dictionary
            |  |  |  |->executionDate: date (YYYY-MM-DD)
            |  |  |  |->assignorName: string
            |  |  |->pageTotalQuantity: number
            |  |->pgpubDocumentMetaData: dictionary
            |  |  |->productIdentifier: string
            |  |  |->zipFileName: string
            |  |  |->fileCreateDateTime: datetime (YYYY-MM-DDThh:mm:ss.ss)
            |  |  |->xmlFileName: string
            |  |  |->fileLocationURI: url as string
            |  |->lastIngestionDateTime: datetime (YYYY-MM-DDThh:mm:ss.ss)
            |  |->recordAttorney: dictionary
            |  |  |->customerNumberCorrespondenceData: dictionary
            |  |  |  |->powerOfAttorneyAddressBag: list of dictionary
            |  |  |  |  |->cityName: string
            |  |  |  |  |->geographicRegionName: string
            |  |  |  |  |->geographicRegionCode: string
            |  |  |  |  |->countryCode: string
            |  |  |  |  |->postalCode: number as string
            |  |  |  |  |->nameLineOneText: string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->addressLineOneText: string
            |  |  |  |  |->addressLineTwoText: string
            |  |  |  |->patronIdentifier: number
            |  |  |->powerOfAttorneyBag: list of dictionary
            |  |  |  |->activeIndicator: string
            |  |  |  |->firstName: string
            |  |  |  |->lastName: string
            |  |  |  |->registrationNumber: nunmber as string
            |  |  |  |->attorneyAddressBag: [
            |  |  |  |  |->cityName: string
            |  |  |  |  |->geographicRegionName: string
            |  |  |  |  |->geographicRegionCode: string
            |  |  |  |  |->countryCode: string
            |  |  |  |  |->postalCode: number as string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->addressLineOneText: string
            |  |  |  |  |->addressLineTwoText: string
            |  |  |  |->telecommunicationAddressBag: list of dictionary[
            |  |  |  |  |->telecommunicationNumber: string
            |  |  |  |  |->telecomTypeCode: string
            |  |  |  |->registeredPractitionerCategory: string
            |  |  |->attorneyBag: list of dictionary
            |  |  |  |->activeIndicator: string
            |  |  |  |->firstName: string
            |  |  |  |->lastName: string
            |  |  |  |->registrationNumber: number as string
            |  |  |  |->attorneyAddressBag: list of dictionary
            |  |  |  |  |->cityName: string
            |  |  |  |  |->geographicRegionName: string
            |  |  |  |  |->geographicRegionCode: string
            |  |  |  |  |->countryCode: string
            |  |  |  |  |->postalCode: number as string
            |  |  |  |  |->nameLineOneText: string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->addressLineOneText: string
            |  |  |  |  |->addressLineTwoText: string
            |  |->applicationNumberText: number as string
            |  |->correspondenceAddressBag: list of dictionary
            |  |  |->cityName: string
            |  |  |->geographicRegionName: string
            |  |  |->geographicRegionCode: string
            |  |  |->countryCode: string
            |  |  |->postalCode: number as string
            |  |  |->nameLineOneText: string
            |  |  |->countryName: string
            |  |  |->addressLineOneText: string
            |  |  |->addressLineTwoText: string
            |  |->foreignPriorityBag: list of dictionary
            |  |  |->filingDate: date (YYYY-MM-DD)
            |  |  |->applicationNumberText: string
            |  |  |->ipOfficeName: string
            |  |->applicationMetaData: dictionary{
            |  |  |->firstInventorToFileIndicator: string
            |  |  |->applicationStatusCode: number
            |  |  |->applicationTypeCode: string
            |  |  |->entityStatusData: dictionary
            |  |  |  |->smallEntityStatusIndicator: boolean
            |  |  |  |->businessEntityStatusCategory: string
            |  |  |->filingDate: date (YYYY-MM-DD)
            |  |  |->uspcSymbolText: string (number/number)
            |  |  |->nationalStageIndicator: boolean
            |  |  |->firstInventorName: string
            |  |  |->cpcClassificationBag: list of strings
            |  |  |->effectiveFilingDate: date (YYYY-MM-DD)
            |  |  |->publicationDateBag: list of dates (YYYY-MM-DD) 
            |  |  |->publicationSequenceNumberBag: list of numbers as strings
            |  |  |->earliestPublicationDate: date (YYYY-MM-DD)
            |  |  |->applicationTypeLabelName: string
            |  |  |->applicationStatusDate: date (YYYY-MM-DD)
            |  |  |->class: number as string
            |  |  |->applicationTypeCategory: string
            |  |  |->inventorBag: list of dictionary
            |  |  |  |->firstName: string
            |  |  |  |->lastName: string
            |  |  |  |->inventorNameText: string
            |  |  |  |->correspondenceAddressBag: list of dictionary
            |  |  |  |  |->cityName: string
            |  |  |  |  |->countryCode: string
            |  |  |  |  |->nameLineOneText: string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->postalAddressCategory: string
            |  |  |->applicationStatusDescriptionText: string
            |  |  |->patentNumber: number as string
            |  |  |->grantDate: date (YYYY-MM-DD)
            |  |  |->applicantBag: list of dictionary
            |  |  |  |->applicantNameText: string
            |  |  |  |->correspondenceAddressBag: list of dictionary
            |  |  |  |  |->cityName: string
            |  |  |  |  |->countryCode: string
            |  |  |  |  |->nameLineOneText: string
            |  |  |  |  |->countryName: string
            |  |  |  |  |->postalAddressCategory: string
            |  |  |->firstApplicantName: string
            |  |  |->customerNumber: number
            |  |  |->groupArtUnitNumber: number as string
            |  |  |->earliestPublicationNumber: string
            |  |  |->inventionTitle: string
            |  |  |->applicationConfirmationNumber: number
            |  |  |->examinerNameText: string
            |  |  |->subclass: number as string
            |  |  |->publicationCategoryBag: list of strings
            |  |  |->docketNumber: number as string, with decimals
            |  |->parentContinuityBag: list of dictionary
            |  |  |->parentApplicationStatusCode: number
            |  |  |->claimParentageTypeCode: string
            |  |  |->claimParentageTypeCodeDescriptionText: string
            |  |  |->parentApplicationStatusDescriptionText: string
            |  |  |->parentApplicationNumberText: string
            |  |  |->parentApplicationFilingDate: date (YYYY-MM-DD)
            |  |  |->childApplicationNumberText: number as string
            |  |->childContinuityBag: list of dictionary
            |  |  |->firstInventorToFileIndicator: boolean
            |  |  |->childApplicationStatusDescriptionText: string
            |  |  |->claimParentageTypeCode: string
            |  |  |->childApplicationStatusCode: number
            |  |  |->claimParentageTypeCodeDescriptionText: string
            |  |  |->childPatentNumber: number as string
            |  |  |->parentApplicationNumberText: number as string
            |  |  |->childApplicationFilingDate: date (YYYY-MM-DD)
            |  |  |->childApplicationNumberText: number as string
            |->requestIdentifier: string
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> data = api.get_application_data("14412875")
        """
        endpoint = f"patent/applications/{application_number}"
        return self._make_request(endpoint, method="GET")
    
    def get_application_metadata(self, application_number: str) -> Dict[str, Any]:
        """
        Get patent application meta data for a provided application number.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing application metadata
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> metadata = api.get_application_metadata("14412875")
        """
        endpoint = f"patent/applications/{application_number}/meta-data"
        response = self._make_request(endpoint, method="GET")
        return response
    
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
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> continuity = api.get_continuity_data("14412875")
        """
        endpoint = f"patent/applications/{application_number}/continuity"
        return self._make_request(endpoint, method="GET")
    
    def get_documents(
        self, 
        application_number: str
    ) -> Dict[str, Any]:
        """
        Get documents details for an application number.
        
        This includes documents under all codes (Examiner's Amendment Communication, 
        Printer Rush, IDS Filed, Application is Now Complete, PTA 36 months).
        Use this endpoint when you want documents related to a specific patent 
        application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing document information and download options
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> documents = api.get_documents("14412875")
        """
        endpoint = f"patent/applications/{application_number}/documents"
        return self._make_request(endpoint, method="GET")
    
    def get_associated_documents(self, application_number: str) -> Dict[str, Any]:
        """
        Get associated (pgpub, grant) documents meta-data for an application.
        
        This endpoint returns metadata for published application documents (pgpub) and 
        granted patent documents, including download URLs for bulk XML files.
        
        Args:
            application_number: The patent application number (e.g., "14104993")
            
        Returns:
            Dictionary containing:
            - count: Number of results
            - patentFileWrapperDataBag: List of patent data with:
              - applicationNumberText: Application number
              - pgpubDocumentMetaData: Published application metadata (if available)
                - zipFileName: Name of the ZIP file
                - productIdentifier: Product identifier (e.g., "APPXML")
                - fileLocationURI: URL to download the bulk XML ZIP file
                - fileCreateDateTime: File creation date/time
                - xmlFileName: Name of the XML file inside the ZIP
              - grantDocumentMetaData: Granted patent metadata (if available)
                - zipFileName: Name of the ZIP file
                - productIdentifier: Product identifier (e.g., "PTGRXML")
                - fileLocationURI: URL to download the bulk XML ZIP file
                - fileCreateDateTime: File creation date/time
                - xmlFileName: Name of the XML file inside the ZIP
              - requestIdentifier: Unique request identifier
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> associated_docs = api.get_associated_documents("14104993")
            >>> # Access published document URL
            >>> if 'pgpubDocumentMetaData' in associated_docs['patentFileWrapperDataBag'][0]:
            ...     pgpub_url = associated_docs['patentFileWrapperDataBag'][0]['pgpubDocumentMetaData']['fileLocationURI']
            
        Note:
            The fileLocationURI points to bulk ZIP files containing XML data. These are large
            files that contain multiple patent applications. You'll need to extract and parse
            the XML to find the specific application's data.
        """
        endpoint = f"patent/applications/{application_number}/associated-documents"
        return self._make_request(endpoint, method="GET")
    
    def get_pgpub_document_url(self, application_number: str) -> Optional[str]:
        """
        Get the published application (pgpub) document download URL for an application.
        
        This is a convenience method that extracts the fileLocationURI from pgpubDocumentMetaData.
        
        Args:
            application_number: The patent application number
            
        Returns:
            URL string to download the published application bulk XML ZIP file, or None if not available
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> pgpub_url = api.get_pgpub_document_url("14104993")
            >>> # pgpub_url: "https://bulkdata.uspto.gov/data/patent/application/redbook/fulltext/2024/ipa240104.zip"
        """
        try:
            result = self.get_associated_documents(application_number)
            patent_data = result.get('patentFileWrapperDataBag', [])
            if patent_data and 'pgpubDocumentMetaData' in patent_data[0]:
                return patent_data[0]['pgpubDocumentMetaData'].get('fileLocationURI')
        except Exception:
            pass
        return None
    
    def get_grant_document_url(self, application_number: str) -> Optional[str]:
        """
        Get the granted patent document download URL for an application.
        
        This is a convenience method that extracts the fileLocationURI from grantDocumentMetaData.
        
        Args:
            application_number: The patent application number
            
        Returns:
            URL string to download the granted patent bulk XML ZIP file, or None if not available
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> grant_url = api.get_grant_document_url("14104993")
            >>> # grant_url: "https://bulkdata.uspto.gov/data/patent/grant/redbook/fulltext/2016/ipg160405.zip"
        """
        try:
            result = self.get_associated_documents(application_number)
            patent_data = result.get('patentFileWrapperDataBag', [])
            if patent_data and 'grantDocumentMetaData' in patent_data[0]:
                return patent_data[0]['grantDocumentMetaData'].get('fileLocationURI')
        except Exception:
            pass
        return None
    
    def get_transactions(
        self, 
        application_number: str
    ) -> Dict[str, Any]:
        """
        Get transaction data for an application number.
        
        This includes details on the date of the transaction, code (Examiner's 
        Amendment Communication, Printer Rush, IDS Filed, Application is Now 
        Complete, PTA 36 months), and transaction description.
        Use this endpoint when you want transaction data related to a specific 
        patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing transaction data
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> transactions = api.get_transactions("14412875")
        """
        endpoint = f"patent/applications/{application_number}/transactions"
        return self._make_request(endpoint, method="GET")
    
    def get_patent_term_adjustment(self, application_number: str) -> Dict[str, Any]:
        """
        Get patent term adjustment data for an application number.
        
        Use this endpoint when you want patent term adjustment data related to a 
        specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing patent term adjustment data
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> pta = api.get_patent_term_adjustment("14412875")
        """
        endpoint = f"patent/applications/{application_number}/adjustment"
        return self._make_request(endpoint, method="GET")
    
    def get_attorney_agent_info(self, application_number: str) -> Dict[str, Any]:
        """
        Get attorney/agent data for an application number.
        
        Use this endpoint when you want address and attorney/agent information related 
        to a specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing attorney/agent information and address
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> attorney_info = api.get_attorney_agent_info("14412875")
        """
        endpoint = f"patent/applications/{application_number}/attorney"
        return self._make_request(endpoint, method="GET")
    
    def get_assignments(self, application_number: str) -> Dict[str, Any]:
        """
        Get assignment data for an application number.
        
        Use this endpoint when you want assignments data related to a specific 
        patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing assignment/ownership information
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> assignments = api.get_assignments("14412875")
        """
        endpoint = f"patent/applications/{application_number}/assignment"
        return self._make_request(endpoint, method="GET")
    
    def get_foreign_priority(self, application_number: str) -> Dict[str, Any]:
        """
        Get foreign-priority data for an application number.
        
        Use this endpoint when you want foreign priority information related to a 
        specific patent application whose application number you know.
        
        Args:
            application_number: The patent application number
            
        Returns:
            Dictionary containing foreign priority information
            
        Example:
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> foreign_priority = api.get_foreign_priority("14412875")
        """
        endpoint = f"patent/applications/{application_number}/foreign-priority"
        return self._make_request(endpoint, method="GET")
    
    def get_complete_patent_info(self, application_number: str) -> Dict[str, Any]:
        """
        Get all available information for a patent application by combining 
        multiple endpoints.
        
        This is a convenience method that fetches:
        - Application data
        - Application metadata
        - Continuity data
        - Documents
        - Associated documents
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
            >>> api = USPTOPatentAPI(api_key="your-key")
            >>> complete_info = api.get_complete_patent_info("14412875")
        """
        applicationNumber = None
        titleData = None
        descriptionData = None
        currentStatusData = None
        currentStatusCode = None
        currentStatusDate = None
        attorneys = []
        inventors = []
        mailingAddresses = []
        documents = []
        filingUser = None           # To be populated with User_Id from endpoint
        filingDate = None

        # applicationData = self.get_application_data(application_number)
        applicationMetaData = self.get_application_metadata(application_number)
        # continuity = self.get_continuity_data(application_number)
        documentsList = self.get_documents(application_number)
        associatedDocuments = self.get_associated_documents(application_number)
        # transactions = self.get_transactions(application_number)
        # patentTermAdjustment = self.get_patent_term_adjustment(application_number)
        attorneyAgent = self.get_attorney_agent_info(application_number)
        # assignments = self.get_assignments(application_number)
        # foreignPriority = self.get_foreign_priority(application_number)

        # Process Metadata and get all other relevant information 
        # [ applicationNumber, titleData, filingDate, descriptionData, currentStatusCode, 
        #   currentStatusDate, currentStatusData, mailingAddresses, inventors  ]
        if 'patentFileWrapperDataBag' in applicationMetaData.keys():
            patentFileWrapperDataBag = applicationMetaData.get('patentFileWrapperDataBag', [])
            for patentWrapperData in patentFileWrapperDataBag:
                if 'applicationNumberText' in patentWrapperData.keys():
                    applicationNumber = f"uspto_{patentWrapperData.get('applicationNumberText', '')}"
                if 'applicationMetaData' in patentWrapperData.keys():
                    metaData = patentWrapperData.get('applicationMetaData', {})
                    titleData = metaData.get('inventionTitle', '')
                    filingDate = metaData.get('filingDate', '')
                    descriptionData = metaData.get('applicationStatusDescriptionText', '')
                    currentStatusCode = metaData.get('applicationStatusCode', 0)
                    currentStatusDate = metaData.get('applicationStatusDate', '')
                    currentStatusData = metaData.get('applicationStatusDescriptionText', '')
                    applicantBag = metaData.get('applicantBag', [])
                    if len(applicantBag) > 0:
                        for person in applicantBag:
                            addressData = person.get('correspondenceAddressBag', [])
                            if len(addressData) > 0:
                                for address in addressData:
                                    processedAddress = self.processAddress(address)
                                    if (processedAddress is not None) and (processedAddress not in mailingAddresses):
                                        mailingAddresses.append(processedAddress)
                    inventorBag = metaData.get('inventorBag', [])
                    if len(inventorBag) > 0:
                        for person in inventorBag:
                            personName = person.get('inventorNameText', '').strip()
                            correspondenceAddressBag = person.get('correspondenceAddressBag', [])
                            if (personName is not None) and (personName != '') and (personName not in inventors):
                                inventors.append(person.get('inventorNameText', ''))
                            for addressData in correspondenceAddressBag:
                                processedAddress = self.processAddress(addressData)
                                if (processedAddress is not None) and (processedAddress not in mailingAddresses):
                                    mailingAddresses.append(processedAddress)
        # Process all available documents and add url with source to documents
        if 'documentBag' in documentsList.keys():
            documentBag = documentsList.get('documentBag', [])
            if len(documentBag) > 0:
                for fileData in documentBag:
                    if 'downloadUrldownloadOptionBag' in fileData.keys():
                        fileDownloadData = fileData.get('downloadOptionBag', [])
                        if len(fileDownloadData) > 0:
                            for downloadData in fileDownloadData:
                                if 'downloadUrl' in downloadData.keys():
                                    documents.append({
                                        'source': 'uspto',
                                        'url': downloadData.get('downloadUrl', '')
                                    })
        if 'patentFileWrapperDataBag' in associatedDocuments.keys():
            patentFileWrapperDataBag = associatedDocuments.get('patentFileWrapperDataBag', [])
            for documentData in patentFileWrapperDataBag:
                grantDocumentData = documentData.get('grantDocumentMetaData', {})
                grantFileUri = grantDocumentData.get('fileLocationURI', '')
                if (grantFileUri is not None) and (grantFileUri != ''):
                    document = {
                        'source': 'uspto',
                        'url': grantFileUri
                    }
                    if grantFileUri not in documents:
                        documents.append(document)
                pgpubDocumentData = documentData.get('pgpubDocumentMetaData', {})
                pgpubFileUri = pgpubDocumentData.get('fileLocationURI', '')
                if (pgpubFileUri is not None) and (pgpubFileUri != ''):
                    document = {
                        'source': 'uspto',
                        'url': pgpubFileUri
                    }
                    if pgpubFileUri not in documents:
                        documents.append(document)
        # Process all available mailing addresses from attorney/agent information
        if 'patentFileWrapperDataBag' not in attorneyAgent.keys():
            patentFileWrapperDataBag = attorneyAgent.get('patentFileWrapperDataBag', {})
            for item in patentFileWrapperDataBag:
                if 'recordAttorney' in item.keys():
                    recordAttorney = item.get('recordAttorney', {})
                    if 'customerNumberCorrespondenceData' in recordAttorney.keys():
                        customerCorrespondenceData = recordAttorney.get('customerNumberCorrespondenceData', {})
                        if 'powerOfAttorneyAddressBag' in customerCorrespondenceData.keys():
                            powerOfAttorneyAddressBag = customerCorrespondenceData.get('powerOfAttorneyAddressBag', [])
                            for addressData in powerOfAttorneyAddressBag:
                                processedAddress = self.processAddress(addressData)
                                if (processedAddress is not None) and (processedAddress not in mailingAddresses):
                                    mailingAddresses.append(processedAddress)
                    if 'powerOfAttorneyBag' in recordAttorney.keys():
                        powerOfAttorneyBag = recordAttorney.get('powerOfAttorneyBag', [])
                        for personData in powerOfAttorneyBag:
                            personName = (personData.get('firstName', '') + ' ' + personData.get('lastName', '')).strip()
                            registrationNumber = personData.get('registrationNumber', '')
                            telecommunicationBag = personData.get('telecommunicationAddressBag', [])
                            contacts = []
                            for communication in telecommunicationBag:
                                number = communication.get('telecommunicationNumber', '')
                                if (number!='') and (number!=None) and (number not in contacts):
                                    contacts.append(number)
                            attorneyPersonData = {
                                'name': personName,
                                'registrationNumber': registrationNumber,
                                'contact': contacts
                            }
                            if (attorneyPersonData not in attorneys) and (personName!='') and (registrationNumber!='') and (len(contacts)>0):
                                attorneys.append(attorneyPersonData)
                            addressDataList = personData.get('attorneyAddressBag', [])
                            for addressData in addressDataList:
                                processedAddress = self.processAddress(addressData)
                                if (processedAddress is not None) and (processedAddress not in mailingAddresses):
                                    mailingAddresses.append(processedAddress)
                    if 'attorneyBag' in recordAttorney.keys():
                        attorneyBag = recordAttorney.get('attorneyBag', [])
                        for personData in attorneyBag:
                            personName = (personData.get('firstName', '') + ' ' + personData.get('lastName', '')).strip()
                            registrationNumber = personData.get('registrationNumber', '')
                            contacts = []
                            telecommunicationBag = personData.get('telecommunicationAddressBag', [])
                            for communication in telecommunicationBag:
                                number = communication.get('telecommunicationNumber', '')
                                if (number!='') and (number!=None) and (number not in contacts):
                                    contacts.append(number)
                            attorneyPersonData = {
                                'name': personName,
                                'registrationNumber': registrationNumber,
                                'contact': contacts
                            }
                            if (attorneyPersonData not in attorneys) and (personName!='') and (registrationNumber!='') and (len(contacts)>0):
                                attorneys.append(attorneyPersonData)
                            personAddresses = personData.get('attorneyAddressBag', [])
                            for addressData in personAddresses:
                                processedAddress = self.processAddress(addressData)
                                if (processedAddress is not None) and (processedAddress not in mailingAddresses):
                                    mailingAddresses.append(processedAddress)

        returnVal = {
            '_id': applicationNumber,
            'title': titleData,
            'status': currentStatusData,
            'description': descriptionData,
            'currentStatusCode': currentStatusCode,
            'currentStatusDate': currentStatusDate,
            'attorneys': attorneys,    # Name, Registration Number, Contact
            'inventors': inventors,    # List of names
            'mailingAddresses': mailingAddresses,  # cityName, geographicRegionName, geographicRegionCode, countryCode, postalCode, addressLineText
            'created_by': filingUser,
            'created_date': datetime.utcnow().isoformat(),
            'filing_date': filingDate,
            'references': [],  # list of dictionaries with url, title, granted_date, similarity_rate
            'documents': documents
        }

        return returnVal


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
    return api.search_patents(query=query, limit=limit, offset=offset)


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
        >>> data = get_patent_application_data("14412875", api_key="your-api-key")
    """
    if not api_key:
        raise MissingAPIKeyError(
            "API key is required. Get your API key at: https://account.uspto.gov/api-manager/"
        )
    api = USPTOPatentAPI(api_key=api_key)
    return api.get_application_data(application_number)
