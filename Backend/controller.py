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
        'description': 'A comprehensive system for analyzing patent documents using artificial intelligence',
        'priority': 'High',
        'assigned_to': 'user_123',
        'created_date': '2024-01-15',
        'due_date': '2024-03-15',
        'references': ['https://dummyurl.com/case_001/ref1', 'https://dummyurl.com/case_001/ref2'],
        'keywords': ['AI', 'patent analysis', 'document analysis', 'artificial intelligence', 'system']
    },
    {
        'id': 'case_002',
        'title': 'Blockchain-Based IP Management Platform',
        'filing_date': '2024-01-20',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'A decentralized platform for managing intellectual property rights',
        'priority': 'Medium',
        'assigned_to': 'user_123',
        'created_date': '2024-01-20',
        'due_date': '2024-03-20',
        'references': ['https://dummyurl.com/case_002/ref1', 'https://dummyurl.com/case_002/ref2'],
        'keywords': ['blockchain', 'IP management', 'decentralized', 'intellectual property', 'platform']
    },
    {
        'id': 'case_003',
        'title': 'Machine Learning Patent Search Engine',
        'filing_date': '2024-01-25',
        'status': 'Completed',
        'accepted_on': '2024-02-10',
        'accepted_by': "user_001",
        'description': 'Advanced search engine for patent databases using ML algorithms',
        'priority': 'High',
        'assigned_to': 'user_123',
        'created_date': '2024-01-25',
        'due_date': '2024-03-25',
        'references': ['https://dummyurl.com/case_003/ref1', 'https://dummyurl.com/case_003/ref2'],
        'keywords': ['machine learning', 'patent search', 'search engine', 'ML algorithms', 'patent database']
    },
    {
        'id': 'case_004',
        'title': 'Automated Legal Document Drafting',
        'filing_date': '2024-01-28',
        'status': 'Active',
        'accepted_on': '2024-02-12',
        'accepted_by': 'user_002',
        'description': 'System for drafting legal documents using AI',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-01-28',
        'due_date': '2024-03-28',
        'references': ['https://dummyurl.com/case_004/ref1', 'https://dummyurl.com/case_004/ref2'],
        'keywords': ['legal document', 'drafting', 'automation', 'AI', 'system']
    },
    {
        'id': 'case_005',
        'title': 'IP Portfolio Management Tool',
        'filing_date': '2024-02-01',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Tool for managing IP portfolios for enterprises',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-02-01',
        'due_date': '2024-04-01',
        'references': ['https://dummyurl.com/case_005/ref1', 'https://dummyurl.com/case_005/ref2'],
        'keywords': ['IP portfolio', 'management', 'tool', 'enterprise', 'intellectual property']
    },
    {
        'id': 'case_006',
        'title': 'Trademark Infringement Detection',
        'filing_date': '2024-02-03',
        'status': 'Completed',
        'accepted_on': '2024-02-15',
        'accepted_by': 'user_004',
        'description': 'AI-powered detection of trademark infringements',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-03',
        'due_date': '2024-04-03',
        'references': ['https://dummyurl.com/case_006/ref1', 'https://dummyurl.com/case_006/ref2'],
        'keywords': ['trademark', 'infringement', 'detection', 'AI', 'intellectual property']
    },
    {
        'id': 'case_007',
        'title': 'Patent Valuation Platform',
        'filing_date': '2024-02-05',
        'status': 'Active',
        'accepted_on': '2024-02-18',
        'accepted_by': 'user_002',
        'description': 'Platform for automated patent valuation',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-02-05',
        'due_date': '2024-04-05',
        'references': ['https://dummyurl.com/case_007/ref1', 'https://dummyurl.com/case_007/ref2'],
        'keywords': ['patent', 'valuation', 'platform', 'automation', 'intellectual property']
    },
    {
        'id': 'case_008',
        'title': 'Copyright Management System',
        'filing_date': '2024-02-07',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'System for managing copyright registrations',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-02-07',
        'due_date': '2024-04-07',
        'references': ['https://dummyurl.com/case_008/ref1', 'https://dummyurl.com/case_008/ref2'],
        'keywords': ['copyright', 'management', 'system', 'registration', 'intellectual property']
    },
    {
        'id': 'case_009',
        'title': 'IP Litigation Analytics',
        'filing_date': '2024-02-09',
        'status': 'Completed',
        'accepted_on': '2024-02-20',
        'accepted_by': 'user_004',
        'description': 'Analytics platform for IP litigation trends',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-09',
        'due_date': '2024-04-09',
        'references': ['https://dummyurl.com/case_009/ref1', 'https://dummyurl.com/case_009/ref2'],
        'keywords': ['IP', 'litigation', 'analytics', 'platform', 'trends']
    },
    {
        'id': 'case_010',
        'title': 'Patent Expiry Notification Service',
        'filing_date': '2024-02-11',
        'status': 'Active',
        'accepted_on': '2024-02-22',
        'accepted_by': 'user_003',
        'description': 'Service to notify about upcoming patent expiries',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-02-11',
        'due_date': '2024-04-11',
        'references': ['https://dummyurl.com/case_010/ref1', 'https://dummyurl.com/case_010/ref2'],
        'keywords': ['patent', 'expiry', 'notification', 'service', 'reminder']
    },
    {
        'id': 'case_011',
        'title': 'Trademark Renewal Automation',
        'filing_date': '2024-02-13',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Automated system for trademark renewals',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-02-13',
        'due_date': '2024-04-13',
        'references': ['https://dummyurl.com/case_011/ref1', 'https://dummyurl.com/case_011/ref2'],
        'keywords': ['trademark', 'renewal', 'automation', 'system', 'intellectual property']
    },
    {
        'id': 'case_012',
        'title': 'IP Risk Assessment Tool',
        'filing_date': '2024-02-15',
        'status': 'Completed',
        'accepted_on': '2024-02-25',
        'accepted_by': 'user_001',
        'description': 'Tool for assessing IP-related risks',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-02-15',
        'due_date': '2024-04-15',
        'references': ['https://dummyurl.com/case_012/ref1', 'https://dummyurl.com/case_012/ref2'],
        'keywords': ['IP', 'risk assessment', 'tool', 'risk', 'intellectual property']
    },
    {
        'id': 'case_013',
        'title': 'Patent Licensing Marketplace',
        'filing_date': '2024-02-17',
        'status': 'Active',
        'accepted_on': '2024-02-27',
        'accepted_by': 'user_003',
        'description': 'Marketplace for patent licensing opportunities',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-02-17',
        'due_date': '2024-04-17',
        'references': ['https://dummyurl.com/case_013/ref1', 'https://dummyurl.com/case_013/ref2'],
        'keywords': ['patent', 'licensing', 'marketplace', 'opportunities', 'intellectual property']
    },
    {
        'id': 'case_014',
        'title': 'IP Due Diligence Automation',
        'filing_date': '2024-02-19',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Automated due diligence for IP transactions',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-02-19',
        'due_date': '2024-04-19',
        'references': ['https://dummyurl.com/case_014/ref1', 'https://dummyurl.com/case_014/ref2'],
        'keywords': ['IP', 'due diligence', 'automation', 'transactions', 'intellectual property']
    },
    {
        'id': 'case_015',
        'title': 'Patent Family Tree Visualizer',
        'filing_date': '2024-02-21',
        'status': 'Completed',
        'accepted_on': '2024-03-01',
        'accepted_by': 'user_002',
        'description': 'Visualization tool for patent family relationships',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-02-21',
        'due_date': '2024-04-21',
        'references': ['https://dummyurl.com/case_015/ref1', 'https://dummyurl.com/case_015/ref2'],
        'keywords': ['patent', 'family tree', 'visualization', 'relationships', 'tool']
    },
    {
        'id': 'case_016',
        'title': 'Trademark Watch Service',
        'filing_date': '2024-02-23',
        'status': 'Active',
        'accepted_on': '2024-03-03',
        'accepted_by': 'user_001',
        'description': 'Service to monitor new trademark filings',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-02-23',
        'due_date': '2024-04-23',
        'references': ['https://dummyurl.com/case_016/ref1', 'https://dummyurl.com/case_016/ref2'],
        'keywords': ['trademark', 'watch', 'service', 'monitor', 'filings']
    },
    {
        'id': 'case_017',
        'title': 'IP Asset Valuation Engine',
        'filing_date': '2024-02-25',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Engine for automated IP asset valuation',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-02-25',
        'due_date': '2024-04-25',
        'references': ['https://dummyurl.com/case_017/ref1', 'https://dummyurl.com/case_017/ref2'],
        'keywords': ['IP asset', 'valuation', 'engine', 'automation', 'intellectual property']
    },
    {
        'id': 'case_018',
        'title': 'Patent Application Drafting Assistant',
        'filing_date': '2024-02-27',
        'status': 'Completed',
        'accepted_on': '2024-03-07',
        'accepted_by': 'user_004',
        'description': 'AI assistant for drafting patent applications',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-02-27',
        'due_date': '2024-04-27',
        'references': ['https://dummyurl.com/case_018/ref1', 'https://dummyurl.com/case_018/ref2'],
        'keywords': ['patent', 'application', 'drafting', 'assistant', 'AI']
    },
    {
        'id': 'case_019',
        'title': 'IP Rights Transfer Platform',
        'filing_date': '2024-03-01',
        'status': 'Active',
        'accepted_on': '2024-03-10',
        'accepted_by': 'user_002',
        'description': 'Platform for transferring IP rights securely',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-03-01',
        'due_date': '2024-05-01',
        'references': ['https://dummyurl.com/case_019/ref1', 'https://dummyurl.com/case_019/ref2'],
        'keywords': ['IP rights', 'transfer', 'platform', 'security', 'intellectual property']
    },
    {
        'id': 'case_020',
        'title': 'Trademark Similarity Checker',
        'filing_date': '2024-03-03',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Tool for checking trademark similarity',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-03-03',
        'due_date': '2024-05-03',
        'references': ['https://dummyurl.com/case_020/ref1', 'https://dummyurl.com/case_020/ref2'],
        'keywords': ['trademark', 'similarity', 'checker', 'tool', 'comparison']
    },
    {
        'id': 'case_021',
        'title': 'Patent Filing Deadline Tracker',
        'filing_date': '2024-03-05',
        'status': 'Completed',
        'accepted_on': '2024-03-15',
        'accepted_by': 'user_003',
        'description': 'Tracker for patent filing deadlines',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-03-05',
        'due_date': '2024-05-05',
        'references': ['https://dummyurl.com/case_021/ref1', 'https://dummyurl.com/case_021/ref2'],
        'keywords': ['patent', 'filing', 'deadline', 'tracker', 'reminder']
    },
    {
        'id': 'case_022',
        'title': 'IP Dispute Resolution Portal',
        'filing_date': '2024-03-07',
        'status': 'Active',
        'accepted_on': '2024-03-17',
        'accepted_by': 'user_004',
        'description': 'Portal for resolving IP disputes online',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-03-07',
        'due_date': '2024-05-07',
        'references': ['https://dummyurl.com/case_022/ref1', 'https://dummyurl.com/case_022/ref2'],
        'keywords': ['IP', 'dispute', 'resolution', 'portal', 'online']
    },
    {
        'id': 'case_023',
        'title': 'Patent Prior Art Search Engine',
        'filing_date': '2024-03-09',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Engine for searching patent prior art',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-03-09',
        'due_date': '2024-05-09',
        'references': ['https://dummyurl.com/case_023/ref1', 'https://dummyurl.com/case_023/ref2'],
        'keywords': ['patent', 'prior art', 'search', 'engine', 'intellectual property']
    },
    {
        'id': 'case_024',
        'title': 'IP Licensing Agreement Generator',
        'filing_date': '2024-03-11',
        'status': 'Completed',
        'accepted_on': '2024-03-21',
        'accepted_by': 'user_001',
        'description': 'Generator for IP licensing agreements',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-03-11',
        'due_date': '2024-05-11',
        'references': ['https://dummyurl.com/case_024/ref1', 'https://dummyurl.com/case_024/ref2'],
        'keywords': ['IP', 'licensing', 'agreement', 'generator', 'intellectual property']
    },
    {
        'id': 'case_025',
        'title': 'Trademark Portfolio Dashboard',
        'filing_date': '2024-03-13',
        'status': 'Active',
        'accepted_on': '2024-03-23',
        'accepted_by': 'user_003',
        'description': 'Dashboard for managing trademark portfolios',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-03-13',
        'due_date': '2024-05-13',
        'references': ['https://dummyurl.com/case_025/ref1', 'https://dummyurl.com/case_025/ref2'],
        'keywords': ['trademark', 'portfolio', 'dashboard', 'management', 'intellectual property']
    },
    {
        'id': 'case_026',
        'title': 'Patent Assignment Workflow',
        'filing_date': '2024-03-15',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Workflow system for patent assignments',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-03-15',
        'due_date': '2024-05-15',
        'references': ['https://dummyurl.com/case_026/ref1', 'https://dummyurl.com/case_026/ref2'],
        'keywords': ['patent', 'assignment', 'workflow', 'system', 'intellectual property']
    },
    {
        'id': 'case_027',
        'title': 'IP Asset Insurance Platform',
        'filing_date': '2024-03-17',
        'status': 'Completed',
        'accepted_on': '2024-03-27',
        'accepted_by': 'user_002',
        'description': 'Platform for insuring IP assets',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-03-17',
        'due_date': '2024-05-17',
        'references': ['https://dummyurl.com/case_027/ref1', 'https://dummyurl.com/case_027/ref2'],
        'keywords': ['IP asset', 'insurance', 'platform', 'intellectual property', 'risk']
    },
    {
        'id': 'case_028',
        'title': 'Trademark Application Status Tracker',
        'filing_date': '2024-03-19',
        'status': 'Active',
        'accepted_on': '2024-03-29',
        'accepted_by': 'user_001',
        'description': 'Tracker for trademark application statuses',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-03-19',
        'due_date': '2024-05-19',
        'references': ['https://dummyurl.com/case_028/ref1', 'https://dummyurl.com/case_028/ref2'],
        'keywords': ['trademark', 'application', 'status', 'tracker', 'monitor']
    },
    {
        'id': 'case_029',
        'title': 'Patent Maintenance Fee Calculator',
        'filing_date': '2024-03-21',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Calculator for patent maintenance fees',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-03-21',
        'due_date': '2024-05-21',
        'references': ['https://dummyurl.com/case_029/ref1', 'https://dummyurl.com/case_029/ref2'],
        'keywords': ['patent', 'maintenance fee', 'calculator', 'cost', 'intellectual property']
    },
    {
        'id': 'case_030',
        'title': 'IP Asset Marketplace',
        'filing_date': '2024-03-23',
        'status': 'Completed',
        'accepted_on': '2024-04-02',
        'accepted_by': 'user_004',
        'description': 'Marketplace for buying and selling IP assets',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-03-23',
        'due_date': '2024-05-23',
        'references': ['https://dummyurl.com/case_030/ref1', 'https://dummyurl.com/case_030/ref2'],
        'keywords': ['IP asset', 'marketplace', 'buy', 'sell', 'intellectual property']
    },
    {
        'id': 'case_031',
        'title': 'Trademark Classifier Tool',
        'filing_date': '2024-03-25',
        'status': 'Active',
        'accepted_on': '2024-04-04',
        'accepted_by': 'user_002',
        'description': 'Tool for classifying trademarks',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-03-25',
        'due_date': '2024-05-25',
        'references': ['https://dummyurl.com/case_031/ref1', 'https://dummyurl.com/case_031/ref2'],
        'keywords': ['trademark', 'classifier', 'tool', 'classification', 'intellectual property']
    },
    {
        'id': 'case_032',
        'title': 'Patent Document Translation Service',
        'filing_date': '2024-03-27',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Service for translating patent documents',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-03-27',
        'due_date': '2024-05-27',
        'references': ['https://dummyurl.com/case_032/ref1', 'https://dummyurl.com/case_032/ref2'],
        'keywords': ['patent', 'document', 'translation', 'service', 'language']
    },
    {
        'id': 'case_033',
        'title': 'IP Litigation Support System',
        'filing_date': '2024-03-29',
        'status': 'Completed',
        'accepted_on': '2024-04-08',
        'accepted_by': 'user_003',
        'description': 'Support system for IP litigation cases',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-03-29',
        'due_date': '2024-05-29',
        'references': ['https://dummyurl.com/case_033/ref1', 'https://dummyurl.com/case_033/ref2'],
        'keywords': ['IP', 'litigation', 'support', 'system', 'cases']
    },
    {
        'id': 'case_034',
        'title': 'Trademark Opposition Management',
        'filing_date': '2024-03-31',
        'status': 'Active',
        'accepted_on': '2024-04-10',
        'accepted_by': 'user_004',
        'description': 'Management tool for trademark oppositions',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-03-31',
        'due_date': '2024-05-31',
        'references': ['https://dummyurl.com/case_034/ref1', 'https://dummyurl.com/case_034/ref2'],
        'keywords': ['trademark', 'opposition', 'management', 'tool', 'intellectual property']
    },
    {
        'id': 'case_035',
        'title': 'Patent Search Automation',
        'filing_date': '2024-04-02',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Automation tool for patent searches',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-04-02',
        'due_date': '2024-06-02',
        'references': ['https://dummyurl.com/case_035/ref1', 'https://dummyurl.com/case_035/ref2'],
        'keywords': ['patent', 'search', 'automation', 'tool', 'intellectual property']
    },
    {
        'id': 'case_036',
        'title': 'IP Asset Tracking System',
        'filing_date': '2024-04-04',
        'status': 'Completed',
        'accepted_on': '2024-04-14',
        'accepted_by': 'user_001',
        'description': 'System for tracking IP assets',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-04-04',
        'due_date': '2024-06-04',
        'references': ['https://dummyurl.com/case_036/ref1', 'https://dummyurl.com/case_036/ref2'],
        'keywords': ['IP asset', 'tracking', 'system', 'monitor', 'intellectual property']
    },
    {
        'id': 'case_037',
        'title': 'Trademark Filing Assistant',
        'filing_date': '2024-04-06',
        'status': 'Active',
        'accepted_on': '2024-04-16',
        'accepted_by': 'user_003',
        'description': 'Assistant for filing trademark applications',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-04-06',
        'due_date': '2024-06-06',
        'references': ['https://dummyurl.com/case_037/ref1', 'https://dummyurl.com/case_037/ref2'],
        'keywords': ['trademark', 'filing', 'assistant', 'application', 'intellectual property']
    },
    {
        'id': 'case_038',
        'title': 'Patent Analytics Dashboard',
        'filing_date': '2024-04-08',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Dashboard for patent analytics',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-04-08',
        'due_date': '2024-06-08',
        'references': ['https://dummyurl.com/case_038/ref1', 'https://dummyurl.com/case_038/ref2'],
        'keywords': ['patent', 'analytics', 'dashboard', 'data', 'intellectual property']
    },
    {
        'id': 'case_039',
        'title': 'IP Rights Enforcement Platform',
        'filing_date': '2024-04-10',
        'status': 'Completed',
        'accepted_on': '2024-04-20',
        'accepted_by': 'user_002',
        'description': 'Platform for enforcing IP rights',
        'priority': 'High',
        'assigned_to': 'user_002',
        'created_date': '2024-04-10',
        'due_date': '2024-06-10',
        'references': ['https://dummyurl.com/case_039/ref1', 'https://dummyurl.com/case_039/ref2'],
        'keywords': ['IP rights', 'enforcement', 'platform', 'intellectual property', 'compliance']
    },
    {
        'id': 'case_040',
        'title': 'Trademark Renewal Reminder',
        'filing_date': '2024-04-12',
        'status': 'Active',
        'accepted_on': '2024-04-22',
        'accepted_by': 'user_001',
        'description': 'Reminder service for trademark renewals',
        'priority': 'Medium',
        'assigned_to': 'user_001',
        'created_date': '2024-04-12',
        'due_date': '2024-06-12',
        'references': ['https://dummyurl.com/case_040/ref1', 'https://dummyurl.com/case_040/ref2'],
        'keywords': ['trademark', 'renewal', 'reminder', 'service', 'intellectual property']
    },
    {
        'id': 'case_041',
        'title': 'Patent Application Status Monitor',
        'filing_date': '2024-04-14',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Monitor for patent application statuses',
        'priority': 'Low',
        'assigned_to': 'user_003',
        'created_date': '2024-04-14',
        'due_date': '2024-06-14',
        'references': ['https://dummyurl.com/case_041/ref1', 'https://dummyurl.com/case_041/ref2'],
        'keywords': ['patent', 'application', 'status', 'monitor', 'intellectual property']
    },
    {
        'id': 'case_042',
        'title': 'IP Asset Sale Platform',
        'filing_date': '2024-04-16',
        'status': 'Completed',
        'accepted_on': '2024-04-26',
        'accepted_by': 'user_004',
        'description': 'Platform for selling IP assets',
        'priority': 'High',
        'assigned_to': 'user_004',
        'created_date': '2024-04-16',
        'due_date': '2024-06-16',
        'references': ['https://dummyurl.com/case_042/ref1', 'https://dummyurl.com/case_042/ref2'],
        'keywords': ['IP asset', 'sale', 'platform', 'marketplace', 'intellectual property']
    },
    {
        'id': 'case_043',
        'title': 'Trademark Dispute Analytics',
        'filing_date': '2024-04-18',
        'status': 'Active',
        'accepted_on': '2024-04-28',
        'accepted_by': 'user_002',
        'description': 'Analytics for trademark disputes',
        'priority': 'Medium',
        'assigned_to': 'user_002',
        'created_date': '2024-04-18',
        'due_date': '2024-06-18',
        'references': ['https://dummyurl.com/case_043/ref1', 'https://dummyurl.com/case_043/ref2'],
        'keywords': ['trademark', 'dispute', 'analytics', 'intellectual property', 'analysis']
    },
    {
        'id': 'case_044',
        'title': 'Patent Family Management',
        'filing_date': '2024-04-20',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Management tool for patent families',
        'priority': 'Low',
        'assigned_to': 'user_001',
        'created_date': '2024-04-20',
        'due_date': '2024-06-20',
        'references': ['https://dummyurl.com/case_044/ref1', 'https://dummyurl.com/case_044/ref2'],
        'keywords': ['patent', 'family', 'management', 'tool', 'intellectual property']
    },
    {
        'id': 'case_045',
        'title': 'IP Asset Evaluation Tool',
        'filing_date': '2024-04-22',
        'status': 'Completed',
        'accepted_on': '2024-05-02',
        'accepted_by': 'user_003',
        'description': 'Tool for evaluating IP assets',
        'priority': 'High',
        'assigned_to': 'user_003',
        'created_date': '2024-04-22',
        'due_date': '2024-06-22',
        'references': ['https://dummyurl.com/case_045/ref1', 'https://dummyurl.com/case_045/ref2'],
        'keywords': ['IP asset', 'evaluation', 'tool', 'assessment', 'intellectual property']
    },
    {
        'id': 'case_046',
        'title': 'Trademark Assignment Workflow',
        'filing_date': '2024-04-24',
        'status': 'Active',
        'accepted_on': '2024-05-04',
        'accepted_by': 'user_004',
        'description': 'Workflow for trademark assignments',
        'priority': 'Medium',
        'assigned_to': 'user_004',
        'created_date': '2024-04-24',
        'due_date': '2024-06-24',
        'references': ['https://dummyurl.com/case_046/ref1', 'https://dummyurl.com/case_046/ref2'],
        'keywords': ['trademark', 'assignment', 'workflow', 'process', 'intellectual property']
    },
    {
        'id': 'case_047',
        'title': 'Patent Expiry Analytics',
        'filing_date': '2024-04-26',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Analytics for upcoming patent expiries',
        'priority': 'Low',
        'assigned_to': 'user_002',
        'created_date': '2024-04-26',
        'due_date': '2024-06-26',
        'references': ['https://dummyurl.com/case_047/ref1', 'https://dummyurl.com/case_047/ref2'],
        'keywords': ['patent', 'expiry', 'analytics', 'upcoming', 'intellectual property']
    },
    {
        'id': 'case_048',
        'title': 'IP Asset Portfolio Dashboard',
        'filing_date': '2024-04-28',
        'status': 'Completed',
        'accepted_on': '2024-05-08',
        'accepted_by': 'user_001',
        'description': 'Dashboard for IP asset portfolios',
        'priority': 'High',
        'assigned_to': 'user_001',
        'created_date': '2024-04-28',
        'due_date': '2024-06-28',
        'references': ['https://dummyurl.com/case_048/ref1', 'https://dummyurl.com/case_048/ref2'],
        'keywords': ['IP asset', 'portfolio', 'dashboard', 'management', 'intellectual property']
    },
    {
        'id': 'case_049',
        'title': 'Trademark Filing Deadline Tracker',
        'filing_date': '2024-04-30',
        'status': 'Active',
        'accepted_on': '2024-05-10',
        'accepted_by': 'user_003',
        'description': 'Tracker for trademark filing deadlines',
        'priority': 'Medium',
        'assigned_to': 'user_003',
        'created_date': '2024-04-30',
        'due_date': '2024-06-30',
        'references': ['https://dummyurl.com/case_049/ref1', 'https://dummyurl.com/case_049/ref2'],
        'keywords': ['trademark', 'filing', 'deadline', 'tracker', 'reminder']
    },
    {
        'id': 'case_050',
        'title': 'Patent Litigation Analytics',
        'filing_date': '2024-05-02',
        'status': 'Pending',
        'accepted_on': None,
        'accepted_by': None,
        'description': 'Analytics for patent litigation cases',
        'priority': 'Low',
        'assigned_to': 'user_004',
        'created_date': '2024-05-02',
        'due_date': '2024-07-02',
        'references': ['https://dummyurl.com/case_050/ref1', 'https://dummyurl.com/case_050/ref2'],
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
        if case['assigned_to'] == user_id:
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
            return user
    return None

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
    for case in mock_cases:
        if case['id'] == case_id:
            case.update(update_data)
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

def get_case_by_id(case_id):
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
    mock_patents = {
        'case_001': [
            {
                'id': 'patent_001',
                'title': 'Machine Learning Methods for Patent Classification',
                'granted_date': '2023-06-15',
                'similarity_rate': 85,
                'patent_number': 'US10,123,456',
                'inventor': 'John Doe',
                'assignee': 'Tech Corp Inc.'
            },
            {
                'id': 'patent_002',
                'title': 'Automated Document Analysis Using Neural Networks',
                'granted_date': '2023-08-22',
                'similarity_rate': 72,
                'patent_number': 'US10,234,567',
                'inventor': 'Jane Smith',
                'assignee': 'AI Solutions Ltd.'
            },
            {
                'id': 'patent_003',
                'title': 'Intelligent Search Algorithms for Patent Databases',
                'granted_date': '2023-11-10',
                'similarity_rate': 68,
                'patent_number': 'US10,345,678',
                'inventor': 'Bob Johnson',
                'assignee': 'SearchTech Inc.'
            },
            {
                'id': 'patent_004',
                'title': 'Natural Language Processing for Legal Document Review',
                'granted_date': '2024-01-05',
                'similarity_rate': 91,
                'patent_number': 'US10,456,789',
                'inventor': 'Alice Brown',
                'assignee': 'LegalAI Corp.'
            }
        ],
        'case_002': [
            {
                'id': 'patent_005',
                'title': 'Blockchain-Based Digital Rights Management',
                'granted_date': '2023-04-12',
                'similarity_rate': 88,
                'patent_number': 'US10,567,890',
                'inventor': 'Charlie Wilson',
                'assignee': 'BlockChain Solutions'
            },
            {
                'id': 'patent_006',
                'title': 'Distributed Ledger Technology for IP Tracking',
                'granted_date': '2023-07-18',
                'similarity_rate': 75,
                'patent_number': 'US10,678,901',
                'inventor': 'David Lee',
                'assignee': 'Distributed IP Inc.'
            }
        ],
        'case_003': [
            {
                'id': 'patent_007',
                'title': 'Semantic Search Methods for Patent Databases',
                'granted_date': '2023-09-30',
                'similarity_rate': 82,
                'patent_number': 'US10,789,012',
                'inventor': 'Eva Martinez',
                'assignee': 'Semantic Search Co.'
            },
            {
                'id': 'patent_008',
                'title': 'Vector-Based Patent Similarity Analysis',
                'granted_date': '2023-12-15',
                'similarity_rate': 79,
                'patent_number': 'US10,890,123',
                'inventor': 'Frank Chen',
                'assignee': 'Vector Analytics Ltd.'
            }
        ]
    }
    
    return mock_patents.get(case_id, [])
