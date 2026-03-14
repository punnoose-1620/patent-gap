import openai
from google import genai
from env_controller import getEnvKey

title_prompt = "You are given two documents: Document A and Document B. Generate a clear and informative title describing the comparison between these two documents in 10 words or fewer. Use only information from the documents and no external references. Do not add any formatting. Strictly stay within the word limit."
report_prompt = "You are given two documents: Document A and Document B. Compare them and generate a concise comparison report of 250 words or fewer. Use only information explicitly contained in the documents and do not include any external references. Do not use any formatting such as headings, bullet points, or numbered lists. Write in plain continuous text. Strictly stay within the word limit."
report_summary_prompt = "You are given a report. Generate a concise summary of the report in 100 words or fewer. Use only information explicitly contained in the report and do not include any external references. Do not use any formatting such as headings, bullet points, or numbered lists. Write in plain continuous text. Strictly stay within the word limit."

def getDefaultModelName():
    """
    Check both Environment variables for API keys and return the default model name
    Gemini > OpenAI > None
    Returns:
        Default model name
    """
    gemini_api_key = getEnvKey('gemini')
    openai_api_key = getEnvKey('openai')
    if gemini_api_key is not None:
        return 'gemini-2.5-flash'
    elif openai_api_key is not None:
        return 'gpt-4o-mini'
    else:
        return None

def getModelClient(model_name='gemini-2.5-flash'):
    """
    Get the model client for the given model name
    Args:
        model_name: Name of the model to use
    Returns:
        Model client
    """
    if 'gemini' in model_name:
        api_key = getEnvKey('gemini')
        if api_key is None:
            print("GEMINI_API_KEY is not set in environment variables")
            return None
        client = genai.Client(api_key=api_key)
    elif 'gpt' in model_name:
        api_key = getEnvKey('openai')
        if api_key is None:
            print("OPENAI_API_KEY is not set in environment variables")
            return None
        openai.api_key = api_key
        client = openai.OpenAI(api_key=api_key)
    else:
        print(f"Model {model_name} is not supported")
        return None
    return client

def llm_health_check(model_name='gemini-2.5-flash'):
    """
    Check the health of the LLM
    """
    client = getModelClient(model_name)
    if client is None:
        return False
    try:
        if 'gemini' in model_name:
            response = client.models.generate_content(model=model_name, contents="Hello, how are you?")
            return response is not None
        else:
            response = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": "Hello, how are you?"}])
            return response is not None
    except Exception:
        return False

def getIndividualReport(reference_text, document_text, model_name='gemini-2.5-flash'):
    """
    Get report for document based on reference text
    Args:
        reference_text: Text of the reference document
        document_text: Text of the document to get report for
        model_name: Name of the model to use
    Returns:
        Report for document (string), or None
    """
    client = getModelClient(model_name)
    if client is None:
        return None
    prompt = f"{report_prompt}\n\nReference Text: {reference_text}\n\nDocument Text: {document_text}"
    try:
        if 'gemini' in model_name:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text if response else None
        else:
            response = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content if response.choices else None
    except Exception:
        return None

def getIndividualTitle(reference_text, document_text, model_name='gemini-2.5-flash'):
    """
    Get title for document based on reference text
    Args:
        reference_text: Text of the reference document
        document_text: Text of the document to get title for
        model_name: Name of the model to use
    Returns:
        Title for document (string), or None
    """
    client = getModelClient(model_name)
    if client is None:
        return None
    prompt = f"{title_prompt}\n\nReference Text: {reference_text}\n\nDocument Text: {document_text}"
    try:
        if 'gemini' in model_name:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text if response else None
        else:
            response = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content if response.choices else None
    except Exception:
        return None

def getCompleteReport(reference_text, documents, model_name='gemini-2.5-flash'):
    """
    Get complete report for documents based on reference text. Returns a markdown formatted report.
    Args:
        reference_text: Text of the reference document
        documents: List of documents to get report for
        model_name: Name of the model to use
    Returns:
        Complete report for documents
    """
    client = getModelClient(model_name)
    if client is None:
        return None

    final_report = ""
    for i in range(len(documents)):
        document = documents[i]
        title = getIndividualTitle(reference_text, document, model_name)
        title = title if title is not None else "Untitled"
        report = getIndividualReport(reference_text, document, model_name)
        if report is not None:
            final_report = f"{final_report}\n-----\n ##{i+1}. {title}\n\n{report}"
    return final_report

def getReportSummary(report, model_name='gemini-2.5-flash'):
    """
    Get summary of the report. report must be the report text (string).
    Args:
        report: Report text to get summary for
        model_name: Name of the model to use
    Returns:
        Summary section string, or None
    """
    client = getModelClient(model_name)
    if client is None:
        return None
    prompt = f"{report_summary_prompt}\n\nReport: {report}"
    try:
        if 'gemini' in model_name:
            response = client.models.generate_content(model=model_name, contents=prompt)
            text = response.text if response else ""
        else:
            response = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}])
            text = response.choices[0].message.content if response.choices else ""
        return f"## Summary\n\n{text}"
    except Exception:
        return None

def getReportWithSummary(report, summary, model_name='gemini-2.5-flash'):
    """
    Get report with summary
    Args:
        report: Report to get summary for
        summary: Summary of the report
        model_name: Name of the model to use
    Returns:
        Report with summary
    """
    return f"# Similarity Report \n\n{summary}\n\n{report}"

def getDummyReportWithSummary(title, model_name='gemini-2.5-flash'):
    """
    Get dummy report with summary
    Args:
        title: Title of the report
        model_name: Name of the model to use
    Returns:
        (dummy_report_text, dummy_summary) both strings, or (None, None)
    """
    dummy_report_prompt = f'You are given the patent application under the title {title} from the US Patent Office. Create a list of 5 similar patents from the US Patent Office. The list can be dummy patents. For each patent provide the following: \n\n- Title of comparison\n- Brief report comparing these 2 patents (limit to 250 words)\n\nThe generated reports should be in MD format with title having "##" and summary having no formatting.'
    client = getModelClient(model_name)
    if client is None:
        return None, None
    prompt = f"{dummy_report_prompt}\n\nTitle: {title}"
    try:
        if 'gemini' in model_name:
            response = client.models.generate_content(model=model_name, contents=prompt)
            dummy_report_text = response.text if response else ""
        else:
            response = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}])
            dummy_report_text = response.choices[0].message.content if response.choices else ""
    except Exception:
        return None, None
    dummy_summary = getReportSummary(dummy_report_text, model_name)
    return dummy_report_text, dummy_summary