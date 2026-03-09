class SearchUrlBuilderByKeywords:
  base_url: str
  def __init__(self, url:str):
    self.base_url = url

  def build_url(self, keywords:list[str], country:str, selector:str):
    if selector == 'free-patents-online':
      return self.free_patents_online(keywords)
    if selector == 'google-patents':
      return self.google_patents(keywords)
    return None

  def free_patents_online(self, keywords:list[str]):
    sort_param = 'sort=relevance'
    keywords_merged = ''

    # for entry in keywords:
    #   entry.replace(' ', '+')

    keywords_merged = "+".join(keywords)
    keywords_merged = keywords_merged.replace(' ', '+')
    print(f"Free Patents Online keywords: {keywords_merged}")
    # for entry in keywords[:-1]:
    #   keywords_merged += entry + '+'
    # keywords_merged += keywords[-1]
    return f'{self.base_url}?{sort_param}&query_txt={keywords_merged}'

  def google_patents(self, keywords:list[str]):
    # for word in keywords:
    #   word.replace(' ', '+')
    keywords_merged = "+".join(keywords)
    keywords_merged = keywords_merged.replace(' ', '+')
    print(f"Google Patents keywords: {keywords_merged}")
    # for entry in keywords[:-1]:
    #   keywords_merged += entry + '+'
    # keywords_merged += keywords[-1]

    q_value = f"q=({keywords_merged})"
    oq_value = f"oq={keywords_merged}"
    page_limit = 'num=5000'

    return f'{self.base_url}/?{q_value}&{page_limit}&{oq_value}'