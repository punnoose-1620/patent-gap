import openai
import google.generativeai as genai
from env_controller import getEnvKey

report_prompt = ""

def llm_health_check(model_name='gemini-2.5-flash'):
    """
    Check the health of the LLM
    """
    client = None
    if 'gemini' in model_name:
        api_key = getEnvKey('gemini')
        if api_key is None:
            print("GEMINI_API_KEY is not set in environment variables")
            return False
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(model_name)
    elif 'gpt' in model_name:
        api_key = getEnvKey('openai')
        if api_key is None:
            print("OPENAI_API_KEY is not set in environment variables")
            return False
        openai.api_key = api_key
        client = openai.OpenAI(api_key=api_key)
        
    else:
        print(f"Model {model_name} is not supported")
        return False

    response = client.generate_content("Hello, how are you?")
    if response is None:
        return False
    return True