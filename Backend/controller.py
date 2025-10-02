"""
Controller functions for handling business logic
"""

mock_cases = [
    {
        'id': 'case_001',
        'title': 'AI-Powered Patent Analysis System',
        'filing_date': '2024-01-15',
        'status': 'Active',
        'accepted_on': '2024-02-01',
        'accepted_by': "user_001",
        'created_by': 'user_001',
        'description': 'A comprehensive system for analyzing patent documents using artificial intelligence',
        'priority': 'High',
        'assigned_to': 'user_123',
        'created_date': '2024-01-15',
        'due_date': '2024-03-15',
        'references': [
            {
                'url': 'https://dummyurl.com/case_001/ref1',
                'title': 'US Patent 10,123,456 - Machine Learning Methods for Patent Classification',
                'granted_date': '2020-03-15',
                'similarity_rate': 85
            },
            {
                'url': 'https://dummyurl.com/case_001/ref2',
                'title': 'US Patent 9,876,543 - Automated Document Analysis Using Neural Networks',
                'granted_date': '2019-08-22',
                'similarity_rate': 72
            },
            {
                'url': 'https://dummyurl.com/case_001/ref3',
                'title': 'US Patent 10,987,654 - Intelligent Search Algorithms for Patent Databases',
                'granted_date': '2021-11-10',
                'similarity_rate': 68
            }
        ],
        'keywords': ['AI', 'patent analysis', 'document analysis', 'artificial intelligence', 'system']
    },
    {
        'id': 'case_002',
        'title': 'Blockchain-Based IP Management Platform',
        'filing_date': '2024-01-20',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_002',
        'description': 'A decentralized platform for managing intellectual property rights',
        'priority': 'Medium',
        'assigned_to': 'user_123',
        'created_date': '2024-01-20',
        'due_date': '2024-03-20',
        'references': [
            {
                'url': 'https://dummyurl.com/case_002/ref1',
                'title': 'US Patent 11,234,567 - Blockchain-Based Digital Rights Management',
                'granted_date': '2021-05-20',
                'similarity_rate': 78
            },
            {
                'url': 'https://dummyurl.com/case_002/ref2',
                'title': 'US Patent 10,876,543 - Decentralized IP Management Systems',
                'granted_date': '2020-09-15',
                'similarity_rate': 82
            }
        ],
        'keywords': ['blockchain', 'IP management', 'decentralized', 'intellectual property', 'platform']
    },
    {
        'id': 'case_003',
        'title': 'Machine Learning Patent Search Engine',
        'filing_date': '2024-01-25',
        'status': 'Completed',
        'accepted_on': '2024-02-10',
        'accepted_by': "user_001",
        'created_by': 'user_003',
        'description': 'Advanced search engine for patent databases using ML algorithms',
        'priority': 'High',
        'assigned_to': 'user_123',
        'created_date': '2024-01-25',
        'due_date': '2024-03-25',
        'references': [
            {
                'url': 'https://dummyurl.com/case_003/ref1',
                'title': 'US Patent 11,345,678 - Semantic Search Methods for Patent Databases',
                'granted_date': '2021-08-30',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_003/ref2',
                'title': 'US Patent 10,765,432 - Vector-Based Patent Similarity Analysis',
                'granted_date': '2020-12-10',
                'similarity_rate': 76
            }
        ],
        'keywords': ['machine learning', 'patent search', 'search engine', 'ML algorithms', 'patent database']
    },
    {
        'id': 'case_004',
        'title': 'Automated Legal Document Drafting',
        'filing_date': '2024-01-28',
        'status': 'Active',
        'accepted_on': '2024-02-12',
        'accepted_by': 'user_002',
        'created_by': 'user_004',
        'description': 'System for drafting legal documents using AI',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-01-28',
        'due_date': '2024-03-28',
        'references': [
            {
                'url': 'https://dummyurl.com/case_004/ref1',
                'title': 'US Patent 11,456,789 - AI-Powered Legal Document Generation',
                'granted_date': '2021-11-25',
                'similarity_rate': 91
            },
            {
                'url': 'https://dummyurl.com/case_004/ref2',
                'title': 'US Patent 10,654,321 - Natural Language Processing for Legal Writing',
                'granted_date': '2020-07-18',
                'similarity_rate': 84
            }
        ],
        'keywords': ['legal document', 'drafting', 'automation', 'AI', 'system']
    },
    {
        'id': 'case_005',
        'title': 'IP Portfolio Management Tool',
        'filing_date': '2024-02-01',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_005',
        'description': 'Tool for managing IP portfolios for enterprises',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-02-01',
        'due_date': '2024-04-01',
        'references': [
            {
                'url': 'https://dummyurl.com/case_005/ref1',
                'title': 'US Patent 11,567,890 - Enterprise IP Portfolio Management Systems',
                'granted_date': '2022-01-15',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_005/ref2',
                'title': 'US Patent 10,543,210 - Intellectual Property Asset Tracking Methods',
                'granted_date': '2020-04-22',
                'similarity_rate': 79
            }
        ],
        'keywords': ['IP portfolio', 'management', 'tool', 'enterprise', 'intellectual property']
    },
    {
        'id': 'case_006',
        'title': 'Trademark Infringement Detection',
        'filing_date': '2024-02-03',
        'status': 'Completed',
        'accepted_on': '2024-02-15',
        'accepted_by': 'user_004',
        'created_by': 'user_006',
        'description': 'AI-powered detection of trademark infringements',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-03',
        'due_date': '2024-04-03',
        'references': [
            {
                'url': 'https://dummyurl.com/case_006/ref1',
                'title': 'US Patent 11,678,901 - Automated Trademark Similarity Detection',
                'granted_date': '2022-03-08',
                'similarity_rate': 93
            },
            {
                'url': 'https://dummyurl.com/case_006/ref2',
                'title': 'US Patent 10,432,109 - Machine Learning for IP Infringement Analysis',
                'granted_date': '2020-06-30',
                'similarity_rate': 86
            }
        ],
        'keywords': ['trademark', 'infringement', 'detection', 'AI', 'intellectual property']
    },
    {
        'id': 'case_007',
        'title': 'Patent Valuation Platform',
        'filing_date': '2024-02-05',
        'status': 'Active',
        'accepted_on': '2024-02-18',
        'accepted_by': 'user_002',
        'created_by': 'user_007',
        'description': 'Platform for automated patent valuation',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-02-05',
        'due_date': '2024-04-05',
        'references': [
            {
                'url': 'https://dummyurl.com/case_007/ref1',
                'title': 'US Patent 11,789,012 - Automated Patent Valuation Methods',
                'granted_date': '2022-05-12',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_007/ref2',
                'title': 'US Patent 10,321,098 - Intellectual Property Asset Valuation Systems',
                'granted_date': '2020-09-05',
                'similarity_rate': 81
            }
        ],
        'keywords': ['patent', 'valuation', 'platform', 'automation', 'intellectual property']
    },
    {
        'id': 'case_008',
        'title': 'Copyright Management System',
        'filing_date': '2024-02-07',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_008',
        'description': 'System for managing copyright registrations',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-02-07',
        'due_date': '2024-04-07',
        'references': [
            {
                'url': 'https://dummyurl.com/case_008/ref1',
                'title': 'US Patent 11,890,123 - Digital Copyright Management Systems',
                'granted_date': '2022-07-20',
                'similarity_rate': 75
            },
            {
                'url': 'https://dummyurl.com/case_008/ref2',
                'title': 'US Patent 10,210,987 - Automated Copyright Registration Methods',
                'granted_date': '2020-11-12',
                'similarity_rate': 83
            }
        ],
        'keywords': ['copyright', 'management', 'system', 'registration', 'intellectual property']
    },
    {
        'id': 'case_009',
        'title': 'IP Litigation Analytics',
        'filing_date': '2024-02-09',
        'status': 'Completed',
        'accepted_on': '2024-02-20',
        'accepted_by': 'user_004',
        'created_by': 'user_009',
        'description': 'Analytics platform for IP litigation trends',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-09',
        'due_date': '2024-04-09',
        'references': [
            {
                'url': 'https://dummyurl.com/case_009/ref1',
                'title': 'US Patent 11,901,234 - IP Litigation Trend Analysis Systems',
                'granted_date': '2022-09-15',
                'similarity_rate': 90
            },
            {
                'url': 'https://dummyurl.com/case_009/ref2',
                'title': 'US Patent 10,109,876 - Legal Analytics and Prediction Methods',
                'granted_date': '2021-01-28',
                'similarity_rate': 77
            }
        ],
        'keywords': ['IP', 'litigation', 'analytics', 'platform', 'trends']
    },
    {
        'id': 'case_010',
        'title': 'Patent Expiry Notification Service',
        'filing_date': '2024-02-11',
        'status': 'Active',
        'accepted_on': '2024-02-22',
        'accepted_by': 'user_003',
        'created_by': 'user_010',
        'description': 'Service to notify about upcoming patent expiries',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-02-11',
        'due_date': '2024-04-11',
        'references': [
            {
                'url': 'https://dummyurl.com/case_010/ref1',
                'title': 'US Patent 12,012,345 - Patent Lifecycle Management Systems',
                'granted_date': '2022-11-30',
                'similarity_rate': 85
            },
            {
                'url': 'https://dummyurl.com/case_010/ref2',
                'title': 'US Patent 10,098,765 - Automated Patent Renewal Notification Methods',
                'granted_date': '2021-03-15',
                'similarity_rate': 82
            }
        ],
        'keywords': ['patent', 'expiry', 'notification', 'service', 'reminder']
    },
    {
        'id': 'case_011',
        'title': 'Trademark Renewal Automation',
        'filing_date': '2024-02-13',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_001',
        'description': 'Automated system for trademark renewals',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-02-13',
        'due_date': '2024-04-13',
        'references': [
            {
                'url': 'https://dummyurl.com/case_011/ref1',
                'title': 'US Patent 12,123,456 - Automated Trademark Renewal Systems',
                'granted_date': '2023-01-15',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_011/ref2',
                'title': 'US Patent 10,987,654 - IP Renewal Notification Methods',
                'granted_date': '2021-05-20',
                'similarity_rate': 79
            }
        ],
        'keywords': ['trademark', 'renewal', 'automation', 'system', 'intellectual property']
    },
    {
        'id': 'case_012',
        'title': 'IP Risk Assessment Tool',
        'filing_date': '2024-02-15',
        'status': 'Completed',
        'accepted_on': '2024-02-25',
        'accepted_by': 'user_001',
        'created_by': 'user_002',
        'description': 'Tool for assessing IP-related risks',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-02-15',
        'due_date': '2024-04-15',
        'references': [
            {
                'url': 'https://dummyurl.com/case_012/ref1',
                'title': 'US Patent 12,234,567 - IP Risk Assessment and Analysis Methods',
                'granted_date': '2023-03-10',
                'similarity_rate': 92
            },
            {
                'url': 'https://dummyurl.com/case_012/ref2',
                'title': 'US Patent 10,876,543 - Intellectual Property Risk Management Systems',
                'granted_date': '2021-07-25',
                'similarity_rate': 84
            }
        ],
        'keywords': ['IP', 'risk assessment', 'tool', 'risk', 'intellectual property']
    },
    {
        'id': 'case_013',
        'title': 'Patent Licensing Marketplace',
        'filing_date': '2024-02-17',
        'status': 'Active',
        'accepted_on': '2024-02-27',
        'accepted_by': 'user_003',
        'created_by': 'user_003',
        'description': 'Marketplace for patent licensing opportunities',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-02-17',
        'due_date': '2024-04-17',
        'references': [
            {
                'url': 'https://dummyurl.com/case_013/ref1',
                'title': 'US Patent 12,345,678 - Patent Licensing Marketplace Systems',
                'granted_date': '2023-05-20',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_013/ref2',
                'title': 'US Patent 10,765,432 - IP Asset Trading Platforms',
                'granted_date': '2021-09-15',
                'similarity_rate': 81
            }
        ],
        'keywords': ['patent', 'licensing', 'marketplace', 'opportunities', 'intellectual property']
    },
    {
        'id': 'case_014',
        'title': 'IP Due Diligence Automation',
        'filing_date': '2024-02-19',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_004',
        'description': 'Automated due diligence for IP transactions',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-02-19',
        'due_date': '2024-04-19',
        'references': [
            {
                'url': 'https://dummyurl.com/case_014/ref1',
                'title': 'US Patent 12,456,789 - Automated IP Due Diligence Methods',
                'granted_date': '2023-07-30',
                'similarity_rate': 86
            },
            {
                'url': 'https://dummyurl.com/case_014/ref2',
                'title': 'US Patent 10,654,321 - Legal Due Diligence Automation Systems',
                'granted_date': '2021-11-10',
                'similarity_rate': 78
            }
        ],
        'keywords': ['IP', 'due diligence', 'automation', 'transactions', 'intellectual property']
    },
    {
        'id': 'case_015',
        'title': 'Patent Family Tree Visualizer',
        'filing_date': '2024-02-21',
        'status': 'Completed',
        'accepted_on': '2024-03-01',
        'accepted_by': 'user_002',
        'created_by': 'user_005',
        'description': 'Visualization tool for patent family relationships',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-02-21',
        'due_date': '2024-04-21',
        'references': [
            {
                'url': 'https://dummyurl.com/case_015/ref1',
                'title': 'US Patent 12,567,890 - Patent Family Tree Visualization Systems',
                'granted_date': '2023-09-15',
                'similarity_rate': 91
            },
            {
                'url': 'https://dummyurl.com/case_015/ref2',
                'title': 'US Patent 10,543,210 - Patent Relationship Mapping Methods',
                'granted_date': '2022-01-25',
                'similarity_rate': 83
            }
        ],
        'keywords': ['patent', 'family tree', 'visualization', 'relationships', 'tool']
    },
    {
        'id': 'case_016',
        'title': 'Trademark Watch Service',
        'filing_date': '2024-02-23',
        'status': 'Active',
        'accepted_on': '2024-03-03',
        'accepted_by': 'user_001',
        'created_by': 'user_006',
        'description': 'Service to monitor new trademark filings',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-02-23',
        'due_date': '2024-04-23',
        'references': [
            {
                'url': 'https://dummyurl.com/case_016/ref1',
                'title': 'US Patent 12,678,901 - Trademark Watch and Monitoring Systems',
                'granted_date': '2023-11-20',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_016/ref2',
                'title': 'US Patent 10,432,109 - Automated IP Monitoring Methods',
                'granted_date': '2022-03-15',
                'similarity_rate': 80
            }
        ],
        'keywords': ['trademark', 'watch', 'service', 'monitor', 'filings']
    },
    {
        'id': 'case_017',
        'title': 'IP Asset Valuation Engine',
        'filing_date': '2024-02-25',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_007',
        'description': 'Engine for automated IP asset valuation',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-02-25',
        'due_date': '2024-04-25',
        'references': [
            {
                'url': 'https://dummyurl.com/case_017/ref1',
                'title': 'US Patent 12,789,012 - IP Asset Valuation Engine Systems',
                'granted_date': '2024-01-10',
                'similarity_rate': 94
            },
            {
                'url': 'https://dummyurl.com/case_017/ref2',
                'title': 'US Patent 10,321,098 - Automated Patent Valuation Methods',
                'granted_date': '2022-05-30',
                'similarity_rate': 85
            }
        ],
        'keywords': ['IP asset', 'valuation', 'engine', 'automation', 'intellectual property']
    },
    {
        'id': 'case_018',
        'title': 'Patent Application Drafting Assistant',
        'filing_date': '2024-02-27',
        'status': 'Completed',
        'accepted_on': '2024-03-07',
        'accepted_by': 'user_004',
        'created_by': 'user_008',
        'description': 'AI assistant for drafting patent applications',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-27',
        'due_date': '2024-04-27',
        'references': [
            {
                'url': 'https://dummyurl.com/case_018/ref1',
                'title': 'US Patent 12,890,123 - Patent Application Drafting Assistant Systems',
                'granted_date': '2024-03-05',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_018/ref2',
                'title': 'US Patent 10,210,987 - Automated Patent Writing Methods',
                'granted_date': '2022-07-20',
                'similarity_rate': 82
            }
        ],
        'keywords': ['patent', 'application', 'drafting', 'assistant', 'AI']
    },
    {
        'id': 'case_019',
        'title': 'IP Rights Transfer Platform',
        'filing_date': '2024-03-01',
        'status': 'Active',
        'accepted_on': '2024-03-10',
        'accepted_by': 'user_002',
        'created_by': 'user_009',
        'description': 'Platform for transferring IP rights securely',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-03-01',
        'due_date': '2024-05-01',
        'references': [
            {
                'url': 'https://dummyurl.com/case_019/ref1',
                'title': 'US Patent 12,901,234 - IP Rights Transfer Platform Systems',
                'granted_date': '2024-05-15',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_019/ref2',
                'title': 'US Patent 10,109,876 - Intellectual Property Transfer Methods',
                'granted_date': '2022-09-10',
                'similarity_rate': 79
            }
        ],
        'keywords': ['IP rights', 'transfer', 'platform', 'security', 'intellectual property']
    },
    {
        'id': 'case_020',
        'title': 'Trademark Similarity Checker',
        'filing_date': '2024-03-03',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_010',
        'description': 'Tool for checking trademark similarity',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-03-03',
        'due_date': '2024-05-03',
        'references': [
            {
                'url': 'https://dummyurl.com/case_020/ref1',
                'title': 'US Patent 13,012,345 - Trademark Similarity Checker Systems',
                'granted_date': '2024-07-20',
                'similarity_rate': 92
            },
            {
                'url': 'https://dummyurl.com/case_020/ref2',
                'title': 'US Patent 10,098,765 - Automated Trademark Comparison Methods',
                'granted_date': '2022-11-25',
                'similarity_rate': 84
            }
        ],
        'keywords': ['trademark', 'similarity', 'checker', 'tool', 'comparison']
    },
    {
        'id': 'case_021',
        'title': 'Patent Filing Deadline Tracker',
        'filing_date': '2024-03-05',
        'status': 'Completed',
        'accepted_on': '2024-03-15',
        'accepted_by': 'user_003',
        'created_by': 'user_001',
        'description': 'Tracker for patent filing deadlines',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-03-05',
        'due_date': '2024-05-05',
        'references': [
            {
                'url': 'https://dummyurl.com/case_021/ref1',
                'title': 'US Patent 13,123,456 - Patent Filing Deadline Tracker Systems',
                'granted_date': '2024-09-10',
                'similarity_rate': 85
            },
            {
                'url': 'https://dummyurl.com/case_021/ref2',
                'title': 'US Patent 10,987,654 - IP Deadline Management Methods',
                'granted_date': '2023-01-15',
                'similarity_rate': 77
            }
        ],
        'keywords': ['patent', 'filing', 'deadline', 'tracker', 'reminder']
    },
    {
        'id': 'case_022',
        'title': 'IP Dispute Resolution Portal',
        'filing_date': '2024-03-07',
        'status': 'Active',
        'accepted_on': '2024-03-17',
        'accepted_by': 'user_004',
        'created_by': 'user_002',
        'description': 'Portal for resolving IP disputes online',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-03-07',
        'due_date': '2024-05-07',
        'references': [
            {
                'url': 'https://dummyurl.com/case_022/ref1',
                'title': 'US Patent 13,234,567 - IP Dispute Resolution Portal Systems',
                'granted_date': '2024-11-25',
                'similarity_rate': 90
            },
            {
                'url': 'https://dummyurl.com/case_022/ref2',
                'title': 'US Patent 10,876,543 - Online Dispute Resolution Methods',
                'granted_date': '2023-03-20',
                'similarity_rate': 82
            }
        ],
        'keywords': ['IP', 'dispute', 'resolution', 'portal', 'online']
    },
    {
        'id': 'case_023',
        'title': 'Patent Prior Art Search Engine',
        'filing_date': '2024-03-09',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_003',
        'description': 'Engine for searching patent prior art',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-03-09',
        'due_date': '2024-05-09',
        'references': [
            {
                'url': 'https://dummyurl.com/case_023/ref1',
                'title': 'US Patent 13,345,678 - Patent Prior Art Search Engine Systems',
                'granted_date': '2025-01-15',
                'similarity_rate': 93
            },
            {
                'url': 'https://dummyurl.com/case_023/ref2',
                'title': 'US Patent 10,765,432 - Automated Prior Art Search Methods',
                'granted_date': '2023-05-30',
                'similarity_rate': 86
            }
        ],
        'keywords': ['patent', 'prior art', 'search', 'engine', 'intellectual property']
    },
    {
        'id': 'case_024',
        'title': 'IP Licensing Agreement Generator',
        'filing_date': '2024-03-11',
        'status': 'Completed',
        'accepted_on': '2024-03-21',
        'accepted_by': 'user_001',
        'created_by': 'user_004',
        'description': 'Generator for IP licensing agreements',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-03-11',
        'due_date': '2024-05-11',
        'references': [
            {
                'url': 'https://dummyurl.com/case_024/ref1',
                'title': 'US Patent 13,456,789 - IP Licensing Agreement Generator Systems',
                'granted_date': '2025-03-20',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_024/ref2',
                'title': 'US Patent 10,654,321 - Automated Contract Generation Methods',
                'granted_date': '2023-07-15',
                'similarity_rate': 81
            }
        ],
        'keywords': ['IP', 'licensing', 'agreement', 'generator', 'intellectual property']
    },
    {
        'id': 'case_025',
        'title': 'Trademark Portfolio Dashboard',
        'filing_date': '2024-03-13',
        'status': 'Active',
        'accepted_on': '2024-03-23',
        'accepted_by': 'user_003',
        'created_by': 'user_005',
        'description': 'Dashboard for managing trademark portfolios',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-03-13',
        'due_date': '2024-05-13',
        'references': [
            {
                'url': 'https://dummyurl.com/case_025/ref1',
                'title': 'US Patent 13,567,890 - Trademark Portfolio Dashboard Systems',
                'granted_date': '2025-05-10',
                'similarity_rate': 91
            },
            {
                'url': 'https://dummyurl.com/case_025/ref2',
                'title': 'US Patent 10,543,210 - IP Portfolio Management Methods',
                'granted_date': '2023-09-05',
                'similarity_rate': 83
            }
        ],
        'keywords': ['trademark', 'portfolio', 'dashboard', 'management', 'intellectual property']
    },
    {
        'id': 'case_026',
        'title': 'Patent Assignment Workflow',
        'filing_date': '2024-03-15',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_006',
        'description': 'Workflow system for patent assignments',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-03-15',
        'due_date': '2024-05-15',
        'references': [
            {
                'url': 'https://dummyurl.com/case_026/ref1',
                'title': 'US Patent 13,678,901 - Patent Assignment Workflow Systems',
                'granted_date': '2025-07-25',
                'similarity_rate': 86
            },
            {
                'url': 'https://dummyurl.com/case_026/ref2',
                'title': 'US Patent 10,432,109 - Automated Assignment Processing Methods',
                'granted_date': '2023-11-10',
                'similarity_rate': 78
            }
        ],
        'keywords': ['patent', 'assignment', 'workflow', 'system', 'intellectual property']
    },
    {
        'id': 'case_027',
        'title': 'IP Asset Insurance Platform',
        'filing_date': '2024-03-17',
        'status': 'Completed',
        'accepted_on': '2024-03-27',
        'accepted_by': 'user_002',
        'created_by': 'user_007',
        'description': 'Platform for insuring IP assets',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-03-17',
        'due_date': '2024-05-17',
        'references': [
            {
                'url': 'https://dummyurl.com/case_027/ref1',
                'title': 'US Patent 13,789,012 - IP Asset Insurance Platform Systems',
                'granted_date': '2025-09-15',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_027/ref2',
                'title': 'US Patent 10,321,098 - Intellectual Property Insurance Methods',
                'granted_date': '2024-01-20',
                'similarity_rate': 80
            }
        ],
        'keywords': ['IP asset', 'insurance', 'platform', 'intellectual property', 'risk']
    },
    {
        'id': 'case_028',
        'title': 'Trademark Application Status Tracker',
        'filing_date': '2024-03-19',
        'status': 'Active',
        'accepted_on': '2024-03-29',
        'accepted_by': 'user_001',
        'created_by': 'user_008',
        'description': 'Tracker for trademark application statuses',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-03-19',
        'due_date': '2024-05-19',
        'references': [
            {
                'url': 'https://dummyurl.com/case_028/ref1',
                'title': 'US Patent 13,890,123 - Trademark Application Status Tracker Systems',
                'granted_date': '2025-11-30',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_028/ref2',
                'title': 'US Patent 10,210,987 - Application Status Monitoring Methods',
                'granted_date': '2024-03-15',
                'similarity_rate': 79
            }
        ],
        'keywords': ['trademark', 'application', 'status', 'tracker', 'monitor']
    },
    {
        'id': 'case_029',
        'title': 'Patent Maintenance Fee Calculator',
        'filing_date': '2024-03-21',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_009',
        'description': 'Calculator for patent maintenance fees',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-03-21',
        'due_date': '2024-05-21',
        'references': [
            {
                'url': 'https://dummyurl.com/case_029/ref1',
                'title': 'US Patent 13,901,234 - Patent Maintenance Fee Calculator Systems',
                'granted_date': '2026-01-20',
                'similarity_rate': 84
            },
            {
                'url': 'https://dummyurl.com/case_029/ref2',
                'title': 'US Patent 10,109,876 - Automated Fee Calculation Methods',
                'granted_date': '2024-05-10',
                'similarity_rate': 76
            }
        ],
        'keywords': ['patent', 'maintenance fee', 'calculator', 'cost', 'intellectual property']
    },
    {
        'id': 'case_030',
        'title': 'IP Asset Marketplace',
        'filing_date': '2024-03-23',
        'status': 'Completed',
        'accepted_on': '2024-04-02',
        'accepted_by': 'user_004',
        'created_by': 'user_010',
        'description': 'Marketplace for buying and selling IP assets',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-03-23',
        'due_date': '2024-05-23',
        'references': [
            {
                'url': 'https://dummyurl.com/case_030/ref1',
                'title': 'US Patent 14,012,345 - IP Asset Marketplace Systems',
                'granted_date': '2026-03-15',
                'similarity_rate': 92
            },
            {
                'url': 'https://dummyurl.com/case_030/ref2',
                'title': 'US Patent 10,098,765 - Intellectual Property Trading Methods',
                'granted_date': '2024-07-05',
                'similarity_rate': 85
            }
        ],
        'keywords': ['IP asset', 'marketplace', 'buy', 'sell', 'intellectual property']
    },
    {
        'id': 'case_031',
        'title': 'Trademark Classifier Tool',
        'filing_date': '2024-03-25',
        'status': 'Active',
        'accepted_on': '2024-04-04',
        'accepted_by': 'user_002',
        'created_by': 'user_001',
        'description': 'Tool for classifying trademarks',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-03-25',
        'due_date': '2024-05-25',
        'references': [
            {
                'url': 'https://dummyurl.com/case_031/ref1',
                'title': 'US Patent 14,123,456 - Trademark Classifier Tool Systems',
                'granted_date': '2026-05-25',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_031/ref2',
                'title': 'US Patent 10,987,654 - Automated Classification Methods',
                'granted_date': '2024-09-20',
                'similarity_rate': 81
            }
        ],
        'keywords': ['trademark', 'classifier', 'tool', 'classification', 'intellectual property']
    },
    {
        'id': 'case_032',
        'title': 'Patent Document Translation Service',
        'filing_date': '2024-03-27',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_002',
        'description': 'Service for translating patent documents',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-03-27',
        'due_date': '2024-05-27',
        'references': [
            {
                'url': 'https://dummyurl.com/case_032/ref1',
                'title': 'US Patent 14,234,567 - Patent Document Translation Service Systems',
                'granted_date': '2026-07-30',
                'similarity_rate': 90
            },
            {
                'url': 'https://dummyurl.com/case_032/ref2',
                'title': 'US Patent 10,876,543 - Automated Translation Methods',
                'granted_date': '2024-11-15',
                'similarity_rate': 83
            }
        ],
        'keywords': ['patent', 'document', 'translation', 'service', 'language']
    },
    {
        'id': 'case_033',
        'title': 'IP Litigation Support System',
        'filing_date': '2024-03-29',
        'status': 'Completed',
        'accepted_on': '2024-04-08',
        'accepted_by': 'user_003',
        'created_by': 'user_003',
        'description': 'Support system for IP litigation cases',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-03-29',
        'due_date': '2024-05-29',
        'references': [
            {
                'url': 'https://dummyurl.com/case_033/ref1',
                'title': 'US Patent 14,345,678 - IP Litigation Support System Systems',
                'granted_date': '2026-09-20',
                'similarity_rate': 91
            },
            {
                'url': 'https://dummyurl.com/case_033/ref2',
                'title': 'US Patent 10,765,432 - Legal Support Automation Methods',
                'granted_date': '2025-01-10',
                'similarity_rate': 84
            }
        ],
        'keywords': ['IP', 'litigation', 'support', 'system', 'cases']
    },
    {
        'id': 'case_034',
        'title': 'Trademark Opposition Management',
        'filing_date': '2024-03-31',
        'status': 'Active',
        'accepted_on': '2024-04-10',
        'accepted_by': 'user_004',
        'created_by': 'user_004',
        'description': 'Management tool for trademark oppositions',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-03-31',
        'due_date': '2024-05-31',
        'references': [
            {
                'url': 'https://dummyurl.com/case_034/ref1',
                'title': 'US Patent 14,456,789 - Trademark Opposition Management Systems',
                'granted_date': '2026-11-25',
                'similarity_rate': 86
            },
            {
                'url': 'https://dummyurl.com/case_034/ref2',
                'title': 'US Patent 10,654,321 - Opposition Process Automation Methods',
                'granted_date': '2025-03-05',
                'similarity_rate': 78
            }
        ],
        'keywords': ['trademark', 'opposition', 'management', 'tool', 'intellectual property']
    },
    {
        'id': 'case_035',
        'title': 'Patent Search Automation',
        'filing_date': '2024-04-02',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_005',
        'description': 'Automation tool for patent searches',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-04-02',
        'due_date': '2024-06-02',
        'references': [
            {
                'url': 'https://dummyurl.com/case_035/ref1',
                'title': 'US Patent 14,567,890 - Patent Search Automation Systems',
                'granted_date': '2027-01-15',
                'similarity_rate': 93
            },
            {
                'url': 'https://dummyurl.com/case_035/ref2',
                'title': 'US Patent 10,543,210 - Automated Search Methods',
                'granted_date': '2025-05-20',
                'similarity_rate': 87
            }
        ],
        'keywords': ['patent', 'search', 'automation', 'tool', 'intellectual property']
    },
    {
        'id': 'case_036',
        'title': 'IP Asset Tracking System',
        'filing_date': '2024-04-04',
        'status': 'Completed',
        'accepted_on': '2024-04-14',
        'accepted_by': 'user_001',
        'created_by': 'user_006',
        'description': 'System for tracking IP assets',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-04-04',
        'due_date': '2024-06-04',
        'references': [
            {
                'url': 'https://dummyurl.com/case_036/ref1',
                'title': 'US Patent 14,678,901 - IP Asset Tracking System Systems',
                'granted_date': '2027-03-30',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_036/ref2',
                'title': 'US Patent 10,432,109 - Asset Tracking Automation Methods',
                'granted_date': '2025-07-15',
                'similarity_rate': 82
            }
        ],
        'keywords': ['IP asset', 'tracking', 'system', 'monitor', 'intellectual property']
    },
    {
        'id': 'case_037',
        'title': 'Trademark Filing Assistant',
        'filing_date': '2024-04-06',
        'status': 'Active',
        'accepted_on': '2024-04-16',
        'accepted_by': 'user_003',
        'created_by': 'user_007',
        'description': 'Assistant for filing trademark applications',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-04-06',
        'due_date': '2024-06-06',
        'references': [
            {
                'url': 'https://dummyurl.com/case_037/ref1',
                'title': 'US Patent 14,789,012 - Trademark Filing Assistant Systems',
                'granted_date': '2027-05-25',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_037/ref2',
                'title': 'US Patent 10,321,098 - Automated Filing Methods',
                'granted_date': '2025-09-10',
                'similarity_rate': 80
            }
        ],
        'keywords': ['trademark', 'filing', 'assistant', 'application', 'intellectual property']
    },
    {
        'id': 'case_038',
        'title': 'Patent Analytics Dashboard',
        'filing_date': '2024-04-08',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_008',
        'description': 'Dashboard for patent analytics',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-04-08',
        'due_date': '2024-06-08',
        'references': [
            {
                'url': 'https://dummyurl.com/case_038/ref1',
                'title': 'US Patent 14,890,123 - Patent Analytics Dashboard Systems',
                'granted_date': '2027-07-20',
                'similarity_rate': 92
            },
            {
                'url': 'https://dummyurl.com/case_038/ref2',
                'title': 'US Patent 10,210,987 - Analytics Visualization Methods',
                'granted_date': '2025-11-05',
                'similarity_rate': 85
            }
        ],
        'keywords': ['patent', 'analytics', 'dashboard', 'data', 'intellectual property']
    },
    {
        'id': 'case_039',
        'title': 'IP Rights Enforcement Platform',
        'filing_date': '2024-04-10',
        'status': 'Completed',
        'accepted_on': '2024-04-20',
        'accepted_by': 'user_002',
        'created_by': 'user_009',
        'description': 'Platform for enforcing IP rights',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-04-10',
        'due_date': '2024-06-10',
        'references': [
            {
                'url': 'https://dummyurl.com/case_039/ref1',
                'title': 'US Patent 14,901,234 - IP Rights Enforcement Platform Systems',
                'granted_date': '2027-09-15',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_039/ref2',
                'title': 'US Patent 10,109,876 - Rights Enforcement Automation Methods',
                'granted_date': '2026-01-20',
                'similarity_rate': 81
            }
        ],
        'keywords': ['IP rights', 'enforcement', 'platform', 'intellectual property', 'compliance']
    },
    {
        'id': 'case_040',
        'title': 'Trademark Renewal Reminder',
        'filing_date': '2024-04-12',
        'status': 'Active',
        'accepted_on': '2024-04-22',
        'accepted_by': 'user_001',
        'created_by': 'user_010',
        'description': 'Reminder service for trademark renewals',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-04-12',
        'due_date': '2024-06-12',
        'references': [
            {
                'url': 'https://dummyurl.com/case_040/ref1',
                'title': 'US Patent 15,012,345 - Trademark Renewal Reminder Systems',
                'granted_date': '2027-11-30',
                'similarity_rate': 85
            },
            {
                'url': 'https://dummyurl.com/case_040/ref2',
                'title': 'US Patent 10,098,765 - Automated Reminder Methods',
                'granted_date': '2026-03-15',
                'similarity_rate': 78
            }
        ],
        'keywords': ['trademark', 'renewal', 'reminder', 'service', 'intellectual property']
    },
    {
        'id': 'case_041',
        'title': 'Patent Application Status Monitor',
        'filing_date': '2024-04-14',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_001',
        'description': 'Monitor for patent application statuses',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-04-14',
        'due_date': '2024-06-14',
        'references': [
            {
                'url': 'https://dummyurl.com/case_041/ref1',
                'title': 'US Patent 15,123,456 - Patent Application Status Monitor Systems',
                'granted_date': '2028-01-25',
                'similarity_rate': 90
            },
            {
                'url': 'https://dummyurl.com/case_041/ref2',
                'title': 'US Patent 10,987,654 - Application Status Tracking Methods',
                'granted_date': '2026-05-10',
                'similarity_rate': 83
            }
        ],
        'keywords': ['patent', 'application', 'status', 'monitor', 'intellectual property']
    },
    {
        'id': 'case_042',
        'title': 'IP Asset Sale Platform',
        'filing_date': '2024-04-16',
        'status': 'Completed',
        'accepted_on': '2024-04-26',
        'accepted_by': 'user_004',
        'created_by': 'user_002',
        'description': 'Platform for selling IP assets',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-04-16',
        'due_date': '2024-06-16',
        'references': [
            {
                'url': 'https://dummyurl.com/case_042/ref1',
                'title': 'US Patent 15,234,567 - IP Asset Sale Platform Systems',
                'granted_date': '2028-03-20',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_042/ref2',
                'title': 'US Patent 10,876,543 - Asset Sale Automation Methods',
                'granted_date': '2026-07-25',
                'similarity_rate': 80
            }
        ],
        'keywords': ['IP asset', 'sale', 'platform', 'marketplace', 'intellectual property']
    },
    {
        'id': 'case_043',
        'title': 'Trademark Dispute Analytics',
        'filing_date': '2024-04-18',
        'status': 'Active',
        'accepted_on': '2024-04-28',
        'accepted_by': 'user_002',
        'created_by': 'user_003',
        'description': 'Analytics for trademark disputes',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-04-18',
        'due_date': '2024-06-18',
        'references': [
            {
                'url': 'https://dummyurl.com/case_043/ref1',
                'title': 'US Patent 15,345,678 - Trademark Dispute Analytics Systems',
                'granted_date': '2028-05-15',
                'similarity_rate': 91
            },
            {
                'url': 'https://dummyurl.com/case_043/ref2',
                'title': 'US Patent 10,765,432 - Dispute Analysis Methods',
                'granted_date': '2026-09-30',
                'similarity_rate': 84
            }
        ],
        'keywords': ['trademark', 'dispute', 'analytics', 'intellectual property', 'analysis']
    },
    {
        'id': 'case_044',
        'title': 'Patent Family Management',
        'filing_date': '2024-04-20',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_004',
        'description': 'Management tool for patent families',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-04-20',
        'due_date': '2024-06-20',
        'references': [
            {
                'url': 'https://dummyurl.com/case_044/ref1',
                'title': 'US Patent 15,456,789 - Patent Family Management Systems',
                'granted_date': '2028-07-10',
                'similarity_rate': 88
            },
            {
                'url': 'https://dummyurl.com/case_044/ref2',
                'title': 'US Patent 10,654,321 - Family Relationship Management Methods',
                'granted_date': '2026-11-20',
                'similarity_rate': 81
            }
        ],
        'keywords': ['patent', 'family', 'management', 'tool', 'intellectual property']
    },
    {
        'id': 'case_045',
        'title': 'IP Asset Evaluation Tool',
        'filing_date': '2024-04-22',
        'status': 'Completed',
        'accepted_on': '2024-05-02',
        'accepted_by': 'user_003',
        'created_by': 'user_005',
        'description': 'Tool for evaluating IP assets',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-04-22',
        'due_date': '2024-06-22',
        'references': [
            {
                'url': 'https://dummyurl.com/case_045/ref1',
                'title': 'US Patent 15,567,890 - IP Asset Evaluation Tool Systems',
                'granted_date': '2028-09-05',
                'similarity_rate': 89
            },
            {
                'url': 'https://dummyurl.com/case_045/ref2',
                'title': 'US Patent 10,543,210 - Asset Evaluation Methods',
                'granted_date': '2027-01-15',
                'similarity_rate': 82
            }
        ],
        'keywords': ['IP asset', 'evaluation', 'tool', 'assessment', 'intellectual property']
    },
    {
        'id': 'case_046',
        'title': 'Trademark Assignment Workflow',
        'filing_date': '2024-04-24',
        'status': 'Active',
        'accepted_on': '2024-05-04',
        'accepted_by': 'user_004',
        'created_by': 'user_006',
        'description': 'Workflow for trademark assignments',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-04-24',
        'due_date': '2024-06-24',
        'references': [
            {
                'url': 'https://dummyurl.com/case_046/ref1',
                'title': 'US Patent 15,678,901 - Trademark Assignment Workflow Systems',
                'granted_date': '2028-11-20',
                'similarity_rate': 86
            },
            {
                'url': 'https://dummyurl.com/case_046/ref2',
                'title': 'US Patent 10,432,109 - Assignment Process Automation Methods',
                'granted_date': '2027-03-10',
                'similarity_rate': 79
            }
        ],
        'keywords': ['trademark', 'assignment', 'workflow', 'process', 'intellectual property']
    },
    {
        'id': 'case_047',
        'title': 'Patent Expiry Analytics',
        'filing_date': '2024-04-26',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_007',
        'description': 'Analytics for upcoming patent expiries',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-04-26',
        'due_date': '2024-06-26',
        'references': [
            {
                'url': 'https://dummyurl.com/case_047/ref1',
                'title': 'US Patent 15,789,012 - Patent Expiry Analytics Systems',
                'granted_date': '2029-01-15',
                'similarity_rate': 92
            },
            {
                'url': 'https://dummyurl.com/case_047/ref2',
                'title': 'US Patent 10,321,098 - Expiry Prediction Methods',
                'granted_date': '2027-05-25',
                'similarity_rate': 85
            }
        ],
        'keywords': ['patent', 'expiry', 'analytics', 'upcoming', 'intellectual property']
    },
    {
        'id': 'case_048',
        'title': 'IP Asset Portfolio Dashboard',
        'filing_date': '2024-04-28',
        'status': 'Completed',
        'accepted_on': '2024-05-08',
        'accepted_by': 'user_001',
        'created_by': 'user_008',
        'description': 'Dashboard for IP asset portfolios',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-04-28',
        'due_date': '2024-06-28',
        'references': [
            {
                'url': 'https://dummyurl.com/case_048/ref1',
                'title': 'US Patent 15,890,123 - IP Asset Portfolio Dashboard Systems',
                'granted_date': '2029-03-30',
                'similarity_rate': 87
            },
            {
                'url': 'https://dummyurl.com/case_048/ref2',
                'title': 'US Patent 10,210,987 - Portfolio Management Methods',
                'granted_date': '2027-07-20',
                'similarity_rate': 80
            }
        ],
        'keywords': ['IP asset', 'portfolio', 'dashboard', 'management', 'intellectual property']
    },
    {
        'id': 'case_049',
        'title': 'Trademark Filing Deadline Tracker',
        'filing_date': '2024-04-30',
        'status': 'Active',
        'accepted_on': '2024-05-10',
        'accepted_by': 'user_003',
        'created_by': 'user_009',
        'description': 'Tracker for trademark filing deadlines',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-04-30',
        'due_date': '2024-06-30',
        'references': [
            {
                'url': 'https://dummyurl.com/case_049/ref1',
                'title': 'US Patent 15,901,234 - Trademark Filing Deadline Tracker Systems',
                'granted_date': '2029-05-25',
                'similarity_rate': 84
            },
            {
                'url': 'https://dummyurl.com/case_049/ref2',
                'title': 'US Patent 10,109,876 - Deadline Tracking Methods',
                'granted_date': '2027-09-15',
                'similarity_rate': 77
            }
        ],
        'keywords': ['trademark', 'filing', 'deadline', 'tracker', 'reminder']
    },
    {
        'id': 'case_050',
        'title': 'Patent Litigation Analytics',
        'filing_date': '2024-05-02',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'created_by': 'user_010',
        'description': 'Analytics for patent litigation cases',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-05-02',
        'due_date': '2024-07-02',
        'references': [
            {
                'url': 'https://dummyurl.com/case_050/ref1',
                'title': 'US Patent 16,012,345 - Patent Litigation Analytics Systems',
                'granted_date': '2029-07-20',
                'similarity_rate': 93
            },
            {
                'url': 'https://dummyurl.com/case_050/ref2',
                'title': 'US Patent 10,098,765 - Litigation Analysis Methods',
                'granted_date': '2027-11-10',
                'similarity_rate': 86
            }
        ],
        'keywords': ['patent', 'litigation', 'analytics', 'cases', 'intellectual property']
    }
]

mock_users = [
    {
        "full_name": "Alice Johnson",
        "id": "user_001",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_001"],
        "patents": ["patent_001"],
        "created_on": "2023-12-01",
        "deleted_on": None,
        "email": "alice.johnson@example.com",
        "password": "alicepass"
    },
    {
        "full_name": "Bob Smith",
        "id": "user_002",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_001", "case_002"],
        "patents": ["patent_002", "patent_003"],
        "created_on": "2023-11-15",
        "deleted_on": None,
        "email": "bob.smith@example.com",
        "password": "bobpass"
    },
    {
        "full_name": "Carol Lee",
        "id": "user_003",
        "title": "Dr.",
        "role": "client",
        "cases": ["case_002"],
        "patents": ["patent_004"],
        "created_on": "2024-01-10",
        "deleted_on": None,
        "email": "carol.lee@example.com",
        "password": "carolpass"
    },
    {
        "full_name": "David Kim",
        "id": "user_004",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_003"],
        "patents": ["patent_005"],
        "created_on": "2023-10-20",
        "deleted_on": None,
        "email": "david.kim@example.com",
        "password": "davidpass"
    },
    {
        "full_name": "Eva Green",
        "id": "user_005",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_001", "case_003"],
        "patents": ["patent_006", "patent_007"],
        "created_on": "2024-02-05",
        "deleted_on": None,
        "email": "eva.green@example.com",
        "password": "evapass"
    },
    {
        "full_name": "Frank Miller",
        "id": "user_006",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_002", "case_003"],
        "patents": ["patent_008"],
        "created_on": "2023-09-30",
        "deleted_on": None,
        "email": "frank.miller@example.com",
        "password": "frankpass"
    },
    {
        "full_name": "Grace Chen",
        "id": "user_007",
        "title": "Dr.",
        "role": "client",
        "cases": [],
        "patents": [],
        "created_on": "2024-03-01",
        "deleted_on": None,
        "email": "grace.chen@example.com",
        "password": "gracepass"
    },
    {
        "full_name": "Henry Brown",
        "id": "user_008",
        "title": "Mr.",
        "role": "attorney",
        "cases": ["case_001"],
        "patents": ["patent_009"],
        "created_on": "2023-08-12",
        "deleted_on": None,
        "email": "henry.brown@example.com",
        "password": "henrypass"
    },
    {
        "full_name": "Ivy Wilson",
        "id": "user_009",
        "title": "Ms.",
        "role": "client",
        "cases": ["case_003"],
        "patents": ["patent_010"],
        "created_on": "2024-01-22",
        "deleted_on": None,
        "email": "ivy.wilson@example.com",
        "password": "ivypass"
    },
    {
        "full_name": "Jack Davis",
        "id": "user_010",
        "title": "Mr.",
        "role": "attorney",
        "cases": [],
        "patents": [],
        "created_on": "2023-07-05",
        "deleted_on": None,
        "email": "jack.davis@example.com",
        "password": "jackpass"
    }
]

def login_user(email, password):
    """
    Authenticate user login
    
    Args:
        email (str): User's email address
        password (str): User's password
    
    Returns:
        dict: Result containing success status, message, and user_id if successful
    """
    # TODO: Implement actual authentication logic
    # For now, using mock authentication
    if not email or not password:
        return {
            'success': False,
            'message': 'Email and password are required'
        }
    
    # Mock authentication - replace with actual database lookup
    for user in mock_users:
        if user['email'] == email and user['password'] == password:
            return {
                'success': True,
                'message': 'Login successful',
                'user_id': user['id'],
                'email': email
            }
    return {
        'success': False,
        'message': 'Invalid email or password'
    }

def get_all_cases():
    return mock_cases

def get_user_cases(user_id):
    """
    Get cases assigned to a specific user
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        list: List of user's cases
    """
    # TODO: Implement actual database query
    user_cases = []
    for case in mock_cases:
        if case['assigned_to'] == user_id or case['accepted_by'] == user_id or case['created_by'] == user_id:
            user_cases.append(case)
    return user_cases

def get_open_cases():
    """
    Get all open cases available for assignment
    
    Returns:
        list: List of open cases
    """
    open_cases = []
    for case in mock_cases:
        if case['status'] != 'Completed':
            open_cases.append(case)
    return open_cases

def get_user_profile(user_id):
    """
    Get user profile information
    
    Args:
        user_id (str): User's unique identifier
    
    Returns:
        dict: User profile data
    """
    for user in mock_users:
        if user['id'] == user_id:
            user_copy = user.copy()
            if 'password' in user_copy:
                del user_copy['password']
            return user_copy
    return None

def verify_password(user_id, entered_password):
    """
    Verify if the entered password matches the user's current password.

    Args:
        user_id (str): User's unique identifier
        entered_password (str): Password to verify

    Returns:
        bool: True if password matches, False otherwise
    """
    for user in mock_users:
        if user['id'] == user_id:
            return user.get('password') == entered_password
    return False

def change_password(user_id, new_password):
    """
    Change the password for a user.

    Args:
        user_id (str): User's unique identifier
        new_password (str): The new password to set

    Returns:
        dict: Result containing success status and message
    """
    for user in mock_users:
        if user['id'] == user_id:
            user['password'] = new_password
            return {
                'success': True,
                'message': 'Password updated successfully'
            }
    return {
        'success': False,
        'message': 'User not found'
    }

def create_case(case_data):
    """
    Create a new case
    
    Args:
        case_data (dict): Case information
    
    Returns:
        dict: Result containing success status and case_id if successful
    """
    if 'id' not in case_data:
        return {
            'success': False,
            'message': 'Case ID is required'
        }
    if case_data['id'] in mock_cases:
        return {
            'success': False,
            'message': 'Case ID already exists'
        }
    mock_cases.append(case_data)
    return {
        'success': True,
        'message': 'Case created successfully',
        'case_id': case_data['id']
    }

def update_case(case_id, update_data):
    """
    Update an existing case
    
    Args:
        case_id (str): Case identifier
        update_data (dict): Updated case information
    
    Returns:
        dict: Result containing success status
    """
    case = get_case_by_id(case_id, show_password=True)
    case.update(update_data)
    if case:
        return {
            'success': True,
            'message': 'Case updated successfully'
        }
    return {
        'success': False,
        'message': 'Case not found'
    }

def delete_case(case_id):
    """
    Delete a case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        dict: Result containing success status
    """
    for case in mock_cases:
        if case['id'] == case_id:
            mock_cases.remove(case)
            return {
                'success': True,
                'message': 'Case deleted successfully'
            }
    return {
        'success': False,
        'message': 'Case not found'
    }

def get_case_by_id(case_id, show_password=False):
    """
    Get detailed information about a specific case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        dict: Case details or None if not found
    """
    # TODO: Implement actual database query
    for case in mock_cases:
        if case['id'] == case_id:
            # remove password from case before returning
            if 'password' in case and not show_password:
                del case['password']
            return case
    return None

def get_case_related_patents(case_id):
    """
    Get patents related to a specific case
    
    Args:
        case_id (str): Case identifier
    
    Returns:
        list: List of related patents
    """
    # TODO: Implement actual database query
    # Mock data for now
    caseData = get_case_by_id(case_id)
    allData = get_all_cases()
    related_patents = []
    for patent in allData:
        if(patent['id'] != case_id):
            matches = 0
            totals = len(caseData['keywords'])
            for keyword in caseData['keywords']:
                if(keyword in patent['keywords']):
                    matches += 1
            if(matches / totals > 0):
                patent['similarity_rate'] = matches * 100 / totals
                related_patents.append(patent)
    return related_patents